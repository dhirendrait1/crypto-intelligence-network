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


    def test_verified_endpoint_states_update_visible_dashboard_panels(self):
        for panel in ("market", "technical", "screening", "evidence", "news", "monitoring"):
            self.assertIn('data-cin-panel="' + panel + '"', self.html)
        self.assertIn("function updateDashboardPanel(name,state,detail,data)", self.html)
        self.assertIn("updateDashboardPanel(name,state,detail,data);", self.html)
        self.assertIn("function renderEndpointMetrics(name,data)", self.html)
        self.assertIn("function metricLine(container,label,value)", self.html)
        self.assertIn("Latest close", self.html)
        self.assertIn("Funding (% / interval)", self.html)
        self.assertIn("latest_closed_candle_age_seconds", self.html)
        self.assertIn("stale_data_warning", self.html)
        self.assertIn("provider_timestamp_quality_counts", self.html)
        self.assertIn("analysis_candle_count", self.html)
        self.assertIn("data.market_structure||data.summary||data.analysis||{}", self.html)
        self.assertIn("summary.rsi_14??summary.rsi", self.html)
        self.assertIn("summary.directional_bias||summary.trend||summary.bias||summary.direction", self.html)
        self.assertIn("summary.structure_event||summary.market_structure||summary.structure", self.html)
        self.assertIn("open_interest_contracts", self.html)
        self.assertIn("spread_percent", self.html)
        self.assertIn("article.provider_seen_at||article.published_at||\"time unknown\"", self.html)
        self.assertIn("Sentiment method warning", self.html)
        self.assertIn("Headline-only public news; no X, Reddit, or Telegram ingestion.", self.html)
        self.assertIn("Bid/ask notional imbalance", self.html)
        self.assertIn("Open-interest value change (4h %)", self.html)
        self.assertIn("JSON.stringify(data.timestamp_quality||{})", self.html)
        self.assertIn("Analysis eligibility", self.html)
        for metric in (
            "Directional bias", "Structure event", "RSI (14)", "MACD histogram",
            "ATR (14)", "Buy-side swing reference", "Scenario targets status",
            "Analysis limitations",
        ):
            with self.subTest(metric=metric):
                self.assertIn(metric, self.html)
        self.assertIn("data.market_structure||data.summary||data.analysis", self.html)
        self.assertIn("data.indicators||{}", self.html)
        self.assertIn("data.scenario_targets||{}", self.html)
        self.assertIn("indicators.rsi_14??summary.rsi_14??summary.rsi", self.html)
        self.assertIn('if(name==="Technical analysis"){', self.html)
        self.assertIn('Waiting for verified API response; chart geometry remains illustrative.', self.html)
        self.assertIn('analysisPanel.querySelectorAll(".ref-kpi strong").forEach(node=>node.textContent="unknown")', self.html)
        self.assertIn("panel.setAttribute(\"data-api-state\",state)", self.html)
        self.assertIn("if(state!==\"available\")", self.html)
        self.assertIn('panel.setAttribute("data-api-state",state)', self.html)
        self.assertIn('document.querySelectorAll("[data-cin-panel]")', self.html)

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
