"""HTTP helper. Prefer curl on this machine because system Python lacks CA certs."""

from __future__ import annotations

import subprocess
import urllib.error
import urllib.request

USER_AGENT = (
    "RAGPredictionGameProject/1.0 "
    "(local merchandising research; Wikimedia + Google Trends RSS)"
)


def http_get(url: str, *, timeout: int = 30) -> bytes:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return subprocess.check_output(
            ["curl", "-sL", "--max-time", str(timeout), "-A", USER_AGENT, url],
            timeout=timeout + 5,
        )


def http_get_json(url: str, *, timeout: int = 45) -> dict:
    import json

    raw = http_get(url, timeout=timeout)
    return json.loads(raw.decode("utf-8", "replace"))


def wikipedia_api(params: dict, *, timeout: int = 45) -> dict:
    from urllib.parse import urlencode

    query = urlencode(params)
    return http_get_json(f"https://en.wikipedia.org/w/api.php?{query}", timeout=timeout)


def wikidata_sparql(query: str, *, timeout: int = 60) -> list[dict]:
    from urllib.parse import quote

    url = "https://query.wikidata.org/sparql?format=json&query=" + quote(query)
    payload = http_get_json(url, timeout=timeout)
    return payload.get("results", {}).get("bindings", [])
