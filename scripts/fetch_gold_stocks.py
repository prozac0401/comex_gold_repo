import csv
import datetime as dt
import json
import os
import re
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Primary source from CME. This may return 403 for GitHub-hosted runners.
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

# Public fallbacks used when CME blocks automated downloads.
GOLDSILVER_GOLD_URL = "https://goldsilver.ai/metal-prices/comex-gold"
SILVEROFTRUTH_GOLD_URL = "https://www.silveroftruth.com/tools/comex-inventory"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

FALLBACK_FIELDS = [
    "date",
    "total_registered",
    "total_eligible",
    "total_pledged",
    "combined_total",
    "source",
]

FALLBACK_PATTERN = re.compile(
    r"Gold(?:<!-- -->)? Inventory.*?"
    r"Registered</span><span[^>]*>(?P<registered>[\d.]+)M oz</span>.*?"
    r"Eligible</span><span[^>]*>(?P<eligible>[\d.]+)M oz</span>.*?"
    r"Total</span><span[^>]*>(?P<total>[\d.]+)M oz</span>",
    re.IGNORECASE | re.DOTALL,
)

GOLDSILVER_SERIES_PATTERN = re.compile(
    r'"registeredData":(?P<registered>\[.*?\]),"eligibleData":(?P<eligible>\[.*?\])',
    re.DOTALL,
)


def make_session() -> requests.Session:
    """Create a retry-enabled HTTP session."""
    session = requests.Session()

    retries = Retry(
        total=3,
        backoff_factor=5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/129.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.cmegroup.com/",
            "Accept": "*/*",
        }
    )

    return session


def xls_path_for(day: dt.date) -> Path:
    return DATA_DIR / f"Gold_Stocks_{day:%Y%m%d}.xls"


def csv_path_for(day: dt.date) -> Path:
    return DATA_DIR / f"Gold_Stocks_{day:%Y%m%d}.csv"


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def date_from_ms(timestamp_ms: int) -> dt.date:
    return dt.datetime.fromtimestamp(timestamp_ms / 1000, dt.timezone.utc).date()


def date_from_row(row: dict) -> dt.date:
    return dt.date.fromisoformat(row["date"])


def parse_date_from_filename(path: Path) -> dt.date | None:
    match = re.search(r"(\d{8})", path.stem)
    if not match:
        return None
    return dt.datetime.strptime(match.group(1), "%Y%m%d").date()


def latest_xls_filename_date() -> dt.date | None:
    dates = [
        parse_date_from_filename(path)
        for path in DATA_DIR.glob("Gold_Stocks_*.xls")
    ]
    dates = [day for day in dates if day is not None]
    if not dates:
        return None
    return max(dates)


def print_response_preview(resp: requests.Response) -> None:
    try:
        text_preview = resp.text[:500]
    except Exception:
        text_preview = ""

    if text_preview:
        print("[ERROR] Response preview (first 500 chars):")
        print(text_preview)


def parse_million_ounces(value: str) -> float:
    return float(value) * 1_000_000


def normalize_embedded_json(html: str) -> str:
    return html.replace(r"\"", '"').replace(r"\/", "/")


def parse_goldsilver_rows(html: str) -> list[dict]:
    normalized = normalize_embedded_json(html)
    match = GOLDSILVER_SERIES_PATTERN.search(normalized)
    if not match:
        raise RuntimeError("Could not parse GoldSilver.ai inventory series")

    registered_data = json.loads(match.group("registered"))
    eligible_data = json.loads(match.group("eligible"))

    registered_by_ts = {
        int(point["x"]): float(point["y"])
        for point in registered_data
        if "x" in point and "y" in point
    }
    eligible_by_ts = {
        int(point["x"]): float(point["y"])
        for point in eligible_data
        if "x" in point and "y" in point
    }

    rows = []
    for timestamp_ms in sorted(registered_by_ts.keys() & eligible_by_ts.keys()):
        registered = registered_by_ts[timestamp_ms]
        eligible = eligible_by_ts[timestamp_ms]
        day = date_from_ms(timestamp_ms)
        rows.append(
            {
                "date": day.isoformat(),
                "total_registered": registered,
                "total_eligible": eligible,
                "total_pledged": "",
                "combined_total": registered + eligible,
                "source": GOLDSILVER_GOLD_URL,
            }
        )

    if not rows:
        raise RuntimeError("GoldSilver.ai inventory series was empty")

    return rows


