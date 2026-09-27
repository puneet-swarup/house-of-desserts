"""Tests for unit conversion."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.utils import units


def test_same_unit_passthrough():
    assert units.convert(Decimal("5"), "kg", "kg") == Decimal("5")


def test_g_to_kg():
    assert units.convert(Decimal("500"), "g", "kg") == Decimal("0.5")


def test_kg_to_g():
    assert units.convert(Decimal("0.5"), "kg", "g") == Decimal("500")


def test_ml_to_l():
    assert units.convert(Decimal("250"), "ml", "l") == Decimal("0.25")


def test_l_to_ml():
    assert units.convert(Decimal("1.5"), "l", "ml") == Decimal("1500")


def test_mass_to_volume_rejected():
    with pytest.raises(HTTPException) as ei:
        units.convert(Decimal("100"), "g", "ml")
    assert ei.value.status_code == 400


def test_count_units_are_their_own_group():
    with pytest.raises(HTTPException):
        units.convert(Decimal("1"), "pcs", "packets")


def test_case_insensitive():
    assert units.convert(Decimal("500"), "G", "KG") == Decimal("0.5")


def test_are_compatible():
    assert units.are_compatible("g", "kg") is True
    assert units.are_compatible("ml", "l") is True
    assert units.are_compatible("g", "ml") is False
    assert units.are_compatible("pcs", "packets") is False
