"""
Second-pass patch: catch dict literals where "customer_id" appears INLINE
(not at the start of a line), which the first patch missed.
Idempotent.
"""

from pathlib import Path

LOOKAHEAD = 6


def patch_file(path: Path) -> bool:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    out = []
    changed = False
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)

        has_cid = '"customer_id":' in line or "'customer_id':" in line
        if has_cid:
            window = "".join(lines[i + 1 : i + 1 + LOOKAHEAD])
            already = "fulfillment_date" in line or "fulfillment_date" in window
            same_line_items = '"items":' in line or "'items':" in line
            if not already and not same_line_items:
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                stripped = nxt.lstrip()
                if stripped.startswith('"') or stripped.startswith("'"):
                    indent = nxt[: len(nxt) - len(nxt.lstrip())]
                else:
                    indent = line[: len(line) - len(line.lstrip())] + "    "
                out.append(f'{indent}"fulfillment_date": "2026-12-31T12:00",\n')
                changed = True

        i += 1

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