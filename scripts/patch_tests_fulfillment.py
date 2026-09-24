"""
Add fulfillment_date to every test call to create_order() and POST /orders.
Idempotent — safe to run twice.
"""

from pathlib import Path

FULFILLMENT_LINE = '"fulfillment_date": "2026-12-31T12:00",'
LOOKAHEAD = 25  # lines to scan forward for an existing fulfillment_date


def patch_file(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    changed = False

    for i, line in enumerate(lines):
        out.append(line)
        stripped = line.lstrip()

        # Trigger on the customer_id key inside any dict literal
        if stripped.startswith('"customer_id":') or stripped.startswith("'customer_id':"):
            window = "".join(lines[i + 1 : i + 1 + LOOKAHEAD])
            if "fulfillment_date" not in window:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f"{indent}{FULFILLMENT_LINE}\n")
                changed = True

    if changed:
        path.write_text("".join(out), encoding="utf-8")
    return changed


def main() -> None:
    root = Path("tests")
    for p in sorted(root.rglob("*.py")):
        if p.name == "__init__.py":
            continue
        if patch_file(p):
            print(f"  patched: {p}")


if __name__ == "__main__":
    main()