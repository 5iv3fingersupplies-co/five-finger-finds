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

    def test_monetization_uses_supplied_public_tag(self):
        affiliate = json.loads((ROOT / "data/affiliate.json").read_text(encoding="utf-8"))
        self.assertTrue(affiliate["monetization_enabled"])
        self.assertEqual(affiliate["amazon_associates_tag"], "fivefingersup-20")
        html = (ROOT / "site/tools/power-bank-capacity-calculator/index.html").read_text(encoding="utf-8")
        self.assertNotIn("Affiliate link inactive", html)
        self.assertIn("https://www.amazon.com/s?", html)
        self.assertIn("tag=fivefingersup-20", html)
        self.assertIn('rel="sponsored nofollow noopener"', html)

    def test_optimization_report_runs(self):
        subprocess.run([sys.executable, "scripts/optimize.py", "--out", "reports"], cwd=ROOT, check=True)
        report_path = ROOT / "reports/optimization-report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["cost"]["incremental_usd"], 0)
        self.assertFalse(report["cost"]["paid_apis_used"])
        self.assertGreaterEqual(len(report["top_page_actions"]), 10)
        self.assertGreaterEqual(len(report["content_gap_actions"]), 5)


if __name__ == "__main__":
    unittest.main()
