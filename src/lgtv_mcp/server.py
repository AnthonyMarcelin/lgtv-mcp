"""FastMCP server: LG TV tools over streamable HTTP."""

from __future__ import annotations

from typing import Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lgtv_mcp.auth import StaticBearerVerifier
from lgtv_mcp import backups as backup_store
from lgtv_mcp.backups import BackupError, read_backup, write_backup
from lgtv_mcp.config import Config, load_config
from lgtv_mcp.presets import resolve_preset_variants
from lgtv_mcp.manifest import write_error_message
from lgtv_mcp.tv import TVError, connected_client, is_paired, read_settings
from lgtv_mcp.validation import (
    ALLOWED_SETTING_KEYS,
    DEFAULT_PICTURE_KEYS,
    ValidationError,
    validate_dynamic_range,
    validate_picture_mode,
    validate_picture_settings,
)
from lgtv_mcp.wol import send_magic_packet


def create_mcp(config: Config | None = None) -> FastMCP:
    cfg = config or load_config()
    cfg.ensure_dirs()

    issuer = f"http://{cfg.mcp_bind_host}:{cfg.mcp_port}"
    # 0.0.0.0 is not a valid issuer host for URL parsers in some cases
    if cfg.mcp_bind_host in ("0.0.0.0", "::"):
        issuer = f"http://127.0.0.1:{cfg.mcp_port}"

    mcp = FastMCP(
        "lgtv-mcp",
        instructions=(
            "Control an LG OLED C2 (webOS 22) over LAN. "
            "Pair once with python -m lgtv_mcp.pair before using tools."
        ),
        host=cfg.mcp_bind_host,
        port=cfg.mcp_port,
        streamable_http_path="/mcp",
        stateless_http=True,
        # LAN control server: clients often hit a raw IP; Host checks are not useful here.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        token_verifier=StaticBearerVerifier(cfg.mcp_bearer_token),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(issuer),
            validate_token_resource=False,
        ),
    )

    @mcp.custom_route("/healthz", methods=["GET"])
    async def healthz(_request: Request) -> Response:
        return JSONResponse({"ok": True})

    @mcp.tool(description="Power state, current input/app, software info, paired yes/no.")
    async def get_status() -> dict[str, Any]:
        paired = await is_paired(cfg)
        result: dict[str, Any] = {
            "paired": paired,
            "host": cfg.lgtv_host,
            "power": None,
            "system_info": None,
            "software_info": None,
            "current_input_or_app": None,
            "inputs": None,
            "warnings": [],
        }

        async def _optional(label: str, coro: Any) -> Any:
            try:
                return await coro
            except Exception as exc:
                result["warnings"].append(f"{label}: {exc}")
                return None

        try:
            async with connected_client(cfg) as client:
                result["paired"] = bool(client.is_registered())
                result["power"] = await _optional("power", client.get_power_state())
                result["system_info"] = await _optional(
                    "system_info", client.get_system_info()
                )
                result["software_info"] = await _optional(
                    "software_info", client.get_software_info()
                )
                result["current_input_or_app"] = await _optional(
                    "current_app", client.get_current_app()
                )
                result["inputs"] = await _optional("inputs", client.get_inputs())
        except TVError as exc:
            result["tv_error"] = str(exc)
            result["reachable"] = False
            return result
        result["reachable"] = True
        return result

    @mcp.tool(
        description=(
            "Read system settings via get_system_settings. "
            "If keys is null, use the readable default picture list. "
            "Optional pic_mode+tv_input reads picture$<input>.<mode>.2d.x. "
            "Batch key errors fall back to per-key reads "
            "(found / missing / rejected). "
            "category: picture, aiPicture, or other."
        )
    )
    async def get_settings(
        keys: list[str] | None = None,
        category: str = "picture",
        pic_mode: str | None = None,
        tv_input: str | None = None,
    ) -> dict[str, Any]:
        if category not in ("picture", "aiPicture", "other"):
            return {"error": f"invalid category {category!r}; use picture, aiPicture, or other"}
        if (pic_mode is None) ^ (tv_input is None):
            return {"error": "pic_mode and tv_input must be set together"}
        if pic_mode is not None:
            try:
                pic_mode = validate_picture_mode(pic_mode)
            except ValidationError as exc:
                return {"error": str(exc)}
        key_list = list(keys) if keys else list(DEFAULT_PICTURE_KEYS)
        try:
            async with connected_client(cfg) as client:
                found, missing, rejected = await read_settings(
                    client,
                    key_list,
                    category=category,
                    pic_mode=pic_mode,
                    tv_input=tv_input,
                )
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"TV command failed: {exc}"}
        result: dict[str, Any] = {
            "category": category,
            "requested": key_list,
            "found": found,
            "missing": missing,
            "rejected": rejected,
        }
        if pic_mode is not None and tv_input is not None:
            result["pic_mode"] = pic_mode
            result["tv_input"] = tv_input
        return result

    @mcp.tool(
        description=(
            "Write picture settings with allowlist validation. "
            "Always auto-backups current values of those keys before write. "
            "If pic_mode and tv_input are set, uses set_picture_settings; "
            "else set_settings(picture, settings). Returns before/after."
        )
    )
    async def set_picture_settings(
        settings: dict[str, Any],
        pic_mode: str | None = None,
        tv_input: str | None = None,
    ) -> dict[str, Any]:
        try:
            cleaned = validate_picture_settings(settings)
        except ValidationError as exc:
            return {"error": str(exc)}

        keys = list(cleaned.keys())
        try:
            async with connected_client(cfg) as client:
                before, _missing, _rej = await read_settings(
                    client,
                    keys,
                    category="picture",
                    pic_mode=pic_mode,
                    tv_input=tv_input,
                )
                backup_path = write_backup(
                    cfg.backups_dir,
                    before,
                    category="picture",
                    meta={"reason": "auto-before-set_picture_settings", "keys": keys},
                )
                if pic_mode is not None and tv_input is not None:
                    await client.set_picture_settings(cleaned, pic_mode, tv_input)
                else:
                    await client.set_settings("picture", cleaned)
                after, _, _ = await read_settings(
                    client,
                    keys,
                    category="picture",
                    pic_mode=pic_mode,
                    tv_input=tv_input,
                )
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": write_error_message(exc)}

        return {
            "ok": True,
            "backup": backup_path.name,
            "before": before,
            "after": after,
            "written": cleaned,
            "mode": (
                "set_picture_settings"
                if pic_mode is not None and tv_input is not None
                else "set_settings"
            ),
        }

    @mcp.tool(
        description=(
            "Set picture mode via client.set_picture_mode "
            "(not set_system_picture_mode). Validates pic_mode against known list."
        )
    )
    async def set_picture_mode(
        pic_mode: str,
        tv_input: str,
        dynamic_range: str = "sdr",
    ) -> dict[str, Any]:
        try:
            pic_mode = validate_picture_mode(pic_mode)
            dynamic_range = validate_dynamic_range(dynamic_range)
        except ValidationError as exc:
            return {"error": str(exc)}
        try:
            async with connected_client(cfg) as client:
                await client.set_picture_mode(pic_mode, tv_input, dynamic_range=dynamic_range)
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"TV command failed: {exc}"}
        return {
            "ok": True,
            "pic_mode": pic_mode,
            "tv_input": tv_input,
            "dynamic_range": dynamic_range,
        }

    @mcp.tool(description="Set current input (e.g. HDMI_1) via client.set_input.")
    async def set_input(input_id: str) -> dict[str, Any]:
        if not input_id or not isinstance(input_id, str):
            return {"error": "input_id is required"}
        try:
            async with connected_client(cfg) as client:
                await client.set_input(input_id)
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"TV command failed: {exc}"}
        return {"ok": True, "input_id": input_id}

    @mcp.tool(
        description=(
            "Send Wake-on-LAN magic packet to broadcast ports 9 and 7. "
            "Returns sent targets. Optional wait_seconds to poll reachability."
        )
    )
    async def power_on(wait_seconds: float = 0) -> dict[str, Any]:
        if not cfg.lgtv_mac:
            return {"error": "LGTV_MAC is not configured"}
        try:
            result = send_magic_packet(cfg.lgtv_mac, broadcast=cfg.lgtv_broadcast)
        except ValueError as exc:
            return {"error": str(exc)}

        if wait_seconds and wait_seconds > 0:
            import asyncio

            reachable = False
            deadline = asyncio.get_event_loop().time() + wait_seconds
            while asyncio.get_event_loop().time() < deadline:
                try:
                    async with connected_client(cfg) as _client:
                        reachable = True
                        break
                except TVError:
                    await asyncio.sleep(1.0)
            result["reachable_after_wait"] = reachable
        return result

    @mcp.tool(description="Power off the TV via client.power_off.")
    async def power_off() -> dict[str, Any]:
        try:
            async with connected_client(cfg) as client:
                await client.power_off()
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"TV command failed: {exc}"}
        return {"ok": True}

    @mcp.tool(
        description=(
            "Apply a named preset (ps5, switch2; aliases ps5_hdr, ps5_sdr). "
            "variants defaults to [sdr, hdr]. Each variant uses the preset "
            "tv_input and writes via set_picture_settings (luna per input/mode). "
            "Skips rejected/missing keys. One variant failure does not stop others. "
            "dry_run plans only. Includes manual_steps for non-API items."
        )
    )
    async def apply_preset(
        name: str,
        variants: list[str] | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        try:
            base_name, preset, variant_names = resolve_preset_variants(name, variants)
        except KeyError as exc:
            return {"error": str(exc)}

        tv_input = preset["tv_input"]
        result: dict[str, Any] = {
            "preset": base_name,
            "requested_as": name,
            "manual_steps": list(preset["manual_steps"]),
            "dry_run": dry_run,
        }

        try:
            async with connected_client(cfg) as client:
                for variant_name in variant_names:
                    variant = preset["variants"].get(variant_name)
                    if variant is None:
                        result[variant_name] = {
                            "error": (
                                f"unknown variant {variant_name!r}; "
                                f"available: {sorted(preset['variants'])}"
                            ),
                        }
                        continue

                    pic_mode = variant["pic_mode"]
                    settings = dict(variant["settings"])
                    keys = list(settings.keys())
                    entry: dict[str, Any] = {
                        "pic_mode": pic_mode,
                        "tv_input": tv_input,
                    }
                    try:
                        before, missing, rejected = await read_settings(
                            client,
                            keys,
                            category="picture",
                            pic_mode=pic_mode,
                            tv_input=tv_input,
                        )
                        skipped: dict[str, str] = {
                            **rejected,
                            **{k: "missing" for k in missing},
                        }
                        to_apply = {
                            k: v for k, v in settings.items() if k not in skipped
                        }
                        entry["before"] = before
                        entry["skipped"] = skipped
                        entry["to_apply"] = to_apply

                        if dry_run:
                            entry["after"] = None
                            result[variant_name] = entry
                            continue

                        if to_apply:
                            backup_path = write_backup(
                                cfg.backups_dir,
                                before,
                                category="picture",
                                meta={
                                    "reason": (
                                        f"auto-before-preset-{base_name}-{variant_name}"
                                    ),
                                    "keys": list(to_apply.keys()),
                                    "pic_mode": pic_mode,
                                    "tv_input": tv_input,
                                },
                            )
                            await client.set_picture_settings(
                                to_apply, pic_mode, tv_input
                            )
                            after, _, _ = await read_settings(
                                client,
                                list(to_apply.keys()),
                                category="picture",
                                pic_mode=pic_mode,
                                tv_input=tv_input,
                            )
                            entry["backup"] = backup_path.name
                            entry["after"] = after
                        else:
                            entry["after"] = before
                            entry["note"] = "no writable keys to apply"
                        result[variant_name] = entry
                    except Exception as exc:
                        entry["error"] = write_error_message(exc)
                        result[variant_name] = entry
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": write_error_message(exc)}

        result["ok"] = all(
            isinstance(result.get(v), dict) and "error" not in result[v]
            for v in variant_names
        )
        return result

    @mcp.tool(description="Save current picture settings to a named backup (or auto name).")
    async def backup_settings(name: str | None = None) -> dict[str, Any]:
        try:
            async with connected_client(cfg) as client:
                found, missing, rejected = await read_settings(
                    client, list(DEFAULT_PICTURE_KEYS), category="picture"
                )
                path = write_backup(
                    cfg.backups_dir,
                    found,
                    name=name,
                    category="picture",
                    meta={
                        "missing_at_backup": missing,
                        "rejected_at_backup": rejected,
                    },
                )
        except TVError as exc:
            return {"error": str(exc)}
        except BackupError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"backup failed: {exc}"}
        return {
            "ok": True,
            "backup": path.name,
            "keys": sorted(found.keys()),
            "missing": missing,
            "rejected": rejected,
        }

    @mcp.tool(description="Restore picture settings from a named backup file.")
    async def restore_settings(name: str) -> dict[str, Any]:
        try:
            data = read_backup(cfg.backups_dir, name)
            settings = data["settings"]
            if not isinstance(settings, dict) or not settings:
                return {"error": "backup has no settings"}
            subset = {k: v for k, v in settings.items() if k in ALLOWED_SETTING_KEYS}
            if not subset:
                return {"error": "backup has no allowlisted settings to restore"}
            cleaned = validate_picture_settings(subset)

            async with connected_client(cfg) as client:
                keys = list(cleaned.keys())
                before, _, _ = await read_settings(client, keys, category="picture")
                auto = write_backup(
                    cfg.backups_dir,
                    before,
                    category="picture",
                    meta={"reason": f"auto-before-restore-{name}"},
                )
                await client.set_settings("picture", cleaned)
                after, _, _ = await read_settings(client, keys, category="picture")
        except BackupError as exc:
            return {"error": str(exc)}
        except ValidationError as exc:
            return {"error": str(exc)}
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": write_error_message(exc)}
        return {
            "ok": True,
            "restored_from": name,
            "auto_backup": auto.name,
            "before": before,
            "after": after,
            "written": cleaned,
        }

    @mcp.tool(description="List available settings backups under DATA_DIR/backups.")
    async def list_backups() -> dict[str, Any]:
        return {"backups": backup_store.list_backups(cfg.backups_dir)}

    @mcp.tool(description="Show a floating message on the TV via client.send_message.")
    async def notify(message: str) -> dict[str, Any]:
        if not message:
            return {"error": "message is required"}
        try:
            async with connected_client(cfg) as client:
                await client.send_message(message)
        except TVError as exc:
            return {"error": str(exc)}
        except Exception as exc:
            return {"error": f"TV command failed: {exc}"}
        return {"ok": True}

    # Keep config on the instance for tests
    mcp._lgtv_config = cfg  # type: ignore[attr-defined]
    return mcp


def create_app(config: Config | None = None):
    """Return the Starlette ASGI app (streamable HTTP + /healthz)."""
    return create_mcp(config).streamable_http_app()
