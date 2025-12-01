from pathlib import Path
import re
from datetime import datetime

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_CSV = BASE_DIR / "summary.csv"


def parse_date_from_filename(path: Path):
    """
    파일명에서 YYYYMMDD 부분을 뽑아서 date로 변환.
    예: Gold_Stocks_20251201.xls → 2025-12-01
    """
    m = re.search(r"(\d{8})", path.stem)
    if not m:
        return None
    s = m.group(1)
    return datetime.strptime(s, "%Y%m%d").date()


def extract_totals_from_file(path: Path):
    """
    한 개의 Gold_Stocks_YYYYMMDD.xls 파일에서
    TOTAL REGISTERED / ELIGIBLE / PLEDGED / COMBINED TOTAL
    의 '최종 재고' 숫자만 뽑아오는 함수.
    """
    date = parse_date_from_filename(path)
    if date is None:
        print(f"[WARN] Skip file without date in name: {path.name}")
        return None

    print(f"[INFO] Parsing {path.name} ...")

    # CME Gold_Stocks.xls 는 보통 옛날 xls 형식이라 xlrd 엔진 사용
    df = pd.read_excel(path, engine="xlrd")

    # 첫 번째 컬럼을 라벨로 사용 (TOTAL REGISTERED 등)
    first_col = df.columns[0]
    labels = df[first_col].astype(str).str.upper().str.strip()

    def get_total(label_key: str):
        """
        label_key 로 시작하는 행을 찾아 그 행의 '마지막 숫자 컬럼'을 반환.
        (예: TOTAL REGISTERED 행의 맨 오른쪽 숫자 = 당일 최종 재고)
        """
        mask = labels.str.startswith(label_key)
        if not mask.any():
            print(f"[WARN] No row for {label_key} in {path.name}")
            return None

        row = df.loc[mask].iloc[0]

        # 숫자 컬럼만 골라서 마지막 값 사용
        numeric_vals = row.select_dtypes(include="number")
        if len(numeric_vals) > 0:
            return numeric_vals.iloc[-1]

        # 혹시 숫자 타입 인식이 안 되면, 그냥 마지막 컬럼 사용 (fallback)
        return row.iloc[-1]

    totals = {
        "date": date.isoformat(),
        "total_registered": get_total("TOTAL REGISTERED"),
        "total_eligible": get_total("TOTAL ELIGIBLE"),
        "total_pledged": get_total("TOTAL PLEDGED"),
        "combined_total": get_total("COMBINED TOTAL"),
    }
    return totals


def main():
    rows = []

    # data/ 폴더의 Gold_Stocks_*.xls 전부 훑기
    for path in sorted(DATA_DIR.glob("Gold_Stocks_*.xls")):
        t = extract_totals_from_file(path)
        if t is not None:
            rows.append(t)

    if not rows:
        print("[INFO] No data rows parsed; nothing to do.")
        return

    df = pd.DataFrame(rows)

    # 날짜 순 정렬 + 같은 날짜가 있으면 마지막 것만 사용
    df = df.sort_values("date")
    df = df.drop_duplicates(subset=["date"], keep="last")

    # 전일 대비 변화(Δ Registered, Δ Combined Total) 계산
    df["delta_registered"] = df["total_registered"].diff()
    df["delta_combined"] = df["combined_total"].diff()

    # summary.csv 로 저장
    df.to_csv(OUT_CSV, index=False)
    print(f"[INFO] Wrote {OUT_CSV.relative_to(BASE_DIR)} with {len(df)} rows")


if __name__ == "__main__":
    main()
