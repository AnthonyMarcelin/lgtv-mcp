"""Gaming picture presets for LG OLED C2.

Sources (documentation only; not fetched at runtime):
- https://www.rtings.com/tv/reviews/lg/c2-oled/settings
- https://www.youtube.com/watch?v=S0G8sHcFQq8 (HDTVTest)
- https://www.youtube.com/watch?v=FDEomvX0YjM (HDTVTest)
- https://www.nintendolife.com/news/2025/06/heres-how-to-fix-the-switch-2s-washed-out-hdr-on-compatible-tvs
  (nintendolife 2025/06 switch-2 HDR fix)
"""

from __future__ import annotations

from typing import Any, TypedDict


class Variant(TypedDict):
    pic_mode: str
    settings: dict[str, Any]


class Preset(TypedDict):
    tv_input: str
    variants: dict[str, Variant]
    manual_steps: list[str]


_SDR_SETTINGS: dict[str, Any] = {
    "superResolution": "off",
    "sharpness": 0,
    "dynamicContrast": "off",
    "dynamicColor": "off",
    "brightness": 50,
    "contrast": 100,
    "gamma": "medium",
}

_HDR_SETTINGS: dict[str, Any] = {
    "hdrDynamicToneMapping": "HGIG",
    "superResolution": "off",
    "sharpness": 0,
    "dynamicContrast": "off",
    "backlight": 100,
    "contrast": 100,
    "brightness": 50,
}

_GAME_OPTIMIZER_STEPS: list[str] = [
    "Game Optimizer: genre Standard, Prevent Input Delay Boost, "
    "VRR & G-Sync on, reduce blue light off, dark room mode off",
]

MANUAL_STEPS_PS5: list[str] = [
    *_GAME_OPTIMIZER_STEPS,
    "PS5: HDR on when supported, RGB range Automatic, "
    "Adjust HDR about 14/14/0, ALLM and VRR Automatic",
]

MANUAL_STEPS_SWITCH2: list[str] = [
    *_GAME_OPTIMIZER_STEPS,
    "Aspect ratio: Just Scan On",
    "Switch 2: HDR output Compatible Software, RGB range Automatic; "
    "Adjust HDR screen 1 until right sun disappears (about 800 nits on C2); "
    "screen 2 paper white 200 (5 clicks from left) in dim room or default 300 "
    "in bright room; if blacks look washed out try TV Black Level Low",
]

# Legacy flat list for callers that only need PS5 steps.
MANUAL_STEPS: list[str] = list(MANUAL_STEPS_PS5)


def _variants() -> dict[str, Variant]:
    return {
        "sdr": {"pic_mode": "game", "settings": dict(_SDR_SETTINGS)},
        "hdr": {"pic_mode": "hdrGame", "settings": dict(_HDR_SETTINGS)},
    }


PRESETS: dict[str, Preset] = {
    "ps5": {
        "tv_input": "hdmi3",
        "variants": _variants(),
        "manual_steps": list(MANUAL_STEPS_PS5),
    },
    "switch2": {
        "tv_input": "hdmi2",
        "variants": _variants(),
        "manual_steps": list(MANUAL_STEPS_SWITCH2),
    },
}

# Alias name -> (base preset, single variant)
PRESET_ALIASES: dict[str, tuple[str, str]] = {
    "ps5_hdr": ("ps5", "hdr"),
    "ps5_sdr": ("ps5", "sdr"),
}

DEFAULT_VARIANTS: list[str] = ["sdr", "hdr"]


def get_preset(name: str) -> Preset:
    """Return a preset by name. Aliases (ps5_hdr, ps5_sdr) resolve to the base preset."""
    base = PRESET_ALIASES[name][0] if name in PRESET_ALIASES else name
    if base not in PRESETS:
        available = sorted(list(PRESETS) + list(PRESET_ALIASES))
        raise KeyError(f"unknown preset {name!r}; available: {available}")
    return PRESETS[base]


def resolve_preset_variants(
    name: str,
    variants: list[str] | None = None,
) -> tuple[str, Preset, list[str]]:
    """Resolve name/aliases to (base_name, preset, variant keys to apply)."""
    if name in PRESET_ALIASES:
        base, forced = PRESET_ALIASES[name]
        return base, PRESETS[base], [forced]
    if name not in PRESETS:
        available = sorted(list(PRESETS) + list(PRESET_ALIASES))
        raise KeyError(f"unknown preset {name!r}; available: {available}")
    chosen = list(variants) if variants is not None else list(DEFAULT_VARIANTS)
    return name, PRESETS[name], chosen
