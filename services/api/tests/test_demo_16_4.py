"""Сквозное демо из раздела 16.4 как автотест: ключевые числа не должны «уплыть» к показу."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "demo_walkthrough.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("demo_walkthrough", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_walkthrough_matches_golden_numbers(capsys: pytest.CaptureFixture[str]) -> None:
    module = _module()
    demo = module.Demo(module.offline_caller())
    assert demo.run() == 0, demo.failures
    out = capsys.readouterr().out.replace(" ", " ")
    assert "Демо 16.4 прошло" in out
    assert "Если 20 октября купить «Телефон» за 12 000 ₽" in out
