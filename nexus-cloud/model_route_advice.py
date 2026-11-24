"""Pure compatibility advice for a reviewed model catalog.

No prompt inspection, network, environment, credential access or dispatch.
The caller remains responsible for fresh configuration review and consent.
"""
from dataclasses import dataclass
from typing import Literal

SLOTS = ("primary", "secondary", "tertiary")
MODES = ("standard", "thinking", "non-thinking")


@dataclass(frozen=True, slots=True)
class Route:
    slot: Literal["primary", "secondary", "tertiary"]
    streaming: bool = False
    modes: tuple[str, ...] = ("standard",)


@dataclass(frozen=True, slots=True)
class Needs:
    mode: str = "standard"
    streaming: bool = False
    preferred_slot: str = "primary"
    on_device_only: bool = False


def recommend(routes: tuple[Route, ...], needs: Needs = Needs()) -> dict:
    """Rank configured compatibility, never infer quality from provider names.

    Cloud routes are not evidence of browser-local execution. No recommendation
    is executable permission, a live health check or a billing estimate.
    """
    if (type(needs) is not Needs or needs.mode not in MODES
            or needs.preferred_slot not in SLOTS
            or type(needs.streaming) is not bool
            or type(needs.on_device_only) is not bool):
        raise ValueError("invalid criteria")
    if type(routes) is not tuple or len(routes) > len(SLOTS):
        raise ValueError("invalid catalog")
    seen = set()
    for route in routes:
        if (type(route) is not Route or route.slot not in SLOTS
                or route.slot in seen or type(route.streaming) is not bool
                or type(route.modes) is not tuple or not route.modes
                or len(route.modes) > len(MODES)
                or any(type(mode) is not str or mode not in MODES for mode in route.modes)
                or len(set(route.modes)) != len(route.modes)
                or "standard" not in route.modes):
            raise ValueError("invalid catalog entry")
        seen.add(route.slot)
    eligible = []
    if needs.on_device_only:
        reason = "DEVICE_CAPABILITY_NOT_ASSESSED"
    else:
        eligible = [r.slot for r in routes if needs.mode in r.modes
                    and (not needs.streaming or r.streaming)]
        eligible.sort(key=lambda slot: (slot != needs.preferred_slot, SLOTS.index(slot)))
        reason = "CONFIGURED_COMPATIBILITY" if eligible else "NO_COMPATIBLE_ROUTE"
    return {
        "reason": reason,
        "eligible_slots": eligible,
        "suggested_slot": eligible[0] if eligible else None,
        "basis": "compatibility_then_preference_then_slot_order",
        "quality": "NOT_ASSESSED",
        "cost": "NOT_ASSESSED",
        "latency": "NOT_ASSESSED",
        "live_availability": "NOT_ASSESSED",
        "requires_fresh_review": True,
        "authority": "none",
    }
