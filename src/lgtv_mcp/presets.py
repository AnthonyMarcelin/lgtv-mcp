"""Gaming picture presets for LG OLED C2.

Sources (for documentation; not fetched at runtime):
- https://www.rtings.com/tv/reviews/lg/c2-oled/settings
- https://www.youtube.com/watch?v=S0G8sHcFQq8 (HDTVTest)
- https://curaforthegamer.com/optimize/optimize-your-lg-oled-tv-for-gaming
"""

from __future__ import annotations

from typing import Any, TypedDict


class Preset(TypedDict):
    pic_mode: str
    settings: dict[str, Any]
    confirmed_keys: list[str]


PRESETS: dict[str, Preset] = {
    "ps5_hdr": {
        "pic_mode": "hdrGame",
        "settings": {
            "hdrDynamicToneMapping": "HGIG",
            "backlight": 100,
            "contrast": 100,
            "brightness": 50,
            "superResolution": "off",
            "sharpness": 0,
            "dynamicContrast": "off",
        },
        "confirmed_keys": [
            "hdrDynamicToneMapping",
            "backlight",
            "contrast",
            "brightness",
            "superResolution",
            "sharpness",
            "dynamicContrast",
        ],
    },
    "ps5_sdr": {
        "pic_mode": "game",
        "settings": {
            "backlight": 80,
            "contrast": 85,
            "brightness": 50,
            "superResolution": "off",
            "sharpness": 0,
            "dynamicContrast": "off",
            "gamma": "medium",
        },
        "confirmed_keys": [
            "backlight",
            "contrast",
            "brightness",
            "superResolution",
            "sharpness",
            "dynamicContrast",
            "gamma",
        ],
    },
}

MANUAL_STEPS: list[str] = [
    "Game Optimizer genre: Standard",
    "Input lag: Boost",
    "VRR: on",
    "PS5 side: HDR on when supported",
    "PS5 side: RGB auto",
    "PS5 side: Adjust HDR ~14/14/0",
]


def get_preset(name: str) -> Preset:
    if name not in PRESETS:
        raise KeyError(
            f"unknown preset {name!r}; available: {sorted(PRESETS)}"
        )
    return PRESETS[name]
