"""HTTP request handler and the server entrypoint."""
from __future__ import annotations

import datetime as dt
import io
import threading
import urllib.parse
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import profile
import tracker
from db import db_connect, outreach_connect
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

    def do_POST(self) -> None:
        if not self.origin_ok():
            self.send_error(HTTPStatus.FORBIDDEN, "cross-origin POST rejected")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        path = self.path.partition("?")[0]
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
