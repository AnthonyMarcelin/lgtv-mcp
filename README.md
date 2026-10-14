# lgtv-mcp

MCP server (Python 3.12) to control an LG OLED C2 (webOS 22) over LAN.

Streamable HTTP transport (`/mcp`), required Bearer auth, public healthcheck at `/healthz`.

## Prerequisites

- TV and host on the same LAN
- TV IP (`LGTV_HOST`) and MAC for Wake-on-LAN (`LGTV_MAC`)
- Python 3.12+ (local) or Docker

## Tools

- `get_status` - power, input/app, software info, paired
- `get_settings` - read settings (broad default list; missing keys listed)
- `set_picture_settings` - allowlisted writes, auto backup before write
- `set_picture_mode` / `set_input` / `power_on` / `power_off`
- `apply_preset` - `ps5_hdr`, `ps5_sdr` (unknown TV keys ignored)
- `backup_settings` / `restore_settings` / `list_backups`
- `notify` - on-screen toast

Presets draw from RTINGS C2, HDTVTest, and Cura for the Gamer. Some Game Optimizer / PS5 options stay manual (returned as `manual_steps`).

## Config

Copy `.env.example` to `.env` and set at least `MCP_BEARER_TOKEN` (long random secret).

| Variable | Default | Role |
|---|---|---|
| `LGTV_HOST` | `192.168.1.x` | TV IP |
| `LGTV_MAC` | (empty) | MAC for WOL |
| `LGTV_BROADCAST` | `192.168.1.255` | WOL broadcast |
| `MCP_BIND_HOST` | `0.0.0.0` | HTTP bind |
| `MCP_PORT` | `8765` | HTTP port |
| `MCP_BEARER_TOKEN` | (required) | Bearer token |
| `DATA_DIR` | `/data` | Pairing key + backups |

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

3. Accept the prompt on the TV (up to 90 s). Use `--force` to re-pair.
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
