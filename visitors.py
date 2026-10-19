#!/usr/bin/env python3
"""
Visitor numbers for the admin tool, read from Cloudflare Web Analytics.

The website itself carries only Cloudflare's cookieless counting script. The
numbers are read back here, on this machine, with a read-only API token that
the artist pastes into Manage artworks. The token is kept in
data/cloudflare.json, which git ignores: it must never reach the public
repository or the published site.
"""
from __future__ import annotations

import datetime
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "data" / "cloudflare.json"
API_URL = "https://api.cloudflare.com/client/v4/graphql"
SITE_HOST = "www.roniluokkamaki.com"
PERIODS = (7, 30, 90)  # days the Visitors page can show
CACHE_SECONDS = 600

_cache: dict[int, tuple[float, dict]] = {}


class VisitorsError(Exception):
    pass


# ----------------------------------------------------------------- settings

def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(account_id: str, api_token: str) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(
        json.dumps({"account_id": account_id, "api_token": api_token}),
        encoding="utf-8")
    _cache.clear()


def is_configured() -> bool:
    s = load_settings()
    return bool(s.get("account_id") and s.get("api_token"))


# -------------------------------------------------------------------- query

# One request, several groupings of the same page loads. `count` is page
# views; `sum.visits` counts a visit once however many pages it opened.
QUERY = """
query Visitors($account: string, $filter: AccountRumPageloadEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: {accountTag: $account}) {
      total: rumPageloadEventsAdaptiveGroups(limit: 1, filter: $filter) {
        count
        sum { visits }
      }
      days: rumPageloadEventsAdaptiveGroups(limit: 200, filter: $filter, orderBy: [date_ASC]) {
        count
        sum { visits }
        dimensions { date }
      }
      pages: rumPageloadEventsAdaptiveGroups(limit: 15, filter: $filter, orderBy: [count_DESC]) {
        count
        dimensions { requestPath }
      }
      referrers: rumPageloadEventsAdaptiveGroups(limit: 10, filter: $filter, orderBy: [count_DESC]) {
        count
        dimensions { refererHost }
      }
      countries: rumPageloadEventsAdaptiveGroups(limit: 10, filter: $filter, orderBy: [count_DESC]) {
        count
        dimensions { countryName }
      }
      devices: rumPageloadEventsAdaptiveGroups(limit: 5, filter: $filter, orderBy: [count_DESC]) {
        count
        dimensions { deviceType }
      }
    }
  }
}
"""


def _post(settings: dict, variables: dict) -> dict:
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"query": QUERY, "variables": variables}).encode("utf-8"),
        headers={"Authorization": f"Bearer {settings['api_token']}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise VisitorsError("Cloudflare refused the API token. Check that it has "
                                "Account Analytics: Read, then save it again.") from None
        raise VisitorsError(f"Cloudflare answered with an error ({e.code}).") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise VisitorsError(f"Could not reach Cloudflare: {e}") from None

    if body.get("errors"):
        msgs = "; ".join(err.get("message", "?") for err in body["errors"])
        raise VisitorsError(f"Cloudflare could not answer: {msgs}")
    accounts = (body.get("data") or {}).get("viewer", {}).get("accounts") or []
    if not accounts:
        raise VisitorsError("No Cloudflare account matches that Account ID.")
    return accounts[0]


def fetch(days: int) -> dict:
    """Visitor numbers for the last `days` days, newest data Cloudflare has."""
    if days not in PERIODS:
        days = PERIODS[1]
    hit = _cache.get(days)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]

    settings = load_settings()
    if not (settings.get("account_id") and settings.get("api_token")):
        raise VisitorsError("Cloudflare is not set up yet.")

    today = datetime.date.today()
    start = today - datetime.timedelta(days=days - 1)
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    variables = {
        "account": settings["account_id"],
        "filter": {"AND": [
            {"datetime_geq": f"{start.isoformat()}T00:00:00Z",
             "datetime_leq": now.isoformat().replace("+00:00", "Z")},
            {"requestHost": SITE_HOST},
        ]},
    }
    raw = _post(settings, variables)

    total = raw.get("total") or [{}]
    by_day = {g["dimensions"]["date"]: g for g in raw.get("days") or []}
    # every day in the period, so quiet days show as zero rather than vanish
    series = []
    for i in range(days):
        d = (start + datetime.timedelta(days=i)).isoformat()
        g = by_day.get(d, {})
        series.append({"date": d, "views": g.get("count", 0),
                       "visits": (g.get("sum") or {}).get("visits", 0)})

    def rows(key: str, dim: str, blank: str) -> list[dict]:
        return [{"label": g["dimensions"][dim] or blank, "views": g["count"]}
                for g in raw.get(key) or []]

    result = {
        "days": days,
        "views": total[0].get("count", 0),
        "visits": (total[0].get("sum") or {}).get("visits", 0),
        "series": series,
        "peak": max((s["visits"] for s in series), default=0),
        "pages": rows("pages", "requestPath", "/"),
        "referrers": rows("referrers", "refererHost", "direct / unknown"),
        "countries": rows("countries", "countryName", "unknown"),
        "devices": rows("devices", "deviceType", "unknown"),
        "home_views": sum(g["count"] for g in raw.get("pages") or []
                          if g["dimensions"]["requestPath"] in ("/", "/index.html",
                                                                 "/fi/", "/fi/index.html")),
    }
    _cache[days] = (time.time(), result)
    return result
