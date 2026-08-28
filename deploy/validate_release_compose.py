#!/usr/bin/env python3
"""Validate the rendered release Compose model from standard input."""

import json
import re
import sys

EXPECTED_IMAGES = {
    "api": "pulsebase-api",
    "sync-service": "pulsebase-sync",
    "ml-service": "pulsebase-ml",
    "backup": "pulsebase-backup",
    "flyway": "pulsebase-migrations",
}
IMAGE_PATTERN = re.compile(
    r"^ghcr\.io/gerfru/(?P<name>[a-z0-9-]+)@sha256:[0-9a-f]{64}$"
)


def validate(model: dict) -> list[str]:
    errors: list[str] = []
    services = model.get("services", {})

    for service_name, service in services.items():
        if "build" in service:
            errors.append(f"{service_name}: release service must not contain build")

    for service_name, image_name in EXPECTED_IMAGES.items():
        service = services.get(service_name)
        if service is None:
            errors.append(f"{service_name}: required release service is missing")
            continue
        image = service.get("image", "")
        match = IMAGE_PATTERN.fullmatch(image)
        if match is None or match.group("name") != image_name:
            errors.append(
                f"{service_name}: expected immutable ghcr.io/gerfru/{image_name} digest"
            )

    flyway = services.get("flyway", {})
    if flyway.get("volumes"):
        errors.append("flyway: migrations must be embedded in the image")

    return errors


def main() -> int:
    model = json.load(sys.stdin)
    errors = validate(model)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Release Compose model is immutable and source-build free.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
