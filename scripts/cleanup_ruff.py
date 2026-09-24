"""
One-off cleanup for the remaining ruff findings that are surgical
edits rather than full-file replacements. Safe to run twice.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def replace_in_file(path: Path, old: str, new: str, *, required: bool = True) -> bool:
    if not path.exists():
        if required:
            print(f"  ! {path} not found")
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"  - {path.name}: pattern not found (already fixed?)")
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"  + {path.name}: applied")
    return True


def remove_duplicate_function(path: Path, func_name: str) -> None:
    """Remove the second (and any later) top-level def of func_name."""
    if not path.exists():
        print(f"  ! {path} not found")
        return
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)

    seen = 0
    ranges = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            seen += 1
            if seen >= 2:
                start = node.lineno
                if node.decorator_list:
                    start = min(d.lineno for d in node.decorator_list)
                end = node.end_lineno
                ranges.append((start - 1, end))

    if not ranges:
        print(f"  - {path.name}: no duplicate {func_name} (already fixed?)")
        return

    for start, end in reversed(ranges):
        # also eat trailing blank lines
        while end < len(lines) and lines[end].strip() == "":
            end += 1
        del lines[start:end]

    path.write_text("".join(lines), encoding="utf-8")
    print(f"  + {path.name}: removed {len(ranges)} duplicate(s) of {func_name}")


def main() -> None:
    print("== E712: .is_(True) ==")
    replace_in_file(
        ROOT / "app/routers/customers.py",
        "Customer.is_active == True)  # ← ADD THIS",
        "Customer.is_active.is_(True))",
    )
    replace_in_file(
        ROOT / "app/routers/customers.py",
        "Address.is_active == True",
        "Address.is_active.is_(True)",
    )
    replace_in_file(
        ROOT / "app/routers/dashboard.py",
        "Product.is_active == True",
        "Product.is_active.is_(True)",
    )
    replace_in_file(
        ROOT / "tests/test_customers.py",
        "Customer.is_active == True",
        "Customer.is_active.is_(True)",
    )

    print("== F401: test_invoices.py availability check ==")
    old_block = (
        "fpdf_available = True\n"
        "try:\n"
        "    from fpdf import FPDF\n"
        "except ImportError:\n"
        "    fpdf_available = False"
    )
    new_block = (
        "import importlib.util\n"
        "fpdf_available = importlib.util.find_spec('fpdf') is not None"
    )
    replace_in_file(ROOT / "tests/test_invoices.py", old_block, new_block)

    print("== B007: rename unused loop var ==")
    replace_in_file(
        ROOT / "tests/ui/test_navigation_ui.py",
        "for href, text in [",
        "for href, _text in [",
    )

    print("== F811: remove duplicate definitions ==")
    remove_duplicate_function(ROOT / "app/routers/customers.py", "list_page")
    remove_duplicate_function(ROOT / "tests/test_customers.py", "test_duplicate_phone_rejected")

    print("\nDone.")


if __name__ == "__main__":
    main()