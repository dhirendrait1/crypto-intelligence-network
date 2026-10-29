"""Static safety and responsive-contract checks for the CIN dashboard preview."""
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = REPO_ROOT / "dashboard" / "index.html"


class DashboardPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = DASHBOARD.read_text(encoding="utf-8")

    def test_preview_is_explicitly_disconnected_and_does_not_claim_live_data(self):
        self.assertIn("UI PREVIEW · API NOT CONNECTED", self.html)
        self.assertIn("This preview does not fetch live data", self.html)
        self.assertIn("No API request has been made.", self.html)

    def test_mobile_viewport_and_narrow_layout_are_defined(self):
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', self.html)
        self.assertIn("@media(max-width:720px)", self.html)
        self.assertIn(".card,.wide{grid-column:1/-1}", self.html)

    def test_required_research_panels_are_present(self):
        for panel in (
            "Market data", "Technical analysis", "Coin screening",
            "Evidence &amp; provenance", "News &amp; derivatives",
            "Monitoring", "Data quality rules",
        ):
            with self.subTest(panel=panel):
                self.assertIn(panel, self.html)

    def test_read_only_boundary_is_visible(self):
        self.assertIn("No trading or order execution", self.html)
        self.assertIn("No wallet access", self.html)
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("XMLHttpRequest", self.html)
        self.assertNotIn("WebSocket(", self.html)

    def test_preview_button_only_updates_local_status(self):
        self.assertIn('document.getElementById("refresh-state").textContent=', self.html)
        self.assertIn("no network request was made", self.html)
        self.assertIn('role="status"', self.html)
        self.assertIn('aria-live="polite"', self.html)


if __name__ == "__main__":
    unittest.main()
