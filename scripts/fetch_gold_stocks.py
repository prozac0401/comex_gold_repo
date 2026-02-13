import datetime as dt
import os
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import ProxyError
from urllib3.util.retry import Retry

# CME Gold stocks 엑셀 파일 주소
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 네트워크 모드:
# - auto  : 기본(환경 프록시 사용) 시도 후 ProxyError 일 때만 direct 재시도
# - proxy : 환경 프록시만 사용
# - direct: 환경 프록시를 무시하고 직접 연결만 사용
NETWORK_MODE = os.getenv("GOLD_STOCK_NETWORK_MODE", "auto").strip().lower()
VALID_NETWORK_MODES = {"auto", "proxy", "direct"}


def make_session(use_env_proxy: bool = True) -> requests.Session:
    """Retry 설정이 들어간 세션 생성."""
    session = requests.Session()
    session.trust_env = use_env_proxy

    retries = Retry(
        total=3,               # 최대 3번까지 재시도
        backoff_factor=5,      # 1차 5초, 2차 10초, 3차 15초 대기
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # 일반 브라우저처럼 보이도록 헤더 설정
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


def fetch_gold_stocks(url: str, timeout=(10, 120)) -> requests.Response:
    """
    환경에 따라 프록시/직접 연결 전략을 선택해 다운로드 요청 수행.
    """
    if NETWORK_MODE not in VALID_NETWORK_MODES:
        raise ValueError(
            f"Invalid GOLD_STOCK_NETWORK_MODE={NETWORK_MODE!r}. "
            f"Use one of {sorted(VALID_NETWORK_MODES)}"
        )

    if NETWORK_MODE == "proxy":
        print("[INFO] Network mode: proxy (use environment proxy only)")
        session = make_session(use_env_proxy=True)
        return session.get(url, timeout=timeout, allow_redirects=True)

    if NETWORK_MODE == "direct":
        print("[INFO] Network mode: direct (ignore environment proxy)")
        session = make_session(use_env_proxy=False)
        return session.get(url, timeout=timeout, allow_redirects=True)

    # auto
    print("[INFO] Network mode: auto (proxy first, then direct on ProxyError)")
    proxy_session = make_session(use_env_proxy=True)

    try:
        return proxy_session.get(url, timeout=timeout, allow_redirects=True)
    except ProxyError as e:
        print(f"[WARN] Proxy request failed: {e!r}")
        print("[WARN] Retrying with direct connection (trust_env=False)...")

        direct_session = make_session(use_env_proxy=False)
        return direct_session.get(url, timeout=timeout, allow_redirects=True)


def download_gold_stocks() -> int:
    today = dt.date.today()
    date_str = today.strftime("%Y%m%d")
    out_path = DATA_DIR / f"Gold_Stocks_{date_str}.xls"

    # 이미 오늘자 파일이 있으면 스킵
    if out_path.exists():
        print(f"[INFO] File already exists for today: {out_path}")
        return 0

    print(f"[INFO] Downloading Gold_Stocks for {today} ...")

    try:
        # timeout=(연결, 읽기) → 읽기 타임아웃을 넉넉하게 120초로 설정
        resp = fetch_gold_stocks(GOLD_STOCK_URL, timeout=(10, 120))
    except Exception as e:
        print(f"[ERROR] Request to CME failed: {e!r}")
        return 1

    if resp.status_code != 200:
        print(
            f"[ERROR] HTTP error from CME: {resp.status_code} {resp.reason}"
        )
        # 혹시 HTML 에러 페이지가 온다면 앞부분만 프린트
        try:
            text_preview = resp.text[:500]
        except Exception:
            text_preview = ""

        if text_preview:
            print("[ERROR] Response preview (first 500 chars):")
            print(text_preview)

        return 1

    # 정상 응답이면 파일 저장
    out_path.write_bytes(resp.content)
    print(f"[INFO] Saved to {out_path}")
    return 0


def main():
    code = download_gold_stocks()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
