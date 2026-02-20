"""
Lint check: scripts/ must never import LLM API clients.

Scripts in scripts/ are data utilities (DB seeding, migrations, etc.).
LLM-dependent logic belongs in skills/ as skill scripts.

If this test fails, move the LLM logic to skills/<name>/scripts/ instead.
"""

import ast
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"

# Any import of these modules is forbidden in scripts/
FORBIDDEN_MODULES = {
    "anthropic",
    "openai",
    "pydantic_ai",
    "litellm",
}


def _collect_imports(source: str) -> list[str]:
    """Return all top-level module names imported in the source."""
    tree = ast.parse(source)
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module.split(".")[0])
    return modules


def _python_scripts() -> list[Path]:
    if not SCRIPTS_DIR.exists():
        return []
    return list(SCRIPTS_DIR.glob("**/*.py"))


def test_scripts_dir_exists():
    """scripts/ directory must exist."""
    assert SCRIPTS_DIR.exists(), f"scripts/ directory not found at {SCRIPTS_DIR}"


def test_no_llm_imports_in_scripts():
    """No script in scripts/ may import an LLM client."""
    scripts = _python_scripts()
    violations = []

    for script in scripts:
        source = script.read_text(encoding="utf-8")
        imports = _collect_imports(source)
        bad = [m for m in imports if m in FORBIDDEN_MODULES]
        if bad:
            violations.append(
                f"{script.relative_to(SCRIPTS_DIR.parent)}: "
                f"forbidden imports {bad}"
            )

    assert not violations, (
        "LLM imports found in scripts/ — move this logic to skills/ instead:\n"
        + "\n".join(f"  • {v}" for v in violations)
    )


def test_scripts_have_docstrings():
    """Every script in scripts/ should have a module-level docstring."""
    scripts = _python_scripts()
    missing = []

    for script in scripts:
        source = script.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
            docstring = ast.get_docstring(tree)
            if not docstring:
                missing.append(str(script.relative_to(SCRIPTS_DIR.parent)))
        except SyntaxError:
            missing.append(f"{script.relative_to(SCRIPTS_DIR.parent)} (syntax error)")

    assert not missing, (
        "Scripts missing module docstring:\n"
        + "\n".join(f"  • {m}" for m in missing)
    )
