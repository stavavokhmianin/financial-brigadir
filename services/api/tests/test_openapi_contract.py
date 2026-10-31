"""openapi.yaml в packages/api_contracts — единственный актуальный контракт (раздел 8.3)."""

import importlib.util
from pathlib import Path
from types import ModuleType

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_openapi.py"

REQUIRED = {  # раздел 22.2
    ("post", "/api/v1/demo/sessions"),
    ("get", "/api/v1/accounts"),
    ("post", "/api/v1/accounts"),
    ("post", "/api/v1/imports/csv"),
    ("get", "/api/v1/transactions"),
    ("get", "/api/v1/obligations"),
    ("post", "/api/v1/obligations"),
    ("post", "/api/v1/forecasts"),
    ("get", "/api/v1/forecasts/{forecast_id}"),
    ("post", "/api/v1/scenarios"),
    ("get", "/api/v1/alerts"),
    ("post", "/api/v1/alerts/read"),
    ("patch", "/api/v1/notification-settings"),
    ("post", "/api/v1/connectors/bank-mock/sync"),
    ("get", "/api/v1/health"),
}
PUBLIC = {
    "/api/v1/health",
    "/api/v1/health/ready",
    "/api/v1/demo/profiles",
    "/api/v1/demo/sessions",
    "/api/v1/demo/live-sessions",
    "/api/v1/meta",
    "/api/v1/pilot/sessions",
}


def _export_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_openapi", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_contract_matches_code() -> None:
    module = _export_module()
    committed = yaml.safe_load(module.TARGET.read_text(encoding="utf-8"))
    assert committed == module.current_schema(), (
        "openapi.yaml устарел: python services/api/scripts/export_openapi.py"
    )


def test_contract_has_all_required_endpoints() -> None:
    schema = _export_module().current_schema()
    present = {(method, path) for path, ops in schema["paths"].items() for method in ops}
    assert present >= REQUIRED
    assert all(path.startswith("/api/v1/") for path in schema["paths"])


def test_private_endpoints_declare_bearer_auth() -> None:
    schema = _export_module().current_schema()
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            secured = bool(op.get("security"))
            assert secured == (path not in PUBLIC), f"{method.upper()} {path}"
            assert op.get("operationId"), f"{method.upper()} {path} без operationId"


def test_money_fields_are_integers() -> None:
    schema = _export_module().current_schema()
    for name, component in schema["components"]["schemas"].items():
        for field, spec in component.get("properties", {}).items():
            if field.endswith("_minor"):
                if spec.get("type") == "array":
                    spec = spec["items"]
                types = {spec.get("type")} | {s.get("type") for s in spec.get("anyOf", [])}
                assert types - {None, "null"} == {"integer"}, f"{name}.{field}"
