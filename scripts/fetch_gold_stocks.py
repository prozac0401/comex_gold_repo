import datetime as dt
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# CME Gold stocks 엑셀 파일 주소
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def make_session() -> requests.Session:
    """Retry 설정이 들어간 세션 생성."""
    session = requests.Session()

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


def download_gold_stocks() -> int:
    today = dt.date.today()
    date_str = today.strftime("%Y%m%d")
    out_path = DATA_DIR / f"Gold_Stocks_{date_str}.xls"

    # 이미 오늘자 파일이 있으면 스킵
    if out_path.exists():
        print(f"[INFO] File already exists for today: {out_path}")
        return 0

    print(f"[INFO] Downloading Gold_Stocks for {today} ...")

    session = make_session()

    try:
        # timeout=(연결, 읽기) → 읽기 타임아웃을 넉넉하게 120초로 설정
        resp = session.get(
            GOLD_STOCK_URL,
            timeout=(10, 120),
            allow_redirects=True,  # 리다이렉트 자동 추적
        )
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