def fetch_goldsilver_snapshots(session: requests.Session) -> list[dict]:
    print(f"[WARN] Falling back to structured source: {GOLDSILVER_GOLD_URL}")

    resp = session.get(
        GOLDSILVER_GOLD_URL,
        timeout=(10, 120),
        allow_redirects=True,
        headers={"Referer": "https://goldsilver.ai/"},
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"GoldSilver.ai HTTP error: {resp.status_code} {resp.reason}"
        )

    rows = parse_goldsilver_rows(resp.text)
    lower_bound = latest_xls_filename_date()
    if lower_bound is not None:
        rows = [row for row in rows if date_from_row(row) >= lower_bound]

    if not rows:
        raise RuntimeError("GoldSilver.ai had no rows newer than local CME files")

    latest = rows[-1]
    if latest["total_eligible"] == 0:
        print(
            "[WARN] Latest structured fallback reports zero eligible gold "
            f"for {latest['date']}"
        )

    return rows


def fetch_silveroftruth_snapshot(session: requests.Session, day: dt.date) -> dict:
    print(f"[WARN] Falling back to summary source: {SILVEROFTRUTH_GOLD_URL}")

    resp = session.get(
        SILVEROFTRUTH_GOLD_URL,
        timeout=(10, 120),
        allow_redirects=True,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Fallback HTTP error: {resp.status_code} {resp.reason}"
        )

    match = FALLBACK_PATTERN.search(resp.text)
    if not match:
        raise RuntimeError("Could not parse fallback gold inventory section")

    registered = parse_million_ounces(match.group("registered"))
    eligible = parse_million_ounces(match.group("eligible"))
    combined_total = parse_million_ounces(match.group("total"))

    return {
        "date": day.isoformat(),
        "total_registered": registered,
        "total_eligible": eligible,
        "total_pledged": "",
        "combined_total": combined_total,
        "source": SILVEROFTRUTH_GOLD_URL,
    }


def save_fallback_snapshot(row: dict) -> None:
    path = csv_path_for(date_from_row(row))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=FALLBACK_FIELDS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(row)


def save_fallback_snapshots(rows: list[dict]) -> None:
    for row in rows:
        save_fallback_snapshot(row)


def read_snapshot_source(path: Path) -> str | None:
    try:
        with path.open(newline="", encoding="utf-8") as f:
            row = next(csv.DictReader(f), None)
    except Exception:
        return None

    if row is None:
        return None
    return row.get("source")


def prune_stale_summary_snapshots(structured_dates: set[dt.date]) -> None:
    if not structured_dates:
        return

    earliest_structured_date = min(structured_dates)

    for path in DATA_DIR.glob("Gold_Stocks_*.csv"):
        day = parse_date_from_filename(path)
        if day is None or day < earliest_structured_date:
            continue
        if (
            day not in structured_dates
            and read_snapshot_source(path) == SILVEROFTRUTH_GOLD_URL
        ):
            path.unlink()
            print(f"[INFO] Removed stale summary fallback snapshot: {path.name}")


def download_gold_stocks() -> int:
    today = utc_today()
    out_xls_path = xls_path_for(today)
    out_csv_path = csv_path_for(today)

    if out_xls_path.exists():
        if out_csv_path.exists():
            out_csv_path.unlink()
        print(f"[INFO] File already exists for today: {out_xls_path}")
        return 0

    print(f"[INFO] Downloading Gold_Stocks for {today} ...")

    session = make_session()

    try:
        resp = session.get(
            GOLD_STOCK_URL,
            timeout=(10, 120),
            allow_redirects=True,
        )
    except Exception as exc:
        print(f"[ERROR] Request to CME failed: {exc!r}")
        resp = None

    if resp is not None and resp.status_code == 200 and resp.content:
        out_xls_path.write_bytes(resp.content)
        if out_csv_path.exists():
            out_csv_path.unlink()
        print(f"[INFO] Saved official CME file to {out_xls_path}")
        return 0

    if resp is not None:
        print(f"[ERROR] HTTP error from CME: {resp.status_code} {resp.reason}")
        print_response_preview(resp)

    try:
        snapshots = fetch_goldsilver_snapshots(session)
    except Exception as exc:
        print(f"[ERROR] Structured fallback fetch failed: {exc!r}")
    else:
        save_fallback_snapshots(snapshots)
        latest_date = date_from_row(snapshots[-1])
        structured_dates = {date_from_row(row) for row in snapshots}
        prune_stale_summary_snapshots(structured_dates)
        print(
            "[INFO] Saved structured fallback snapshots through "
            f"{latest_date.isoformat()}"
        )
        return 0

    if os.environ.get("ALLOW_SUMMARY_FALLBACK") != "1":
        print(
            "[ERROR] Summary fallback is disabled because it has no explicit "
            "source date. Set ALLOW_SUMMARY_FALLBACK=1 to force it."
        )
        return 1

    try:
        snapshot = fetch_silveroftruth_snapshot(session, today)
    except Exception as exc:
        print(f"[ERROR] Summary fallback fetch failed: {exc!r}")
        return 1

    save_fallback_snapshot(snapshot)
    print(f"[INFO] Saved summary fallback snapshot to {out_csv_path}")
    return 0


def main():
    code = download_gold_stocks()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
