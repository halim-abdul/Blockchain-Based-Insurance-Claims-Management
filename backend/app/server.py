"""Small localhost JSON API for the synthetic claims demo."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .core import ClaimError, ClaimService
from .evidence_store import IpfsEvidenceStore


ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "frontend"


def handler_for(service):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type="application/json"):
            data = json.dumps(body).encode() if content_type == "application/json" else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'")
            self.end_headers()
            self.wfile.write(data)

        def _route(self):
            path = urlparse(self.path).path
            if self.command == "GET" and path in {"/", "/app.js", "/style.css"}:
                name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
                mime = {"index.html": "text/html; charset=utf-8", "app.js": "text/javascript; charset=utf-8", "style.css": "text/css; charset=utf-8"}[name]
                self._send(200, (STATIC / name).read_bytes(), mime)
                return
            if not path.startswith("/api/"):
                raise ClaimError("Not found", 404)
            actor = self.headers.get("X-Demo-User", "")
            parts = path.strip("/").split("/")
            if self.command == "GET":
                if parts == ["api", "policies"]:
                    result = service.policies(actor)
                elif parts == ["api", "claims"]:
                    result = service.claims(actor)
                elif len(parts) == 3 and parts[:2] == ["api", "claims"]:
                    result = service.detail(actor, parts[2])
                else:
                    raise ClaimError("Not found", 404)
                self._send(200, result)
                return
            if self.command != "POST":
                raise ClaimError("Method not allowed", 405)
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1500000:
                raise ClaimError("Request body must be 1 byte to 1.5 MB", 413)
            try:
                body = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeDecodeError):
                raise ClaimError("Invalid JSON") from None
            if not isinstance(body, dict):
                raise ClaimError("JSON object required")
            key = self.headers.get("Idempotency-Key")
            if parts == ["api", "claims"]:
                result = service.create(actor, key, body.get("policy_id"), body.get("requested_minor"), body.get("incident_date"))
            elif len(parts) == 4 and parts[:2] == ["api", "claims"]:
                claim_id, action = parts[2:]
                if action == "evidence":
                    result = service.add_evidence(actor, key, claim_id, body.get("content_base64"), body.get("mime"))
                else:
                    result = service.transition(actor, key, claim_id, action, body)
            else:
                raise ClaimError("Not found", 404)
            self._send(200, result)

        def do_GET(self):
            self._safe_route()

        def do_POST(self):
            self._safe_route()

        def _safe_route(self):
            try:
                self._route()
            except ClaimError as exc:
                self._send(exc.status, {"error": str(exc)})
            except (OSError, ValueError) as exc:
                self._send(400, {"error": str(exc)})

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Synthetic insurance claims demo")
    parser.add_argument("--db", default="work/claims.sqlite3")
    parser.add_argument("--evidence", default="work/evidence")
    parser.add_argument("--ipfs-api", help="Opt in to a local IPFS daemon; synthetic files only")
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    service = ClaimService(args.db, args.evidence, IpfsEvidenceStore(args.ipfs_api) if args.ipfs_api else None)
    server = ThreadingHTTPServer(("127.0.0.1", 8000), handler_for(service))
    print("Demo running at http://127.0.0.1:8000", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
