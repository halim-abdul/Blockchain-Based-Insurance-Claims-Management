"""Content-addressed local storage and an opt-in IPFS daemon adapter.

Only synthetic files belong in this demo. IPFS content may become public.
"""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class LocalEvidenceStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data):
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / digest
        if not path.exists():
            path.write_bytes(data)
        return digest


class IpfsEvidenceStore:
    """Uses a trusted local Kubo API; never expose its API port publicly."""

    def __init__(self, api_url="http://127.0.0.1:5001"):
        parsed = urlparse(api_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("IPFS API must be a local HTTP endpoint")
        self.api_url = api_url.rstrip("/")

    def put(self, data):
        boundary = "claims-demo-boundary"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"synthetic-evidence\"\r\n"
                "Content-Type: application/octet-stream\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        request = Request(self.api_url + "/api/v0/add?pin=true", body, method="POST",
                          headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
        cid = result.get("Hash")
        if not isinstance(cid, str) or not cid:
            raise ValueError("IPFS daemon returned no CID")
        return cid
