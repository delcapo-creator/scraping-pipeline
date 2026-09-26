"""Fetcher tests against a local HTTP server (no internet needed)."""
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from scrapekit.http import BlockedByRobots, Fetcher

HITS = {"flaky": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            body, code = b"User-agent: *\nDisallow: /private/\n", 200
        elif self.path == "/flaky":
            HITS["flaky"] += 1
            body, code = (b"busy", 503) if HITS["flaky"] < 3 else ("ok é".encode(), 200)
        elif self.path.startswith("/private/"):
            body, code = b"secret", 200
        else:
            body, code = f"page {self.path}".encode(), 200
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


def test_retries_on_503(server):
    f = Fetcher(delay=0, retries=3)
    f.session.adapters["http://"].max_retries.backoff_factor = 0
    assert f.get_text(server + "/flaky") == "ok é"
    assert HITS["flaky"] == 3


def test_robots_txt_is_respected(server):
    f = Fetcher(delay=0)
    with pytest.raises(BlockedByRobots):
        f.get_text(server + "/private/data")
    assert Fetcher(delay=0, respect_robots=False).get_text(server + "/private/data") == "secret"


def test_rate_limit(server):
    f = Fetcher(delay=0.2)
    t0 = time.monotonic()
    for i in range(4):
        f.get_text(f"{server}/p{i}")
    assert time.monotonic() - t0 >= 0.6          # 3 waits of 0.2s after the first request


def test_cache(server, tmp_path):
    f = Fetcher(delay=0, cache_dir=tmp_path)
    a = f.get_text(server + "/cached")
    b = f.get_text(server + "/cached")
    assert a == b == "page /cached"
    assert f.stats == {"requests": 1, "cache_hits": 1}
