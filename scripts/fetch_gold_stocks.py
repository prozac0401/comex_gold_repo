import datetime as dt
from pathlib import Path
import requests

# TODO: 이 부분을 실제 CME Gold_Stocks.xls 다운로드 URL로 교체하세요.
# 예: CME 사이트에서 Gold_Stocks.xls 링크 주소를 복사해서 넣으면 됩니다.
GOLD_STOCK_URL = "https://www.cmegroup.com/delivery_reports/Gold_Stocks.xls"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

def main():
    today = dt.date.today()
    date_str = today.strftime("%Y%m%d")
    out_path = DATA_DIR / f"Gold_Stocks_{date_str}.xls"

    # 이미 해당 날짜 파일이 있으면 스킵
    if out_path.exists():
        print(f"[INFO] File already exists for today: {out_path}")
        return

    print(f"[INFO] Downloading Gold_Stocks for {today} ...")
    resp = requests.get(GOLD_STOCK_URL, timeout=30)
    resp.raise_for_status()

    out_path.write_bytes(resp.content)
    print(f"[INFO] Saved to {out_path}")

if __name__ == "__main__":
    main()
