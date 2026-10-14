"""Allowlist and bounds validation."""

from __future__ import annotations

import pytest

from lgtv_mcp.validation import (
    ValidationError,
    validate_picture_mode,
    validate_picture_settings,
)


def test_valid_settings():
    out = validate_picture_settings(
        {
            "backlight": 80,
            "sharpness": 0,
            "hdrDynamicToneMapping": "HGIG",
            "colorTemperature": -10,
        }
    )
    assert out["backlight"] == 80
    assert out["hdrDynamicToneMapping"] == "HGIG"


def test_unknown_key_rejected():
    with pytest.raises(ValidationError, match="unknown key"):
        validate_picture_settings({"backlight": 50, "notARealKey": 1})


def test_out_of_bounds_rejected():
    with pytest.raises(ValidationError, match="out of bounds"):
        validate_picture_settings({"backlight": 101})
    with pytest.raises(ValidationError, match="out of bounds"):
        validate_picture_settings({"sharpness": 51})
    with pytest.raises(ValidationError, match="out of bounds"):
        validate_picture_settings({"colorTemperature": -51})


def test_enum_rejected():
    with pytest.raises(ValidationError, match="invalid value"):
        validate_picture_settings({"gamma": "ultra"})


def test_bool_not_accepted_as_int():
    with pytest.raises(ValidationError, match="integer"):
        validate_picture_settings({"backlight": True})


def test_picture_mode():
    assert validate_picture_mode("hdrGame") == "hdrGame"
    with pytest.raises(ValidationError, match="invalid pic_mode"):
        validate_picture_mode("notAMode")
