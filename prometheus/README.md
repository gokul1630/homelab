# Homelab Prometheus Exporter

Exports metrics from **Immich**, **Navidrome**, and **Docmost** for Prometheus scraping.

## Metrics

### Immich (`immich_*`)
| Metric | Description |
|---|---|
| `immich_up` | 1 if reachable |
| `immich_photos_total` | Total photos in library |
| `immich_videos_total` | Total videos in library |
| `immich_disk_usage_bytes` | Total asset storage used |
| `immich_disk_available_bytes` | Available disk space |
| `immich_disk_size_bytes` | Total disk size |
| `immich_disk_use_percent` | Disk usage percentage |
| `immich_users_total` | Total users |
| `immich_active_users_total` | Non-deleted users |
| `immich_user_photos_total{user,email}` | Photos per user |
| `immich_user_videos_total{user,email}` | Videos per user |
| `immich_user_disk_usage_bytes{user,email}` | Disk usage per user |
| `immich_job_active{queue}` | Active jobs per queue |
| `immich_job_waiting{queue}` | Waiting jobs per queue |
| `immich_job_paused{queue}` | 1 if queue is paused |

### Navidrome (`navidrome_*`)
| Metric | Description |
|---|---|
| `navidrome_up` | 1 if reachable |
| `navidrome_artists_total` | Total artists |
| `navidrome_active_streams_total` | Currently active streams |
| `navidrome_scanning` | 1 if scan in progress |
| `navidrome_scan_count_total` | Items scanned |
| `navidrome_users_total` | Total users |
| `navidrome_admin_users_total` | Admin users |
| `navidrome_radio_stations_total` | Internet radio stations |
| `navidrome_playlists_total` | Total playlists |
| `navidrome_playlist_songs_total` | Songs across all playlists |
| `navidrome_playlist_duration_seconds_total` | Total playlist duration |

### Docmost (`docmost_*`)
| Metric | Description |
|---|---|
| `docmost_up` | 1 if reachable |
| `docmost_workspaces_total` | Total workspaces |
| `docmost_spaces_total` | Total spaces |
| `docmost_pages_total` | Total pages/documents |
| `docmost_members_total` | Total workspace members |
| `docmost_members_by_role_total{role}` | Members grouped by role |
| `docmost_groups_total` | Total groups |
| `docmost_attachments_total` | Total attachments |
| `docmost_attachments_size_bytes` | Total attachment storage |

## Quick Start

### Docker Compose

```bash
# Copy and edit the compose file
cp docker-compose.yml docker-compose.override.yml
# Fill in your URLs and credentials, then:
docker compose up -d
```

### Bare Metal / venv

```bash
pip install -r requirements.txt

export IMMICH_URL=http://immich:2283
export IMMICH_API_KEY=your-key

export NAVIDROME_URL=http://navidrome:4533
export NAVIDROME_USER=admin
export NAVIDROME_PASSWORD=secret

export DOCMOST_URL=http://docmost:3000
export DOCMOST_EMAIL=admin@example.com
export DOCMOST_PASSWORD=secret

python exporter.py
```

Metrics will be available at `http://localhost:9877/metrics`.

### Prometheus Config

Paste the contents of `prometheus-scrape-config.yml` into your `prometheus.yml`.

## Getting Credentials

**Immich API key** — Immich web UI → Account Settings → API Keys → New API Key

**Navidrome** — Use any Navidrome admin account (token auth is derived automatically from username + password using the OpenSubsonic token scheme)

**Docmost** — Use any admin account email/password. The exporter logs in automatically and refreshes the token on expiry.

## Notes

- The exporter uses Prometheus' **pull** model — Prometheus scrapes `/metrics` on demand; no polling loop runs inside the exporter.
- All collectors are **fault-isolated**: if one service is down, the others still export normally. A `*_up` gauge will be set to 0 for unreachable services.
- Docmost's API endpoints are inferred from common REST patterns. If your version uses different paths, check the Docmost API docs and update the `_get()` call paths in `DocmostCollector`.
