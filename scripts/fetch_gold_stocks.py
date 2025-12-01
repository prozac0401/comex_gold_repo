import datetime as dt
from pathlib import Path

import requests

# CME Gold stocks 엑셀 파일 주소
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)


def download_gold_stocks():
    today = dt.date.today()
    date_str = today.strftime("%Y%m%d")
    out_path = DATA_DIR / f"Gold_Stocks_{date_str}.xls"

    # 이미 오늘자 파일이 있으면 스킵
    if out_path.exists():
        print(f"[INFO] File already exists for today: {out_path}")
        return 0

    print(f"[INFO] Downloading Gold_Stocks for {today} ...")

    headers = {
        # 일반 브라우저처럼 보이게 User-Agent 세팅
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36"
        ),
        # 대충 CME 사이트 내에서 온 것처럼 보이게 Referer 추가
        "Referer": "https://www.cmegroup.com/",
        "Accept": "*/*",
    }

    try:
        resp = requests.get(
            GOLD_STOCK_URL,
            headers=headers,
            timeout=60,
            allow_redirects=True,
        )
    except Exception as e:
        print(f"[ERROR] Request to CME failed: {e}")
        # GitHub Actions가 실패로 인식하도록 1 리턴
        return 1

    if resp.status_code != 200:
        print(
            f"[ERROR] HTTP error from CME: {resp.status_code} {resp.reason}"
        )
        # 혹시 html 에러 페이지 내용이 온다면 앞부분만 찍어서 디버깅에 도움
        text_preview = ""
        try:
            text_preview = resp.text[:500]
        except Exception:
            pass

        if text_preview:
            print("[ERROR] Response preview:")
            print(text_preview)

        return 1

    # 정상 응답이면 파일 저장
    out_path.write_bytes(resp.content)
    print(f"[INFO] Saved to {out_path}")
    return 0


def main():
    code = download_gold_stocks()
    # main의 return 값을 프로세스 종료 코드로 사용
    raise SystemExit(code)


if __name__ == "__main__":
    main()
