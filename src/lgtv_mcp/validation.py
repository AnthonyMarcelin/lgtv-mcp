"""Allowlist validation for picture settings and picture modes."""

from __future__ import annotations

from typing import Any

# From bscpylgtv WebOsClient.set_picture_mode docstring.
KNOWN_PICTURE_MODES: frozenset[str] = frozenset(
    {
        "cinema",
        "eco",
        "expert1",
        "expert2",
        "filmMaker",
        "game",
        "normal",
        "personalized",
        "photo",
        "sports",
        "vivid",
        "hdrCinema",
        "hdrCinemaBright",
        "hdrExternal",
        "hdrFilmMaker",
        "hdrGame",
        "hdrPersonalized",
        "hdrStandard",
        "hdrVivid",
        "dolbyHdrCinema",
        "dolbyHdrCinemaBright",
        "dolbyHdrDarkAmazon",
        "dolbyHdrGame",
        "dolbyHdrPersonalized",
        "dolbyHdrStandard",
        "dolbyHdrVivid",
    }
)

KNOWN_DYNAMIC_RANGES: frozenset[str] = frozenset(
    {
        "sdr",
        "sdrALLM",
        "hdr",
        "hdrALLM",
        "technicolorHdr",
        "technicolorHdrALLM",
        "dolbyHdr",
        "dolbyHdrALLM",
    }
)

DEFAULT_PICTURE_KEYS: list[str] = [
    "pictureMode",
    "backlight",
    "contrast",
    "brightness",
    "color",
    "sharpness",
    "gamma",
    "peakBrightness",
    "hdrDynamicToneMapping",
    "colorGamut",
    "colorTemperature",
    "truMotionMode",
    "mpegNoiseReduction",
    "noiseReduction",
    "superResolution",
    "dynamicContrast",
    "blackLevel",
    "adjustingLuminance",
    "gameOptimization",
    "inputOptimization",
    "vrr",
    "allm",
    "eyeComfortMode",
]

# key -> (kind, constraint)
# kind: "int_range" | "enum"
_ALLOWLIST: dict[str, tuple[str, Any]] = {
    "backlight": ("int_range", (0, 100)),
    "contrast": ("int_range", (0, 100)),
    "brightness": ("int_range", (0, 100)),
    "color": ("int_range", (0, 100)),
    "sharpness": ("int_range", (0, 50)),
    "colorTemperature": ("int_range", (-50, 50)),
    "hdrDynamicToneMapping": ("enum", frozenset({"on", "off", "HGIG"})),
    "gamma": ("enum", frozenset({"low", "medium", "high1", "high2"})),
    "peakBrightness": ("enum", frozenset({"off", "low", "medium", "high"})),
    "colorGamut": ("enum", frozenset({"auto", "extended", "wide"})),
    "truMotionMode": (
        "enum",
        frozenset({"off", "cinemaClear", "natural", "smooth", "user", "clear"}),
    ),
    "mpegNoiseReduction": (
        "enum",
        frozenset({"off", "low", "medium", "high", "auto"}),
    ),
    "noiseReduction": (
        "enum",
        frozenset({"off", "low", "medium", "high", "auto"}),
    ),
    "superResolution": ("enum", frozenset({"off", "low", "medium", "high"})),
    "dynamicContrast": ("enum", frozenset({"off", "low", "medium", "high"})),
    "blackLevel": ("enum", frozenset({"low", "high", "auto"})),
}

ALLOWED_SETTING_KEYS: frozenset[str] = frozenset(_ALLOWLIST)


class ValidationError(ValueError):
    """Raised when settings fail allowlist validation."""


def validate_picture_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Validate and return a cleaned copy of picture settings.

    Rejects unknown keys and out-of-bounds values with a clear error.
    """
    if not isinstance(settings, dict) or not settings:
        raise ValidationError("settings must be a non-empty object")

    cleaned: dict[str, Any] = {}
    errors: list[str] = []

    for key, value in settings.items():
        if key not in _ALLOWLIST:
            errors.append(f"unknown key: {key}")
            continue
        kind, constraint = _ALLOWLIST[key]
        if kind == "int_range":
            lo, hi = constraint
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f"{key} must be an integer in [{lo}, {hi}]")
                continue
            if value < lo or value > hi:
                errors.append(f"{key} out of bounds: {value} not in [{lo}, {hi}]")
                continue
            cleaned[key] = value
        elif kind == "enum":
            allowed: frozenset[str] = constraint
            if value not in allowed:
                errors.append(
                    f"{key} invalid value {value!r}; allowed: {sorted(allowed)}"
                )
                continue
            cleaned[key] = value

    if errors:
        raise ValidationError("; ".join(errors))
    return cleaned


def validate_picture_mode(pic_mode: str) -> str:
    if pic_mode not in KNOWN_PICTURE_MODES:
        raise ValidationError(
            f"invalid pic_mode {pic_mode!r}; known: {sorted(KNOWN_PICTURE_MODES)}"
        )
    return pic_mode


def validate_dynamic_range(dynamic_range: str) -> str:
    if dynamic_range not in KNOWN_DYNAMIC_RANGES:
        raise ValidationError(
            f"invalid dynamic_range {dynamic_range!r}; "
            f"known: {sorted(KNOWN_DYNAMIC_RANGES)}"
        )
    return dynamic_range
