from importlib.metadata import requires

import financial_sdk


def test_sdk_does_not_load_framework_or_storage_dependencies() -> None:
    assert financial_sdk.__version__ == "0.1.0"
    forbidden = ("fastapi", "sqlalchemy", "pydantic", "react")
    dependencies = tuple(requires("financial-sdk") or ())
    assert all(not dependency.casefold().startswith(forbidden) for dependency in dependencies)
