#!/usr/bin/env python3
"""Check that process diagnostics retain bytes hidden by UTF-8 replacement."""
import base64
import hashlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest


class RawCommandLineTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "linux", "requires Linux procfs")
    def test_distinct_invalid_arguments_remain_distinct(self):
        monitor = runpy.run_path(str(Path(__file__).with_name("monitor-build.py")))
        children = []
        try:
            for argument in [b"path-\xff", b"path-\xfe"]:
                children.append(subprocess.Popen([
                    os.fsencode(sys.executable), b"-c", b"import time; time.sleep(60)", argument,
                ]))
            table, _ = monitor["processes"]()
            rows = [table[child.pid] for child in children]
            for child, row in zip(children, rows):
                raw = Path(f"/proc/{child.pid}/cmdline").read_bytes()
                self.assertEqual(base64.b64decode(row["cmdlineBase64"]), raw)
                self.assertEqual(row["cmdlineSha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(rows[0]["argv"], rows[1]["argv"])
            self.assertNotEqual(rows[0]["cmdlineBase64"], rows[1]["cmdlineBase64"])
            self.assertNotEqual(rows[0]["cmdlineSha256"], rows[1]["cmdlineSha256"])
        finally:
            for child in children:
                child.terminate()
                child.wait()


if __name__ == "__main__":
    unittest.main()
