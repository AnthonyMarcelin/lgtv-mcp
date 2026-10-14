# lgtv-mcp

MCP server (Python 3.12) to control an LG OLED C2 (webOS 22) over LAN.

Streamable HTTP transport (`/mcp`), required Bearer auth, public healthcheck at `/healthz`.

## Prerequisites

- TV and host on the same LAN
- TV IP (`LGTV_HOST`) and MAC for Wake-on-LAN (`LGTV_MAC`)
- Python 3.12+ (local) or Docker

## Tools

- `get_status` - power, input/app, software info, paired
- `get_settings` - readable default keys; optional `pic_mode`+`tv_input`; per-key fallback
- `set_picture_settings` - allowlisted writes, auto backup before write
- `set_picture_mode` / `set_input` / `power_on` / `power_off`
- `apply_preset` - `ps5` / `switch2` (aliases `ps5_hdr`, `ps5_sdr`); variants `sdr`/`hdr`
- `backup_settings` / `restore_settings` / `list_backups`
- `notify` - on-screen toast

Presets draw from RTINGS C2, HDTVTest, and nintendolife Switch 2 HDR notes. Game Optimizer / console options stay manual (`manual_steps`).

## Known limits

Live on LG OLED42C26LB (webOS 22, unsigned comp manifest):

- Refused picture keys (batch or single): `gameOptimization`, `gameGenre`, `inputOptimization`, `vrr`, `allm`, `motionProOLED`, `localDimming`, `hdrMode`, `lowLevelAdjustment`, `whiteBalanceColorTemperature`. `truMotionMode` has no value in game mode.
- `software_info` often returns 401 with the comp manifest; other status fields may still work.
- Settings writes work via `set_settings` / `set_picture_settings` (luna alert path) when pairing permissions allow.
- HDMI / `tv_input` ids vary per home (`ps5` defaults to `hdmi3`, `switch2` to `hdmi2`).

## Config

Copy `.env.example` to `.env` and set at least `MCP_BEARER_TOKEN` (long random secret).

| Variable | Default | Role |
|---|---|---|
| `LGTV_HOST` | `192.168.1.x` | TV IP |
| `LGTV_MAC` | (empty) | MAC for WOL |
| `LGTV_BROADCAST` | `192.168.1.255` | WOL broadcast |
| `LGTV_MANIFEST_PATH` | (packaged `manifest_comp.json`) | Override unsigned pairing manifest |
| `LGTV_EXTRA_PERMISSIONS` | (empty) | Comma list appended to manifest.permissions at pair (needs `--force` re-pair) |
| `MCP_BIND_HOST` | `0.0.0.0` | HTTP bind |
| `MCP_PORT` | `8765` | HTTP port |
| `MCP_BEARER_TOKEN` | (required) | Bearer token |
| `DATA_DIR` | `/data` | Pairing key + backups |

Pairing uses the unsigned `manifest_comp.json` (no signed certificate). Recent LG firmware blacklists the classic signed manifest.

Settings writes use the luna alert trick (`createAlert`/`closeAlert`). The comp manifest lacks `WRITE_NOTIFICATION_ALERT` and `WRITE_SETTINGS`. Constant `EXTRA_PERMISSIONS` in code is empty by default; set `LGTV_EXTRA_PERMISSIONS=WRITE_NOTIFICATION_ALERT,WRITE_SETTINGS` and re-pair with `--force` if picture/settings writes return insufficient permissions.

Never commit `.env` or the real token.

## Docker deploy

```bash
cp .env.example .env   # then edit
mkdir -p data
docker compose up -d --build
```

`network_mode: host` reaches the TV and sends WOL on the LAN.
Volume `./data:/data` keeps the pairing key and backups.

## Pairing

1. Power on the TV; same network as the host.
2. Run:

```bash
export $(grep -v '^#' .env | xargs)
python -m lgtv_mcp.pair
```

3. Accept the prompt on the TV (up to 90 s). Use `--force` to re-pair (required after changing `LGTV_EXTRA_PERMISSIONS`).
4. CLI prints redacted TV message summaries and `paired` (never the key).
5. Key is stored in `$DATA_DIR/.aiopylgtv.sqlite`.

## Security notes

- Bearer auth is mandatory for `/mcp`; `/healthz` is public and does not touch the TV.
- Pairing key and token are secrets: keep them in `DATA_DIR` / `.env`, not in git.
- LAN-only: do not expose this server to the public internet without additional controls.

## Local run / tests

```bash
python -m venv /tmp/lgtv-venv && source /tmp/lgtv-venv/bin/activate
pip install -e ".[dev]"
export $(grep -v '^#' .env | xargs)
python -m lgtv_mcp
pytest
```

Server: `http://$MCP_BIND_HOST:$MCP_PORT/mcp`.
Tests mock the TV (no real network).

## En bref

Serveur MCP pour piloter un LG OLED C2 en LAN (HTTP streamable, Bearer obligatoire).
Configurer `.env` (`LGTV_HOST=192.168.1.x`, `LGTV_MAC=AA:BB:CC:DD:EE:FF`, `MCP_BEARER_TOKEN`), appairer avec `python -m lgtv_mcp.pair`, deployer via `docker compose up -d --build`.
