# lgtv-mcp

Serveur MCP (Python 3.12) pour piloter un LG OLED C2 (webOS 22) en LAN.

Transport HTTP streamable (`/mcp`), authentification Bearer obligatoire, healthcheck public sur `/healthz`.

## Prérequis

- TV et machine hôte sur le même LAN
- IP de la TV (`LGTV_HOST`) et MAC pour le Wake-on-LAN (`LGTV_MAC`)
- Python 3.12+ (local) ou Docker

## Configuration

Copier `.env.example` vers `.env` et renseigner au minimum `MCP_BEARER_TOKEN` (long secret aléatoire).

| Variable | Défaut | Rôle |
|---|---|---|
| `LGTV_HOST` | `192.168.1.137` | IP de la TV |
| `LGTV_MAC` | (vide) | MAC pour WOL |
| `LGTV_BROADCAST` | `192.168.1.255` | Broadcast WOL |
| `MCP_BIND_HOST` | `0.0.0.0` | Bind HTTP |
| `MCP_PORT` | `8765` | Port HTTP |
| `MCP_BEARER_TOKEN` | (requis) | Token Bearer |
| `DATA_DIR` | `/data` | Clé de pairing + backups |

Ne jamais committer `.env` ni le token.

## Appairage

1. Allumer la TV, même réseau que l'hôte.
2. Lancer :

```bash
export $(grep -v '^#' .env | xargs)
python -m lgtv_mcp.pair
```

3. Accepter la demande d'appairage sur la TV (délai 60 s).
4. Le CLI affiche uniquement `paired` (jamais la clé).
5. La clé est stockée dans `$DATA_DIR/.aiopylgtv.sqlite`.

## Lancement local

```bash
python -m venv /tmp/lgtv-venv && source /tmp/lgtv-venv/bin/activate
pip install -e ".[dev]"
export $(grep -v '^#' .env | xargs)
python -m lgtv_mcp
```

Le serveur écoute sur `http://$MCP_BIND_HOST:$MCP_PORT/mcp`.
Les outils MCP exigent `Authorization: Bearer <MCP_BEARER_TOKEN>`.
`GET /healthz` renvoie `{"ok":true}` sans auth et sans accès TV.

## Docker

```bash
cp .env.example .env   # puis éditer
mkdir -p data
docker compose up -d --build
```

`network_mode: host` pour joindre la TV et envoyer le WOL sur le LAN.
Volume `./data:/data` pour conserver la clé et les backups.

## Outils MCP

- `get_status` : alimentation, entrée/app, infos logicielles, paired
- `get_settings` : lecture settings (liste large par défaut, clés manquantes listées)
- `set_picture_settings` : écriture allowlistée, backup auto avant écriture
- `set_picture_mode` / `set_input` / `power_on` / `power_off`
- `apply_preset` : `ps5_hdr`, `ps5_sdr` (ignore les clés inconnues de la TV)
- `backup_settings` / `restore_settings` / `list_backups`
- `notify` : message flottant

Presets basés sur RTINGS C2, HDTVTest, et Cura for the Gamer. Certains réglages Game Optimizer / PS5 restent manuels (renvoyés dans `manual_steps`).

## Tests

```bash
pip install -e ".[dev]"
pytest
```

Les tests mockent la TV (aucun accès réseau réel).
