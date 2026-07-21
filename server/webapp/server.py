"""HTTP request handler and the server entrypoint."""
from __future__ import annotations

import datetime as dt
import io
import json
import threading
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import profile
import tracker
from db import db_connect, outreach_connect
from pipeline import rate_jobs
from sources import Job
from utils import load_config

from .assets import FAVICON
from .multipart import parse_multipart
from .pages import GET_ROUTES
from .state import BUILD, BUILD_LOCK, NOTES_FAILED, NOTES_LOCK, NOTES_PENDING, db
from .workers import build_worker, note_worker


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
        fn = GET_ROUTES.get(path)
        if fn is None:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self.respond(fn(urllib.parse.parse_qs(query)))

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
        elif path == "/add":
            self.post_add(form)
        elif path == "/done":
            self.post_done(form)
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
            jobs.append(Job(
                source=str(it.get("source") or "linkedin"),
                title=str(it.get("title") or "").strip(),
                company=company,
                url=url,
                location=str(it.get("location") or "").strip(),
                description=str(it.get("description") or "").strip()[:2000],
            ))

        conn = db()
        rated = rate_jobs(conn, jobs, cfg)
        conn.close()
        floor = cfg.get("resume", {}).get("min_llm_score", 5)
        body = json.dumps({"results": [
            {"uid": j.uid, "title": j.title, "company": j.company,
             "score": j.score, "llm_score": j.llm_score,
             "fit_note": j.fit_note,
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
                threading.Thread(target=build_worker,
                                 args=("notes" in form,), daemon=True).start()
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
        self.redirect(f"/?date={urllib.parse.quote(date)}")

    def post_add(self, form: dict[str, list[str]]) -> None:
        company = form.get("company", [""])[0].strip()
        if not company:
            self.redirect("/log")
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
        conn.close()
        self.redirect(f"/company?name={urllib.parse.quote(company)}")

    def post_done(self, form: dict[str, list[str]]) -> None:
        raw = form.get("id", [""])[0]
        if raw.isdigit():
            conn = db()
            conn.execute("UPDATE outreach SET followup_done = 1 WHERE id = ?",
                         (int(raw),))
            conn.commit()
            conn.close()
        self.redirect("/due")


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
