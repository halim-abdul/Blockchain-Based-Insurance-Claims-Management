import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.evidence_store import IpfsEvidenceStore, LocalEvidenceStore


class FakeResponse:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return b'{"Hash":"bafy-synthetic-cid"}'


class StorageTest(unittest.TestCase):
    def test_local_store_is_content_addressed(self):
        scratch = Path(__file__).resolve().parents[2] / "work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            store = LocalEvidenceStore(folder)
            digest = hashlib.sha256(b"SYNTHETIC").hexdigest()
            self.assertEqual(store.put(b"SYNTHETIC"), digest)
            self.assertEqual(store.put(b"SYNTHETIC"), digest)
            self.assertEqual((Path(folder) / digest).read_bytes(), b"SYNTHETIC")

    def test_ipfs_requires_local_api(self):
        with self.assertRaises(ValueError):
            IpfsEvidenceStore("https://public.example")

    def test_ipfs_adapter_returns_cid(self):
        with patch("backend.app.evidence_store.urlopen", return_value=FakeResponse()) as send:
            cid = IpfsEvidenceStore().put(b"SYNTHETIC")
        self.assertEqual(cid, "bafy-synthetic-cid")
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertIn(b"SYNTHETIC", request.data)


if __name__ == "__main__": unittest.main()
