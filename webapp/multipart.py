"""Minimal multipart/form-data parser (stdlib dropped `cgi` in 3.13)."""
from __future__ import annotations

import re


def parse_multipart(content_type: str, body: bytes) -> dict[str, bytes]:
    """Returns field-name → raw bytes; enough for a single file upload and
    binary-safe (the payload is never decoded). `\\bname=` avoids matching
    the `filename=` parameter.
    """
    m = re.search(r"boundary=([^;]+)", content_type)
    if not m:
        return {}
    boundary = b"--" + m.group(1).strip().strip('"').encode()
    fields: dict[str, bytes] = {}
    for chunk in body.split(boundary):
        if not chunk or chunk[:2] == b"--":      # preamble / closing delimiter
            continue
        if chunk[:2] == b"\r\n":
            chunk = chunk[2:]
        head, sep, content = chunk.partition(b"\r\n\r\n")
        if not sep:
            continue
        if content.endswith(b"\r\n"):
            content = content[:-2]
        name = re.search(r'\bname="([^"]*)"', head.decode("utf-8", "replace"))
        if name:
            fields[name.group(1)] = content
    return fields
