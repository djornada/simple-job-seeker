"""HTTP request handler and the server entrypoint."""
from __future__ import annotations

import datetime as dt
import io
import json
import sqlite3
import threading
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import profile
import tracker
from db import applications as apps_db
from db import db_connect, outreach_connect
from pipeline import rate_jobs
from sources import Job
from utils import load_config

from .assets import FAVICON, HTMX_JS
from .layout import company_href
from .multipart import parse_multipart
from .pages import (
    GET_ROUTES,
    ITEM_SELECT,
    expired_on,
    get_build_status,
    get_coverage_status,
    log_prompt,
    note_block,
    render_app,
    render_item,
)
from .state import (
    BUILD,
    BUILD_LOCK,
    COVERAGE_FAILED,
    COVERAGE_LOCK,
    COVERAGE_PENDING,
    NOTES_FAILED,
    NOTES_LOCK,
    NOTES_PENDING,
    db,
)
from .workers import build_worker, coverage_worker, note_worker


class Handler(BaseHTTPRequestHandler):
    server_version = "simple-job-seeker-web/1.0"

    def respond(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_bytes(self, data: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, location: str) -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.end_headers()

    def origin_ok(self) -> bool:
        """Reject cross-site POSTs; same-origin forms send a matching Origin."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin == f"http://{self.headers.get('Host', '')}"

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        if path == "/favicon.ico":
            if FAVICON:
                self.send_bytes(FAVICON, "image/x-icon")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if path == "/static/htmx.min.js":
            self.send_bytes(HTMX_JS, "text/javascript")
            return
        # blank values kept: `/board?log=` opens an empty log dialog
        params = urllib.parse.parse_qs(query, keep_blank_values=True)
        if path == "/company":  # old links: the timeline is a Board row now
            name = params.get("name", [""])[0].strip()
            if name:
                conn = db()
                name = tracker.resolve_company(conn, name)
                conn.close()
            self.redirect(company_href(name) if name else "/board")
            return
        if path == "/log":  # old links: the form is Board's log dialog now
            company = params.get("company", [""])[0]
            self.redirect("/board?log=" + urllib.parse.quote(company))
            return
        if path == "/due":  # old links: due items are Board's due section now
            self.redirect("/board")
            return
        if path == "/gaps":  # old links: skill gaps is a section of Stats now
            days = params.get("days", [""])[0]
            self.redirect("/stats" + (f"?days={urllib.parse.quote(days)}"
                                      if days else "") + "#gaps")
            return
        fn = GET_ROUTES.get(path)
        if fn is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.respond(fn(params))

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin", "")
        path = self.path.partition("?")[0]
        if path == "/api/rate" and origin.startswith("chrome-extension://"):
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers",
                             "Content-Type, X-Extension-Token")
            self.end_headers()
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        path = self.path.partition("?")[0]
        if path == "/api/rate":  # extension calls carry their own token auth
            self.post_api_rate(raw)
            return
        if not self.origin_ok():
            self.send_error(HTTPStatus.FORBIDDEN, "cross-origin POST rejected")
            return
        if path == "/import":  # multipart file upload — keep the raw bytes
            self.post_import(raw, self.headers.get("Content-Type", ""))
            return
        form = urllib.parse.parse_qs(raw.decode())
        if path == "/build":
            self.post_build(form)
        elif path == "/toggle":
            self.post_toggle(form)
        elif path == "/note":
            self.post_note(form)
        elif path == "/coverage":
            self.post_coverage(form)
        elif path == "/add":
            self.post_add(form)
        elif path == "/done":
            self.post_done(form)
        elif path == "/apply":
            self.post_apply(form)
        elif path == "/applications/move":
            self.post_app_move(form)
        elif path == "/applications/followup":
            self.post_app_followup(form)
        elif path == "/applications/sweep":
            self.post_app_sweep(form)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    # -- POST actions -------------------------------------------------------

    def post_api_rate(self, raw: bytes) -> None:
        """Score items the browser extension read off LinkedIn; queue
        anything that clears the bar. Token-gated since this is the one
        endpoint on this server that accepts cross-origin POSTs."""
        cfg = load_config()
        token = cfg.get("extension", {}).get("token", "")
        if not token or self.headers.get("X-Extension-Token") != token:
            self.send_error(HTTPStatus.FORBIDDEN, "missing/invalid extension token")
            return
        try:
            items = json.loads(raw.decode()).get("items", [])
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "invalid JSON body")
            return

        jobs = []
        for it in items:
            url = str(it.get("url") or "").strip()
            company = str(it.get("company") or "").strip()
            if not url or not company:
                continue
            text = str(it.get("description") or "").strip()
            jobs.append(Job(
                source=str(it.get("source") or "linkedin"),
                title=str(it.get("title") or "").strip(),
                company=company,
                url=url,
                location=str(it.get("location") or "").strip(),
                description=text[:2000],
                full_text=text[:20000],
            ))

        conn = db()
        rated = rate_jobs(conn, jobs, cfg)
        conn.close()
        floor = cfg.get("resume", {}).get("min_llm_score", 5)
        body = json.dumps({"results": [
            {"uid": j.uid, "title": j.title, "company": j.company,
             "score": j.score, "llm_score": j.llm_score,
             "fit_note": j.fit_note, "flags": j.flags,
             "queued": j.score > 0 or (j.llm_score or 0) >= floor}
            for j in rated
        ]}).encode()

        origin = self.headers.get("Origin", "")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if origin.startswith("chrome-extension://"):
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(body)

    def post_build(self, form: dict[str, list[str]]) -> None:
        with BUILD_LOCK:
            if not BUILD["running"]:
                BUILD["running"] = True
                BUILD["error"] = ""
                BUILD["progress"] = ""
                threading.Thread(target=build_worker,
                                 args=("notes" in form,), daemon=True).start()
        if self.headers.get("HX-Request") == "true":
            date = form.get("date", [""])[0]
            self.respond(get_build_status({"date": [date]}))
            return
        self.redirect("/")

    def post_import(self, raw: bytes, content_type: str) -> None:
        data = parse_multipart(content_type, raw).get("resume")
        if not data:
            self.redirect("/profile?err=" + urllib.parse.quote("no file selected"))
            return
        try:
            profile.ingest(io.BytesIO(data))
        except zipfile.BadZipFile:
            self.redirect("/profile?err=" + urllib.parse.quote("not a ZIP archive"))
            return
        except profile.ProfileError as e:
            self.redirect("/profile?err=" + urllib.parse.quote(str(e)[:140]))
            return
        self.redirect("/profile?ok=1")

    def post_toggle(self, form: dict[str, list[str]]) -> None:
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        conn = db()
        conn.execute(
            "UPDATE queue_items SET done = 1 - done WHERE date = ? AND uid = ?",
            (date, uid))
        conn.commit()
        self.respond_item(conn, date, uid, offer_log=True)

    def respond_item(self, conn: sqlite3.Connection, date: str, uid: str,
                     offer_log: bool = False) -> None:
        """After a queue-card action: the re-rendered card for htmx, else a
        redirect back to that day's queue. With `offer_log`, a card now
        ticked also opens the log dialog (`log_prompt`). Closes `conn`."""
        if self.headers.get("HX-Request") == "true":
            row = conn.execute(
                f"{ITEM_SELECT} WHERE date = ? AND uid = ?",
                (date, uid)).fetchone()
            prompt = (log_prompt(conn, row, date)
                      if offer_log and row is not None and row["done"] else "")
            conn.close()
            if row is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            with NOTES_LOCK:
                pending, failed = uid in NOTES_PENDING, uid in NOTES_FAILED
            self.respond(render_item(row, date, load_config(), pending, failed)
                         + prompt)
            return
        conn.close()
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_note(self, form: dict[str, list[str]]) -> None:
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        if uid:
            with NOTES_LOCK:
                fresh = uid not in NOTES_PENDING
                NOTES_PENDING.add(uid)
                NOTES_FAILED.discard(uid)  # retry: clear the prior failure
            if fresh:
                threading.Thread(target=note_worker, args=(date, uid),
                                 daemon=True).start()
        if uid and self.headers.get("HX-Request") == "true":
            self.respond(note_block(date, uid, None, True, False))
            return
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_coverage(self, form: dict[str, list[str]]) -> None:
        """"Check keywords": start a background coverage check (the
        `/note` pattern); htmx gets the pending block, which polls."""
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        if uid:
            with COVERAGE_LOCK:
                fresh = uid not in COVERAGE_PENDING
                COVERAGE_PENDING.add(uid)
                COVERAGE_FAILED.pop(uid, None)  # retry: clear prior failure
            if fresh:
                threading.Thread(target=coverage_worker, args=(date, uid),
                                 daemon=True).start()
        if uid and self.headers.get("HX-Request") == "true":
            self.respond(get_coverage_status({"date": [date], "uid": [uid]}))
            return
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_add(self, form: dict[str, list[str]]) -> None:
        company = form.get("company", [""])[0].strip()
        if not company:
            self.redirect("/board?log=")
            return
        action = form.get("action", ["visited"])[0]
        if action not in tracker.ACTIONS:
            action = "visited"
        person = form.get("person", [""])[0].strip() or None
        note = form.get("note", [""])[0].strip() or None
        followup = form.get("followup", [""])[0].strip()
        today = dt.date.today()
        due = ((today + dt.timedelta(days=int(followup))).isoformat()
               if followup.isdigit() else None)
        conn = db()
        company = tracker.resolve_company(conn, company)
        conn.execute(
            "INSERT INTO outreach (company, person, action, note, date, followup_due) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (company, person, action, note, today.isoformat(), due))
        conn.commit()
        uid = form.get("uid", [""])[0]
        if uid:  # a ticked card's log prompt: stay on the queue
            self.respond_item(conn, form.get("date", [""])[0], uid)
            return
        conn.close()
        self.redirect(company_href(company))

    def post_done(self, form: dict[str, list[str]]) -> None:
        raw = form.get("id", [""])[0]
        if raw.isdigit():
            conn = db()
            conn.execute("UPDATE outreach SET followup_done = 1 WHERE id = ?",
                         (int(raw),))
            conn.commit()
            conn.close()
        self.redirect("/board")


    def post_apply(self, form: dict[str, list[str]]) -> None:
        """"I applied": from a queue card (date + uid) or the
        /applications form (company + role)."""
        date = form.get("date", [""])[0]
        uid = form.get("uid", [""])[0]
        conn = db()
        if uid:
            row = conn.execute(
                "SELECT company, title, url FROM queue_items "
                "WHERE date = ? AND uid = ?", (date, uid)).fetchone()
            if row is None:
                conn.close()
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            apps_db.apply(conn, row["company"], row["title"] or "(no title)",
                          url=row["url"], uid=uid)
            self.respond_item(conn, date, uid)
            return
        company = form.get("company", [""])[0].strip()
        role = form.get("role", [""])[0].strip()
        if not company or not role:
            conn.close()
            self.redirect("/applications?err="
                          + urllib.parse.quote("company and role are required"))
            return
        apps_db.apply(conn, tracker.resolve_company(conn, company), role,
                      url=form.get("url", [""])[0].strip() or None,
                      note=form.get("note", [""])[0].strip() or None)
        conn.close()
        self.redirect("/applications")

    def respond_app(self, conn: sqlite3.Connection, raw_id: str, error: str,
                    form: dict[str, list[str]]) -> None:
        """After an application action: the re-rendered row for htmx, else
        a redirect to /board (its due section) or /applications. Closes
        `conn`."""
        if self.headers.get("HX-Request") == "true":
            try:
                row = apps_db.get(conn, int(raw_id))
            except (apps_db.TransitionError, ValueError):
                conn.close()
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            expired = expired_on(conn, [row["uid"]]).get(row["uid"], "")
            conn.close()
            self.respond(render_app(row, error, expired))
            return
        conn.close()
        back = "/board" if form.get("back", [""])[0] == "/board" else "/applications"
        self.redirect(back + ("?err=" + urllib.parse.quote(error) if error else ""))

    def post_app_move(self, form: dict[str, list[str]]) -> None:
        raw_id = form.get("id", [""])[0]
        note = form.get("note", [""])[0].strip() or None
        conn = db()
        error = ""
        try:
            apps_db.move(conn, int(raw_id), form.get("status", [""])[0], note=note)
        except apps_db.TransitionError as e:
            error = str(e)
        except ValueError:
            error = "bad application id"
        self.respond_app(conn, raw_id, error, form)

    def post_app_followup(self, form: dict[str, list[str]]) -> None:
        raw_id = form.get("id", [""])[0]
        conn = db()
        error = ""
        try:
            apps_db.record_followup(conn, int(raw_id))
        except apps_db.TransitionError as e:
            error = str(e)
        except ValueError:
            error = "bad application id"
        self.respond_app(conn, raw_id, error, form)

    def post_app_sweep(self, form: dict[str, list[str]]) -> None:
        """Second step of Board's sweep: move the confirmed ids."""
        ids = [int(i) for i in form.get("id", []) if i.isdigit()]
        conn = db()
        apps_db.sweep(conn, load_config(), ids)
        conn.close()
        self.redirect("/board")


def main() -> int:
    cfg = load_config()
    web = cfg.get("web", {})
    host = web.get("host", "127.0.0.1")
    port = int(web.get("port", 8765))
    # ensure both schemas exist before the first request
    db_connect().close()
    outreach_connect().close()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"simple-job-seeker web UI on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0
