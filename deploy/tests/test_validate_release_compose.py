import copy
import importlib.util
import pathlib
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / "validate_release_compose.py"
SPEC = importlib.util.spec_from_file_location("validate_release_compose", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

DIGEST = "a" * 64


def valid_model() -> dict:
    services = {
        service: {"image": f"ghcr.io/gerfru/{image}@sha256:{DIGEST}"}
        for service, image in MODULE.EXPECTED_IMAGES.items()
    }
    return {"services": services}


class ValidateReleaseComposeTests(unittest.TestCase):
    def test_accepts_immutable_release_model(self):
        self.assertEqual(MODULE.validate(valid_model()), [])

    def test_rejects_build_directive(self):
        model = valid_model()
        model["services"]["api"]["build"] = {"context": "."}
        self.assertIn(
            "api: release service must not contain build", MODULE.validate(model)
        )

    def test_rejects_mutable_image(self):
        model = valid_model()
        model["services"]["api"]["image"] = "ghcr.io/gerfru/pulsebase-api:latest"
        self.assertTrue(
            any("api: expected immutable" in e for e in MODULE.validate(model))
        )

    def test_rejects_migration_bind_mount(self):
        model = copy.deepcopy(valid_model())
        model["services"]["flyway"]["volumes"] = [
            {"type": "bind", "source": "db/migrations", "target": "/flyway/sql"}
        ]
        self.assertIn(
            "flyway: migrations must be embedded in the image",
            MODULE.validate(model),
        )


if __name__ == "__main__":
    unittest.main()
