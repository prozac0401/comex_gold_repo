import csv
import datetime as dt
import re
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Primary source from CME. This may return 403 for GitHub-hosted runners.
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

# Public fallback that exposes the latest COMEX gold inventory totals in HTML.
FALLBACK_GOLD_URL = "https://www.silveroftruth.com/tools/comex-inventory"

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


def fetch_fallback_snapshot(session: requests.Session, day: dt.date) -> dict:
    print(f"[WARN] Falling back to {FALLBACK_GOLD_URL}")

    resp = session.get(
        FALLBACK_GOLD_URL,
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
        "source": FALLBACK_GOLD_URL,
    }


def save_fallback_snapshot(path: Path, row: dict) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FALLBACK_FIELDS)
        writer.writeheader()
        writer.writerow(row)


def download_gold_stocks() -> int:
    today = dt.date.today()
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
        snapshot = fetch_fallback_snapshot(session, today)
    except Exception as exc:
        print(f"[ERROR] Fallback fetch failed: {exc!r}")
        return 1

    save_fallback_snapshot(out_csv_path, snapshot)
    print(f"[INFO] Saved fallback snapshot to {out_csv_path}")
    return 0


def main():
    code = download_gold_stocks()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
