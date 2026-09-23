"""No shipped file cites the local, unpublished planning document.

That document lives only in a local planning workspace and is never committed here, so any
citation from a file a reader of the published repository can open is a dangling reference.
This now covers `tools/` as well: the consolidated tooling module is read by anyone reviewing
what the gate actually enforces, so its comments are reader-facing too. `tests/` is excluded
because this checker and the README checker must be able to name what they forbid.
"""

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_ROOTS = ("README.md", ".github", "agents", "tools")
NEEDLE = "DESIGN" + ".md"


def tracked_files():
    listed = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "-z", "--cached", "--others",
                             "--exclude-standard", *SHIPPED_ROOTS], capture_output=True, text=True, check=True)
    return [entry for entry in listed.stdout.split("\0") if entry and "__pycache__" not in entry]


class NoDesignMdCitationTestCase(unittest.TestCase):
    def test_the_scan_covers_real_files(self):
        # Guards against a silently-empty scan making the assertion below vacuously true.
        paths = tracked_files()
        self.assertTrue(paths)
        for root in SHIPPED_ROOTS:
            with self.subTest(root=root):
                self.assertTrue(any(path == root or path.startswith(root + "/") for path in paths))

    def test_no_shipped_file_cites_the_unpublished_design_document(self):
        offenders = [path for path in tracked_files()
                     if (REPO_ROOT / path).is_file()
                     and NEEDLE in (REPO_ROOT / path).read_text(encoding="utf-8", errors="replace")]
        self.assertEqual(offenders, [], f"shipped file(s) cite the unpublished planning document: {offenders}")


if __name__ == "__main__":
    unittest.main()
