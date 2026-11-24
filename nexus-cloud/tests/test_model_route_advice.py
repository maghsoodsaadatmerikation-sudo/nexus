"""Synthetic compatibility cases; no provider clients or user data."""
from itertools import permutations

import pytest

from model_route_advice import Needs, Route, recommend

CATALOG = (
    Route("primary", True),
    Route("secondary", False, ("standard", "thinking", "non-thinking")),
    Route("tertiary", True),
)


def test_deterministic_preference_order_for_every_catalog_permutation():
    for routes in permutations(CATALOG):
        result = recommend(routes, Needs(preferred_slot="tertiary"))
        assert result["eligible_slots"] == ["tertiary", "primary", "secondary"]
        assert result["suggested_slot"] == "tertiary"
        assert result["requires_fresh_review"] is True
        assert result["authority"] == "none"
        for field in ("quality", "cost", "latency", "live_availability"):
            assert result[field] == "NOT_ASSESSED"


def test_required_capabilities_are_not_silently_downgraded():
    assert recommend(CATALOG, Needs(mode="thinking"))["eligible_slots"] == ["secondary"]
    assert recommend(CATALOG, Needs(streaming=True))["eligible_slots"] == ["primary", "tertiary"]
    assert recommend(CATALOG, Needs(mode="thinking", streaming=True))["suggested_slot"] is None


def test_private_device_requirement_never_recommends_cloud():
    result = recommend(CATALOG, Needs(on_device_only=True))
    assert result["eligible_slots"] == []
    assert result["suggested_slot"] is None
    assert result["reason"] == "DEVICE_CAPABILITY_NOT_ASSESSED"


def test_missing_preference_and_empty_catalog():
    assert recommend((CATALOG[2],), Needs(preferred_slot="secondary"))["suggested_slot"] == "tertiary"
    assert recommend(())["reason"] == "NO_COMPATIBLE_ROUTE"


@pytest.mark.parametrize("needs", [Needs(mode="other"), Needs(streaming=1),
                                    Needs(preferred_slot="other"), Needs(on_device_only="yes")])
def test_invalid_criteria(needs):
    with pytest.raises(ValueError):
        recommend(CATALOG, needs)


@pytest.mark.parametrize("routes", [(CATALOG[0], CATALOG[0]), (Route("other"),),
                                    (Route("primary", 1),), (Route("primary", modes=()),),
                                    (Route("primary", modes=("standard", "standard")),),
                                    (Route("primary", modes=("thinking",)),),
                                    (Route("primary", modes=("standard", "other")),)])
def test_invalid_catalog(routes):
    with pytest.raises(ValueError):
        recommend(routes)
