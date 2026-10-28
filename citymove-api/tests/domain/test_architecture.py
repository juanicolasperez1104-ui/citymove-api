"""Hexagonal rule checked automatically: the inner layers never import
frameworks or outer layers."""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "app"
FORBIDDEN = {
    "domain": {"fastapi", "starlette", "pydantic", "sqlalchemy", "httpx", "duckdb",
               "app.application", "app.infrastructure", "app.api"},
    "application": {"fastapi", "starlette", "pydantic", "sqlalchemy", "httpx", "duckdb",
                    "app.infrastructure", "app.api"},
}


def imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_inner_layers_do_not_depend_on_outer_layers(layer):
    offenders = []
    for file in (ROOT / layer).rglob("*.py"):
        for name in imports_of(file):
            if any(name == f or name.startswith(f + ".") for f in FORBIDDEN[layer]):
                offenders.append(f"{file.relative_to(ROOT)} imports {name}")
    assert offenders == []


def test_four_layers_exist():
    assert {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith("_")} >= {
        "domain", "application", "api", "infrastructure"}
