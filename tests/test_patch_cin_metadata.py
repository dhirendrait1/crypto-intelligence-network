"""Regression tests for the CIN deployment metadata/router patch."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH_SCRIPT = REPO_ROOT / "patch_cin_metadata_fixed.py"
MODULES = (
    "market_data_step1.py",
    "coin_screening_step2.py",
    "commodity_backing_assessment.py",
    "commodity_backing_api.py",
    "growth_fundamentals_assessment.py",
    "growth_fundamentals_api.py",
    "cin_evidence_ingestion.py",
    "cin_evidence_ingestion_api.py",
    "cin_technical_analysis.py",
    "cin_technical_analysis_api.py",
    "cin_public_market_candles_api.py",
    "cin_derivatives_market_data_api.py",
    "cin_public_news_sentiment_api.py",
    "cin_monitoring_status.py",
    "cin_monitoring_status_api.py",
    "cin_source_observation_contract.py",
)


class DeploymentPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app_dir = self.root / "cin" / "app"
        self.app_dir.mkdir(parents=True)
        (self.app_dir / "main.py").write_text(
            '"""Crypto Intelligence Network (CIN) test app."""\n'
            "from fastapi import FastAPI\n"
            "app = FastAPI()\n\n"
            'if __name__ == "__main__":\n'
            "    pass\n",
            encoding="utf-8",
        )
        for module in MODULES:
            (self.root / module).write_text("# test stub\n", encoding="utf-8")
        self.script = self.root / "patch_cin_metadata_fixed.py"
        self.script.write_text(PATCH_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def run_patch(self):
        return subprocess.run(
            [sys.executable, str(self.script)],
            cwd=self.root,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_patch_is_idempotent_and_registers_routes_before_main_guard(self):
        first = self.run_patch()
        self.assertEqual(first.returncode, 0, first.stderr)
        main_path = self.app_dir / "main.py"
        first_text = main_path.read_text(encoding="utf-8")
        self.assertLess(first_text.index("cin_market_data_router"), first_text.index('if __name__ == "__main__":'))

        second = self.run_patch()
        self.assertEqual(second.returncode, 0, second.stderr)
        second_text = main_path.read_text(encoding="utf-8")
        self.assertEqual(second_text, first_text)

        for router in (
            "cin_market_data_router",
            "cin_coin_screening_router",
            "cin_commodity_backing_router",
            "cin_growth_fundamentals_router",
            "cin_public_evidence_router",
            "cin_technical_analysis_router",
            "cin_public_market_candles_router",
            "cin_derivatives_market_data_router",
            "cin_public_news_sentiment_router",
            "cin_monitoring_status_router",
        ):
            with self.subTest(router=router):
                self.assertEqual(second_text.count(f"app.include_router({router})"), 1)

    def test_monitoring_api_module_is_copied_into_deployment_app(self):
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.root / "cin_monitoring_status_api.py"
        installed = self.app_dir / "cin_monitoring_status_api.py"
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
        main_text = (self.app_dir / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from app.cin_monitoring_status_api import router as cin_monitoring_status_router",
            main_text,
        )
        self.assertEqual(main_text.count("app.include_router(cin_monitoring_status_router)"), 1)

    def test_shared_monitoring_aggregator_is_copied_into_deployment_app(self):
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.root / "cin_monitoring_status.py"
        installed = self.app_dir / "cin_monitoring_status.py"
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))

    def test_missing_required_module_fails_before_any_scaffold_mutation(self):
        main_path = self.app_dir / "main.py"
        original_main = main_path.read_text(encoding="utf-8")
        missing_module = self.root / MODULES[-1]
        missing_module.unlink()

        result = self.run_patch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Required CIN module(s) not found", result.stderr)
        self.assertEqual(main_path.read_text(encoding="utf-8"), original_main)
        self.assertFalse(any((self.app_dir / name).exists() for name in MODULES))

    def test_missing_branding_title_fails_before_any_scaffold_mutation(self):
        main_path = self.app_dir / "main.py"
        original_main = main_path.read_text(encoding="utf-8")
        main_path.write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")

        result = self.run_patch()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Could not find a CIN application title to validate", result.stderr)
        self.assertEqual(main_path.read_text(encoding="utf-8"), "from fastapi import FastAPI\napp = FastAPI()\n")
        self.assertFalse(any((self.app_dir / name).exists() for name in MODULES))

    def test_old_branding_normalization_preserves_new_router_registrations(self):
        main_path = self.app_dir / "main.py"
        original = main_path.read_text(encoding="utf-8")
        main_path.write_text(
            original.replace("Crypto Intelligence Network (CIN)", "Crypto Intelligence Engine", 1),
            encoding="utf-8",
        )

        result = self.run_patch()

        self.assertEqual(result.returncode, 0, result.stderr)
        patched = main_path.read_text(encoding="utf-8")
        self.assertIn('"""Crypto Intelligence Network (CIN) test app."""', patched)
        self.assertIn("from app.market_data_step1 import router as cin_market_data_router", patched)
        self.assertIn("app.include_router(cin_market_data_router)", patched)
        self.assertLess(patched.index("cin_market_data_router"), patched.index('if __name__ == "__main__":'))

        second = self.run_patch()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(main_path.read_text(encoding="utf-8"), patched)

    def test_patch_fails_closed_on_partial_router_registration(self):
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        main_path = self.app_dir / "main.py"
        original = main_path.read_text(encoding="utf-8")
        # Simulate pending branding normalization and a partially registered route.
        broken = original.replace("Crypto Intelligence Network (CIN)", "Crypto Intelligence Engine", 1)
        broken = broken.replace("app.include_router(cin_market_data_router)\n", "", 1)
        main_path.write_text(broken, encoding="utf-8")
        for module in MODULES:
            (self.app_dir / module).unlink()

        result = self.run_patch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Partial router registration detected", result.stderr)
        self.assertEqual(main_path.read_text(encoding="utf-8"), broken)
        self.assertFalse(any((self.app_dir / name).exists() for name in MODULES))


    def test_source_observation_contract_is_copied_into_deployment_app(self):
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.root / "cin_source_observation_contract.py"
        installed = self.app_dir / "cin_source_observation_contract.py"
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))


    def test_source_observation_contract_is_copied_into_deployment_app(self):
        result = self.run_patch()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.root / "cin_source_observation_contract.py"
        installed = self.app_dir / "cin_source_observation_contract.py"
        self.assertTrue(installed.is_file())
        self.assertEqual(installed.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
