"""
Remove all remaining `hsn_code` references after the v0.3 product schema
change (HSN dropped in favour of SKU-only).

Handles Python files (dict literals, kwargs, attribute access) and HTML
templates (HSN table columns, HSN badges). Safe to run twice.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY_FILES = list((ROOT / "app").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
HTML_FILES = list((ROOT / "app" / "templates").rglob("*.html"))


def clean_python(path: Path) -> None:
    if path.name in {"cleanup_hsn.py", "cleanup_ruff.py", "fix_test_filter.py"}:
        return
    text = path.read_text(encoding="utf-8")
    original = text

    # 1. dict literal lines:   "hsn_code": "1905",
    text = re.sub(r'^\s*"hsn_code"\s*:\s*[^\n]*,?\s*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r"^\s*'hsn_code'\s*:\s*[^\n]*,?\s*\n", '', text, flags=re.MULTILINE)

    # 2. kwarg lines:          hsn_code=...,  (at start of a line, indented)
    text = re.sub(r'^\s*hsn_code\s*=\s*[^\n]*,?\s*\n', '', text, flags=re.MULTILINE)

    # 3. inline kwargs:        , hsn_code=...,   or  hsn_code=...,  mid-line
    text = re.sub(r',\s*hsn_code\s*=\s*[^,)\n]+', '', text)
    text = re.sub(r'(?<!["\'])hsn_code\s*=\s*[^,)\n]+\s*,\s*', '', text)

    # 4. attribute access:     product.hsn_code   (in non-test code)
    #    Do not remove from strings — those we handle in HTML pass.
    text = re.sub(r'\.hsn_code\b', '.sku', text)

    # 5. dict access:          it["hsn_code"]  /  it['hsn_code']
    text = re.sub(r'\[\s*["\']hsn_code["\']\s*\]', '["sku"]', text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  + {path.relative_to(ROOT)}")


def clean_html(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    original = text

    # Remove <th ...>HSN</th> (with surrounding whitespace)
    text = re.sub(r'\s*<th[^>]*>\s*HSN\s*</th>\s*', '\n', text, flags=re.IGNORECASE)

    # Remove <td ...>{{ item.hsn_code }}</td> or similar
    text = re.sub(
        r'\s*<td[^>]*>\s*\{\{[^}]*hsn_code[^}]*\}\}\s*</td>\s*',
        '\n', text, flags=re.IGNORECASE,
    )

    # Remove HSN badges: <span ...>HSN: {{ ... }}</span>
    text = re.sub(
        r'\s*<span[^>]*>\s*HSN:\s*\{\{[^}]*\}\}\s*</span>\s*', '', text,
        flags=re.IGNORECASE,
    )

    # Any remaining `hsn_code` interpolation left alone? Remove the whole line.
    text = re.sub(r'^.*hsn_code.*\n', '', text, flags=re.MULTILINE)

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"  + {path.relative_to(ROOT)}")


def main() -> None:
    print("Python:")
    for p in PY_FILES:
        clean_python(p)
    print("HTML:")
    for p in HTML_FILES:
        clean_html(p)
    print("\nDone. Now replace invoice_service.py, run ruff + pytest.")


if __name__ == "__main__":
    main()