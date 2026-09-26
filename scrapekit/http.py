"""A polite HTTP client: retries, timeouts, rate limiting, robots.txt and an optional disk cache.

Every site module receives a `Fetcher` instead of calling `requests` directly.
That keeps the scraping logic testable (tests pass a fake fetcher that reads
local HTML files) and keeps the politeness rules in one place.
"""
from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

DEFAULT_UA = "scrapekit/1.0 (+https://github.com/delcapo-creator/scraping-pipeline)"


class BlockedByRobots(Exception):
    """Raised when robots.txt disallows a URL."""


class Fetcher:
    def __init__(
        self,
        delay: float = 0.5,
        timeout: float = 20.0,
        retries: int = 3,
        user_agent: str = DEFAULT_UA,
        cache_dir: str | Path | None = None,
        respect_robots: bool = True,
    ) -> None:
        self.delay = delay
        self.timeout = timeout
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.cache_dir = Path(cache_dir) if cache_dir else None
        if self.cache_dir:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

        retry = Retry(
            total=retries,
            backoff_factor=1.0,                      # 1s, 2s, 4s ...
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            respect_retry_after_header=True,
        )
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=16)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self._lock = threading.Lock()
        self._last_request = 0.0
        self._robots: dict[str, RobotFileParser] = {}
        self.stats = {"requests": 0, "cache_hits": 0}

    # ------------------------------------------------------------------ helpers
    def _wait_turn(self) -> None:
        """Global rate limit shared by all threads: at most one request per `delay` seconds."""
        with self._lock:
            now = time.monotonic()
            wait = self._last_request + self.delay - now
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        root = f"{parts.scheme}://{parts.netloc}"
        with self._lock:
            rp = self._robots.get(root)
        if rp is None:
            rp = RobotFileParser()
            try:
                r = self.session.get(root + "/robots.txt", timeout=self.timeout)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except requests.RequestException:
                rp.parse([])                         # unreachable robots.txt -> allow
            with self._lock:
                self._robots[root] = rp
        return rp.can_fetch(self.user_agent, url)

    def _cache_path(self, url: str) -> Path | None:
        if not self.cache_dir:
            return None
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest() + ".cache")

    # ------------------------------------------------------------------ public
    def get_text(self, url: str) -> str:
        cp = self._cache_path(url)
        if cp and cp.exists():
            self.stats["cache_hits"] += 1
            return cp.read_text(encoding="utf-8")
        if not self._allowed(url):
            raise BlockedByRobots(url)
        self._wait_turn()
        log.debug("GET %s", url)
        r = self.session.get(url, timeout=self.timeout)
        r.raise_for_status()
        r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
        self.stats["requests"] += 1
        if cp:
            cp.write_text(r.text, encoding="utf-8")
        return r.text

    def get_json(self, url: str):
        import json
        return json.loads(self.get_text(url))
