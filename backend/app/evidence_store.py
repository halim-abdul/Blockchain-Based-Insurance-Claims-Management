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


