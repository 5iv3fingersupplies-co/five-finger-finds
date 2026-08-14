from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SiteBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, "scripts/maintenance.py", "--out", "reports"], cwd=ROOT, check=True)
        subprocess.run([sys.executable, "scripts/build.py", "--out", "site", "--automation-report", "reports/automation-report.json"], cwd=ROOT, check=True)

    def test_validation_passes(self):
        subprocess.run([sys.executable, "scripts/validate.py", "--dist", "site"], cwd=ROOT, check=True)

    def test_tool_and_guide_counts(self):
        tools = json.loads((ROOT / "data/tools.json").read_text(encoding="utf-8"))
        guides = json.loads((ROOT / "data/pages.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(tools), 10)
        self.assertGreaterEqual(len(guides), 25)

    def test_generated_pages_exist(self):
        html_pages = list((ROOT / "site").rglob("*.html"))
        self.assertGreaterEqual(len(html_pages), 40)
        self.assertTrue((ROOT / "site/tools/portable-air-pump-selector/index.html").exists())
        self.assertTrue((ROOT / "site/guides/household-emergency-kit-without-clutter/index.html").exists())

    def test_monetization_is_placeholder_until_tag_supplied(self):
        affiliate = json.loads((ROOT / "data/affiliate.json").read_text(encoding="utf-8"))
        self.assertFalse(affiliate["monetization_enabled"])
        self.assertEqual(affiliate["amazon_associates_tag"], "")
        html = (ROOT / "site/tools/power-bank-capacity-calculator/index.html").read_text(encoding="utf-8")
        self.assertIn("Affiliate link inactive", html)
        self.assertNotIn("amazon.com/s?", html)


if __name__ == "__main__":
    unittest.main()
