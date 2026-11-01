from pathlib import Path


def test_application_consumes_public_sdk_boundary() -> None:
    app = Path(__file__).parents[1] / "app"
    offenders = [
        path.relative_to(app)
        for path in app.rglob("*.py")
        if "forecast_core" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []
