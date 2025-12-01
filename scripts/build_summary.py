from pathlib import Path
import re
from datetime import datetime
import csv

import xlrd

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


def get_total_from_row(sheet, row_idx):
    """
    한 행에서 숫자 셀들만 골라 마지막 숫자 값을 반환.
    (TOTAL REGISTERED 등의 '최종 재고' 값)
    """
    last_val = None
    for col_idx in range(sheet.ncols):
        cell = sheet.cell(row_idx, col_idx)
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            last_val = cell.value
    return last_val


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

    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)

    total_registered = None
    total_eligible = None
    total_pledged = None
    combined_total = None

    for row_idx in range(sheet.nrows):
        first_cell = sheet.cell(row_idx, 0)
        if first_cell.ctype == xlrd.XL_CELL_EMPTY:
            continue

        label = str(first_cell.value).upper().strip()

        if label.startswith("TOTAL REGISTERED"):
            total_registered = get_total_from_row(sheet, row_idx)
        elif label.startswith("TOTAL ELIGIBLE"):
            total_eligible = get_total_from_row(sheet, row_idx)
        elif label.startswith("TOTAL PLEDGED"):
            total_pledged = get_total_from_row(sheet, row_idx)
        elif label.startswith("COMBINED TOTAL"):
            combined_total = get_total_from_row(sheet, row_idx)

    if any(v is None for v in [total_registered, total_eligible, total_pledged, combined_total]):
        print(f"[WARN] Missing some totals in {path.name}: "
              f"reg={total_registered}, eli={total_eligible}, ple={total_pledged}, comb={combined_total}")

    return {
        "date": date.isoformat(),
        "total_registered": total_registered,
        "total_eligible": total_eligible,
        "total_pledged": total_pledged,
        "combined_total": combined_total,
    }


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

    # 날짜 순 정렬 + 같은 날짜는 마지막 것만 사용
    rows.sort(key=lambda r: r["date"])
    dedup = {}
    for r in rows:
        dedup[r["date"]] = r
    dates_sorted = sorted(dedup.keys())
    final_rows = [dedup[d] for d in dates_sorted]

    # Δ Registered, Δ Combined 계산
    prev_reg = None
    prev_comb = None
    for r in final_rows:
        reg = r["total_registered"]
        comb = r["combined_total"]

        if prev_reg is None or reg is None:
            r["delta_registered"] = None
        else:
            r["delta_registered"] = reg - prev_reg

        if prev_comb is None or comb is None:
            r["delta_combined"] = None
        else:
            r["delta_combined"] = comb - prev_comb

        prev_reg = reg
        prev_comb = comb

    # CSV 저장
    fieldnames = [
        "date",
        "total_registered",
        "total_eligible",
        "total_pledged",
        "combined_total",
        "delta_registered",
        "delta_combined",
    ]

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in final_rows:
            writer.writerow(r)

    print(f"[INFO] Wrote {OUT_CSV.relative_to(BASE_DIR)} with {len(final_rows)} rows")


if __name__ == "__main__":
    main()
