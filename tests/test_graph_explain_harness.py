"""Keep the scoped explain guardrails tied to executable regression checks."""
import ast
from pathlib import Path
import re


def test_explain_failure_memory_points_to_executable_regressions():
    root = Path(__file__).resolve().parents[1]
    memory = root / "docs/failures/kg-explain-boundary.md"
    instruction = (root / ".github/instructions/kg-explain.instructions.md").read_text(encoding="utf-8")
    assert "docs/failures/kg-explain-boundary.md" in instruction
    targets = re.findall(r"`(tests/[^`]+\.py)::(test_\w+)`", memory.read_text(encoding="utf-8"))
    assert len(targets) >= 7
    for file, name in targets:
        tree = ast.parse((root/file).read_text(encoding="utf-8"))
        assert name in {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}, (file,name)
