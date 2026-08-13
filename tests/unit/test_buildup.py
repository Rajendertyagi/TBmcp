"""Unit tests for OI/price buildup classification logic."""
from __future__ import annotations

import pytest

from analytics import buildup_color, classify_buildup
from constants import BUILDUP_COLORS, NEUTRAL_BUILDUP


class TestClassifyBuildup:
    @pytest.mark.parametrize("oi_change,price_change,expected", [
        # OI up + price up        -> Long Buildup (bullish)
        (10, 5, "Long Buildup"),
        (0.1, 0.01, "Long Buildup"),
        # OI up + price down      -> Short Buildup (bearish)
        (10, -5, "Short Buildup"),
        # OI down + price down    -> Long Unwinding (bulls exiting)
        (-10, -5, "Long Unwinding"),
        # OI down + price up      -> Short Covering (bears exiting)
        (-10, 5, "Short Covering"),
        # Flat/ambiguous          -> Neutral
        (0, 5, NEUTRAL_BUILDUP),
        (5, 0, NEUTRAL_BUILDUP),
        (0, 0, NEUTRAL_BUILDUP),
        (-5, 0, NEUTRAL_BUILDUP),
        (0, -5, NEUTRAL_BUILDUP),
    ])
    def test_quadrants(self, oi_change, price_change, expected):
        assert classify_buildup(oi_change, price_change) == expected


class TestBuildupColor:
    def test_known_tag_maps_to_constant_color(self):
        for tag, color in BUILDUP_COLORS.items():
            assert buildup_color(tag) == color

    def test_unknown_tag_falls_back_to_neutral(self):
        assert buildup_color("Bogus Tag") == BUILDUP_COLORS[NEUTRAL_BUILDUP]
        assert buildup_color("") == BUILDUP_COLORS[NEUTRAL_BUILDUP]

    def test_neutral_is_never_orphaned(self):
        # The neutral entry must exist in the color map so the fallback works.
        assert NEUTRAL_BUILDUP in BUILDUP_COLORS
