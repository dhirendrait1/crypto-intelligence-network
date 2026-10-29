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
            "Evidence & provenance", "News & derivatives",
            "Monitoring", "Data quality rules",
        ):
            with self.subTest(panel=panel):
                self.assertIn(panel, self.html)

    def test_read_only_boundary_is_visible(self):
        self.assertIn("No trading or order execution", self.html)
        self.assertIn("No wallet access", self.html)
        self.assertNotIn("XMLHttpRequest", self.html)
        self.assertNotIn("WebSocket(", self.html)
        self.assertIn('id="connect-api"', self.html)
        self.assertIn('method:"GET"', self.html)
        self.assertIn('credentials:"omit"', self.html)
        self.assertIn('redirect:"error"', self.html)
        self.assertIn('id="disconnect-api"', self.html)
        self.assertNotIn('method:"POST"', self.html)
        self.assertNotIn("/orders", self.html)
        self.assertNotIn("/wallet", self.html)

    def test_preview_button_only_updates_local_status(self):
        self.assertIn('document.getElementById("refresh-state").textContent=', self.html)
        self.assertIn("No request was made by this button.", self.html)
        self.assertIn('role="status"', self.html)
        self.assertIn('aria-live="polite"', self.html)

    def test_api_requests_require_explicit_user_action_and_safe_origin(self):
        self.assertIn('connectButton.addEventListener("click"', self.html)
        self.assertIn('disconnectButton.addEventListener("click"', self.html)
        self.assertIn('function validOrigin(value)', self.html)
        self.assertIn('url.protocol==="https:"||url.protocol==="http:"', self.html)
        self.assertIn('activeController=new AbortController()', self.html)
        self.assertIn('cache:"no-store"', self.html)
        self.assertIn('results.replaceChildren()', self.html)
        self.assertIn('Partial connection:', self.html)
        self.assertIn('Request blocked or network/CORS error.', self.html)


    def test_read_only_endpoints_and_response_schemas_are_explicit(self):
        for endpoint in (
            "/market-candles?symbol=BTCUSDT",
            "/technical-analysis/market?symbol=BTCUSDT",
            "/coin-screening?vs_currency=usd",
            "/news-sentiment?query=cryptocurrency",
            "/derivatives/market-snapshot?symbol=BTCUSDT",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertIn(endpoint, self.html)
        self.assertIn("Invalid CIN response schema", self.html)
        self.assertIn("Number.isInteger(data.count)&&Array.isArray(data.data)", self.html)
        self.assertIn("!!data.sentiment_summary", self.html)
        self.assertIn("!!data.data_quality", self.html)
        self.assertIn("not data correctness, freshness, or source authenticity", self.html)


    def test_reference_matched_dense_intelligence_terminal_is_present(self):
        for section in (
            "Market status ribbon",
            "BTC market structure",
            "Feed latency & data quality",
            "Neural shell / evidence relationship map",
            "Watchlist / screening",
            "Execution tape / event stream",
            "Resolution funnel / analysis trace",
            "READ ONLY",
            "No wallet connected",
        ):
            with self.subTest(section=section):
                self.assertIn(section, self.html)
        self.assertIn('id="network-dots"', self.html)
        self.assertIn("for(let i=0;i<560;i++)", self.html)
        self.assertIn("not live measurements", self.html)
        self.assertIn("Nodes are illustrative", self.html)
        self.assertIn("@media(max-width:560px)", self.html)
        self.assertIn("No live data", self.html)


if __name__ == "__main__":
    unittest.main()
