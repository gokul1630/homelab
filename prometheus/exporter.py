#!/usr/bin/env python3

import os
import time
import logging
import json
import time
import argparse
import requests
import subprocess
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("homelab_exporter")


class ImmichCollector:
    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"x-api-key": api_key})

    def _get(self, path: str) -> dict | None:
        try:
            r = self.session.get(
                f"{self.base_url}{path}", timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("Immich request failed for %s: %s", path, exc)
            return None

    def collect(self):
        prefix = "immich"

        up = GaugeMetricFamily(
            f"{prefix}_up", "1 if Immich is reachable, 0 otherwise")
        server_info = self._get("/api/server/about")
        if server_info is None:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up

        # Server statistics
        stats = self._get("/api/server/statistics")
        if stats:
            photos = GaugeMetricFamily(
                f"{prefix}_photos_total", "Total number of photos")
            photos.add_metric([], stats.get("photos", 0))
            yield photos

            videos = GaugeMetricFamily(
                f"{prefix}_videos_total", "Total number of videos")
            videos.add_metric([], stats.get("videos", 0))
            yield videos

        # User statistics
        users = self._get("/api/users")
        if users is not None:
            user_count = GaugeMetricFamily(
                f"{prefix}_users_total", "Total number of users")
            user_count.add_metric([], len(users))
            yield user_count

            active_users = GaugeMetricFamily(
                f"{prefix}_active_users_total", "Number of active users"
            )
            active_users.add_metric(
                [], sum(1 for u in users if not u.get("deletedAt"))
            )
            yield active_users

        # Per-user asset stats
        user_photos = GaugeMetricFamily(
            f"{prefix}_user_photos_total",
            "Photos per user",
            labels=["user", "uid"],
        )
        user_videos = GaugeMetricFamily(
            f"{prefix}_user_videos_total",
            "Videos per user",
            labels=["user", "uid"],
        )
        user_total_usage_bytes = GaugeMetricFamily(
            f"{prefix}_user_total_usage_bytes",
            "User total usage of bytes",
            labels=["user", "uid"],
        )

        if stats:
            for user in stats.get('usageByUser', []):
                if user:
                    uid = user.get("userId", "")
                    name = user.get("userName", uid)
                    user_photos.add_metric(
                        [name, uid], user.get("photos", 0))
                    user_videos.add_metric(
                        [name, uid], user.get("videos", 0))
                    user_total_usage_bytes.add_metric(
                        [name, uid], user.get("usage", 0))
        yield user_photos
        yield user_videos
        yield user_total_usage_bytes

        # Jobs / Queue health
        jobs = self._get("/api/jobs")
        if jobs:
            job_active = GaugeMetricFamily(
                f"{prefix}_job_active",
                "Number of active jobs in queue",
                labels=["queue"],
            )
            job_waiting = GaugeMetricFamily(
                f"{prefix}_job_waiting",
                "Number of waiting jobs in queue",
                labels=["queue"],
            )
            job_paused = GaugeMetricFamily(
                f"{prefix}_job_paused",
                "1 if the queue is paused",
                labels=["queue"],
            )
            for queue_name, info in jobs.items():
                counts = info.get("jobCounts", {})
                job_active.add_metric([queue_name], counts.get("active", 0))
                job_waiting.add_metric(
                    [queue_name],
                    counts.get("waiting", 0) + counts.get("paused", 0),
                )
                job_paused.add_metric([queue_name], 1 if info.get(
                    "queueStatus", {}).get("isPaused") else 0)
            yield job_active
            yield job_waiting
            yield job_paused
# ---------------------------------------------------------------------------
# Navidrome Collector
# ---------------------------------------------------------------------------


class NavidromeCollector:
    """Collects metrics from the Navidrome music server (OpenSubsonic API)."""

    def __init__(self, base_url: str, username: str, password: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.timeout = timeout
        self.client = "homelab-exporter"
        self.version = "1.16.1"

    def _params(self, extra: dict | None = None) -> dict:
        import hashlib
        import secrets
        salt = secrets.token_hex(6)
        token = hashlib.md5((self.password + salt).encode()).hexdigest()
        p = {
            "u": self.username,
            "t": token,
            "s": salt,
            "v": self.version,
            "c": self.client,
            "f": "json",
        }
        if extra:
            p.update(extra)
        return p

    def _get(self, endpoint: str, extra: dict | None = None) -> dict | None:
        try:
            r = requests.get(
                f"{self.base_url}/rest/{endpoint}",
                params=self._params(extra),
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            subsonic = data.get("subsonic-response", {})
            if subsonic.get("status") != "ok":
                log.warning("Navidrome error response from %s: %s",
                            endpoint, subsonic.get("error"))
                return None
            return subsonic
        except Exception as exc:
            log.warning("Navidrome request failed for %s: %s", endpoint, exc)
            return None

    def collect(self):
        prefix = "navidrome"

        ping = self._get("ping")
        up = GaugeMetricFamily(
            f"{prefix}_up", "1 if Navidrome is reachable, 0 otherwise")
        if ping is None:
            up.add_metric([], 0)
            yield up
            return
        up.add_metric([], 1)
        yield up

        # Library stats
        stats = self._get("getArtists")
        if stats:
            artists = stats.get("artists", {})
            artist_count = GaugeMetricFamily(
                f"{prefix}_artists_total", "Total number of artists")
            artist_count.add_metric([], artists.get(
                "ignoredArticles") and len(artists.get("index", [])) or 0)
            # Actually count from index
            total = sum(len(idx.get("artist", []))
                        for idx in artists.get("index", []))
            artist_count.add_metric([], total)
            yield artist_count

        album_data = self._get("getAlbumList2", {"type": "newest", "size": 1})
        # Use getNowPlaying for active streams
        now_playing = self._get("getNowPlaying")
        if now_playing is not None:
            playing = now_playing.get("nowPlaying", {}).get("entry", [])
            if isinstance(playing, dict):
                playing = [playing]
            streams = GaugeMetricFamily(
                f"{prefix}_active_streams_total", "Number of currently active streams"
            )
            streams.add_metric([], len(playing))
            yield streams

        # Scan status
        scan = self._get("getScanStatus")
        if scan:
            scan_status = scan.get("scanStatus", {})
            scanning = GaugeMetricFamily(
                f"{prefix}_scanning", "1 if a library scan is in progress"
            )
            scanning.add_metric([], 1 if scan_status.get("scanning") else 0)
            yield scanning

            count = GaugeMetricFamily(
                f"{prefix}_scan_count_total", "Number of items scanned in last/current scan"
            )
            count.add_metric([], scan_status.get("count", 0))
            yield count

        # Users
        users_resp = self._get("getUsers")
        if users_resp:
            raw_users = users_resp.get("users", {}).get("user", [])
            if isinstance(raw_users, dict):
                raw_users = [raw_users]
            user_count = GaugeMetricFamily(
                f"{prefix}_users_total", "Total Navidrome users")
            user_count.add_metric([], len(raw_users))
            yield user_count

            admin_count = GaugeMetricFamily(
                f"{prefix}_admin_users_total", "Number of admin users")
            admin_count.add_metric(
                [], sum(1 for u in raw_users if u.get("adminRole")))
            yield admin_count

        # Internet radio stations
        radios = self._get("getInternetRadioStations")
        if radios:
            stations = radios.get("internetRadioStations", {}).get(
                "internetRadioStation", [])
            if isinstance(stations, dict):
                stations = [stations]
            radio_count = GaugeMetricFamily(
                f"{prefix}_radio_stations_total", "Number of internet radio stations configured"
            )
            radio_count.add_metric([], len(stations))
            yield radio_count

        # Playlists
        playlists_resp = self._get("getPlaylists")
        if playlists_resp:
            plists = playlists_resp.get("playlists", {}).get("playlist", [])
            if isinstance(plists, dict):
                plists = [plists]
            playlist_count = GaugeMetricFamily(
                f"{prefix}_playlists_total", "Total number of playlists"
            )
            playlist_count.add_metric([], len(plists))
            yield playlist_count

            total_songs = GaugeMetricFamily(
                f"{prefix}_playlist_songs_total", "Total songs across all playlists"
            )
            total_songs.add_metric(
                [], sum(p.get("songCount", 0) for p in plists))
            yield total_songs

            total_duration = GaugeMetricFamily(
                f"{prefix}_playlist_duration_seconds_total",
                "Total duration of all playlist songs in seconds",
            )
            total_duration.add_metric(
                [], sum(p.get("duration", 0) for p in plists))
            yield total_duration


class ZpoolCollector:
    STATE_MAP = {
        "ONLINE": 1,
        "DEGRADED": 2,
        "FAULTED": 3,
        "OFFLINE": 4,
        "UNAVAIL": 5,
        "REMOVED": 6,
        "SUSPENDED": 7,
    }

    def __init__(self, pool_name=None):
        self.pool_name = pool_name

    def get_zpool_status(self):
        cmd = [
            "chroot",
            "/host",
            "zpool",
            "status",
            "-jp"]

        if self.pool_name:
            cmd.append(self.pool_name)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)

        except Exception as exc:
            log.warning("zpool collection failed: %s", exc)
            return None

    def _walk_vdev(self, pool_name, vdev, metrics):
        labels = [
            pool_name,
            vdev.get("name", "unknown"),
            vdev.get("vdev_type", "unknown"),
        ]

        state = vdev.get("state", "UNKNOWN")

        metrics["state"].add_metric(
            labels,
            self.STATE_MAP.get(state, 0),
        )

        metrics["read_errors"].add_metric(
            labels,
            int(vdev.get("read_errors", 0)),
        )

        metrics["write_errors"].add_metric(
            labels,
            int(vdev.get("write_errors", 0)),
        )

        metrics["checksum_errors"].add_metric(
            labels,
            int(vdev.get("checksum_errors", 0)),
        )

        metrics["slow_ios"].add_metric(
            labels,
            int(vdev.get("slow_ios", 0)),
        )

        alloc = (
            vdev.get("alloc_space")
            or vdev.get("allocated")
            or 0
        )

        total = (
            vdev.get("total_space")
            or vdev.get("rep_dev_size")
            or 0
        )

        physical = (
            vdev.get("phys_space")
            or 0
        )

        metrics["allocated_bytes"].add_metric(
            labels,
            alloc
        )

        metrics["total_bytes"].add_metric(
            labels,
            total
        )

        metrics["physical_bytes"].add_metric(
            labels,
            physical
        )

        for child in vdev.get("vdevs", {}).values():
            self._walk_vdev(pool_name, child, metrics)

    def collect(self):
        data = self.get_zpool_status()

        zpool_up = GaugeMetricFamily(
            "zpool_up",
            "1 if zpool command succeeded"
        )

        if not data:
            zpool_up.add_metric([], 0)
            yield zpool_up
            return

        zpool_up.add_metric([], 1)
        yield zpool_up

        pool_state = GaugeMetricFamily(
            "zpool_state",
            "Pool state",
            labels=["pool"]
        )

        pool_txg = GaugeMetricFamily(
            "zpool_txg",
            "Current TXG",
            labels=["pool"]
        )

        pool_error_count = GaugeMetricFamily(
            "zpool_error_count",
            "Pool error count",
            labels=["pool"]
        )

        scan_errors = GaugeMetricFamily(
            "zpool_scan_errors",
            "Scan errors",
            labels=["pool"]
        )

        scan_examined_bytes = GaugeMetricFamily(
            "zpool_scan_examined_bytes",
            "Scan examined bytes",
            labels=["pool"]
        )

        scan_processed_bytes = GaugeMetricFamily(
            "zpool_scan_processed_bytes",
            "Scan processed bytes",
            labels=["pool"]
        )

        scan_issued_bytes = GaugeMetricFamily(
            "zpool_scan_issued_bytes",
            "Scan issued bytes",
            labels=["pool"]
        )

        metrics = {
            "state": GaugeMetricFamily(
                "zpool_vdev_state",
                "VDEV state",
                labels=["pool", "vdev", "type"]
            ),
            "read_errors": GaugeMetricFamily(
                "zpool_vdev_read_errors",
                "Read errors",
                labels=["pool", "vdev", "type"]
            ),
            "write_errors": GaugeMetricFamily(
                "zpool_vdev_write_errors",
                "Write errors",
                labels=["pool", "vdev", "type"]
            ),
            "checksum_errors": GaugeMetricFamily(
                "zpool_vdev_checksum_errors",
                "Checksum errors",
                labels=["pool", "vdev", "type"]
            ),
            "slow_ios": GaugeMetricFamily(
                "zpool_vdev_slow_ios",
                "Slow IO count",
                labels=["pool", "vdev", "type"]
            ),
            "allocated_bytes": GaugeMetricFamily(
                "zpool_vdev_allocated_bytes",
                "Allocated bytes",
                labels=["pool", "vdev", "type"]
            ),
            "total_bytes": GaugeMetricFamily(
                "zpool_vdev_total_bytes",
                "Total bytes",
                labels=["pool", "vdev", "type"]
            ),
            "physical_bytes": GaugeMetricFamily(
                "zpool_vdev_physical_bytes",
                "Physical bytes",
                labels=["pool", "vdev", "type"]
            ),
        }

        for pool_name, pool in data.get("pools", {}).items():

            state = pool.get("state", "UNKNOWN")

            pool_state.add_metric(
                [pool_name],
                self.STATE_MAP.get(state, 0)
            )

            pool_error_count.add_metric(
                [pool_name],
                int(pool.get("error_count", 0))
            )

            scan = pool.get("scan_stats", {})

            scan_errors.add_metric(
                [pool_name],
                int(scan.get("errors", 0))
            )

            scan_examined_bytes.add_metric(
                [pool_name],
                scan.get("examined")
            )

            scan_processed_bytes.add_metric(
                [pool_name],
                scan.get("processed")
            )

            scan_issued_bytes.add_metric(
                [pool_name],
                scan.get("issued")
            )

            root_vdev = pool.get("vdevs", {}).get(pool_name)

            if root_vdev:
                self._walk_vdev(
                    pool_name,
                    root_vdev,
                    metrics,
                )

        yield pool_state
        yield pool_error_count
        yield scan_errors
        yield scan_examined_bytes
        yield scan_processed_bytes
        yield scan_issued_bytes

        for metric in metrics.values():
            yield metric
# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def parse_args():
    p = argparse.ArgumentParser(description="Homelab Prometheus Exporter")
    p.add_argument("--port", type=int,
                   default=int(os.getenv("EXPORTER_PORT", "9877")))
    p.add_argument("--scrape-interval", type=int, default=int(os.getenv("SCRAPE_INTERVAL", "60")),
                   help="Seconds between metric refreshes (unused in pull model, but kept for logging)")
    # Immich
    p.add_argument("--immich-url", default=os.getenv("IMMICH_URL", ""))
    p.add_argument("--immich-api-key", default=os.getenv("IMMICH_API_KEY", ""))
    # Navidrome
    p.add_argument("--navidrome-url", default=os.getenv("NAVIDROME_URL", ""))
    p.add_argument("--navidrome-user", default=os.getenv("NAVIDROME_USER", ""))
    p.add_argument("--navidrome-password",
                   default=os.getenv("NAVIDROME_PASSWORD", ""))
    # zpool status
    p.add_argument("--zpool_name", default=os.getenv("zpool_name", ""))
    return p.parse_args()


def main():
    args = parse_args()

    collectors = []

    if args.immich_url and args.immich_api_key:
        log.info("Registering Immich collector → %s", args.immich_url)
        collectors.append(ImmichCollector(
            args.immich_url, args.immich_api_key))
    else:
        log.warning(
            "Immich not configured (need --immich-url and --immich-api-key)")

    if args.navidrome_url and args.navidrome_user:
        log.info("Registering Navidrome collector → %s", args.navidrome_url)
        collectors.append(NavidromeCollector(
            args.navidrome_url, args.navidrome_user, args.navidrome_password
        ))
    else:
        log.warning(
            "Navidrome not configured (need --navidrome-url, --navidrome-user, --navidrome-password)")

    collectors.append(ZpoolCollector(
        pool_name=args.zpool_name
    ))

    for c in collectors:
        REGISTRY.register(c)

    log.info("Starting exporter on :%d/metrics", args.port)
    start_http_server(args.port)

    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
