import csv
import re
from datetime import datetime
from pathlib import Path

import xlrd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUT_CSV = BASE_DIR / "summary.csv"
DATE_LABEL_PATTERN = re.compile(
    r"(?P<label>Activity|Report) Date:\s*(?P<date>\d{1,2}/\d{1,2}/\d{4})",
    re.IGNORECASE,
)


def parse_date_from_filename(path: Path):
    """Extract YYYYMMDD from the filename and return a date."""
    match = re.search(r"(\d{8})", path.stem)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%Y%m%d").date()


def parse_date_from_sheet(sheet):
    """Prefer CME's activity date over the download/report date."""
    report_date = None

    for row_idx in range(sheet.nrows):
        for col_idx in range(sheet.ncols):
            cell = sheet.cell(row_idx, col_idx)
            if cell.ctype != xlrd.XL_CELL_TEXT:
                continue

            match = DATE_LABEL_PATTERN.search(str(cell.value))
            if not match:
                continue

            parsed = datetime.strptime(match.group("date"), "%m/%d/%Y").date()
            if match.group("label").lower() == "activity":
                return parsed
            report_date = parsed

    return report_date


def parse_number(value):
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_total_from_row(sheet, row_idx):
    """Return the last numeric cell from a totals row."""
    last_val = None
    for col_idx in range(sheet.ncols):
        cell = sheet.cell(row_idx, col_idx)
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            last_val = cell.value
    return last_val


def extract_totals_from_xls(path: Path):
    print(f"[INFO] Parsing {path.name} ...")

    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    date = parse_date_from_sheet(sheet) or parse_date_from_filename(path)
    if date is None:
        print(f"[WARN] Skip file without date in workbook or name: {path.name}")
        return None

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

    if any(
        value is None
        for value in [
            total_registered,
            total_eligible,
            total_pledged,
            combined_total,
        ]
    ):
        print(
            f"[WARN] Missing some totals in {path.name}: "
            f"reg={total_registered}, eli={total_eligible}, "
            f"ple={total_pledged}, comb={combined_total}"
        )

    return {
        "date": date.isoformat(),
        "total_registered": total_registered,
        "total_eligible": total_eligible,
        "total_pledged": total_pledged,
        "combined_total": combined_total,
        "_source_priority": 2,
    }


def extract_totals_from_csv(path: Path):
    date = parse_date_from_filename(path)
    if date is None:
        print(f"[WARN] Skip file without date in name: {path.name}")
        return None

    print(f"[INFO] Parsing {path.name} ...")

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader, None)

    if row is None:
        print(f"[WARN] Empty fallback snapshot: {path.name}")
        return None

    return {
        "date": row.get("date") or date.isoformat(),
        "total_registered": parse_number(row.get("total_registered")),
        "total_eligible": parse_number(row.get("total_eligible")),
        "total_pledged": parse_number(row.get("total_pledged")),
        "combined_total": parse_number(row.get("combined_total")),
        "_source_priority": 1,
    }


def extract_totals(path: Path):
    suffix = path.suffix.lower()
    if suffix == ".xls":
        return extract_totals_from_xls(path)
    if suffix == ".csv":
        return extract_totals_from_csv(path)
    return None


def main():
    rows = []

    for path in sorted(DATA_DIR.glob("Gold_Stocks_*.*")):
        totals = extract_totals(path)
        if totals is not None:
            rows.append(totals)

    if not rows:
        print("[INFO] No data rows parsed; nothing to do.")
        return

    rows.sort(key=lambda row: row["date"])

    dedup = {}
    for row in rows:
        existing = dedup.get(row["date"])
        if existing is None or row["_source_priority"] >= existing["_source_priority"]:
            dedup[row["date"]] = row

    final_rows = [dedup[date] for date in sorted(dedup.keys())]

    prev_reg = None
    prev_comb = None
    for row in final_rows:
        reg = row["total_registered"]
        comb = row["combined_total"]

        if prev_reg is None or reg is None:
            row["delta_registered"] = None
        else:
            row["delta_registered"] = reg - prev_reg

        if prev_comb is None or comb is None:
            row["delta_combined"] = None
        else:
            row["delta_combined"] = comb - prev_comb

        prev_reg = reg
        prev_comb = comb

    fieldnames = [
        "date",
        "total_registered",
        "total_eligible",
        "total_pledged",
        "combined_total",
        "delta_registered",
        "delta_combined",
    ]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        for row in final_rows:
            writer.writerow({key: row.get(key) for key in fieldnames})

    print(f"[INFO] Wrote {OUT_CSV.relative_to(BASE_DIR)} with {len(final_rows)} rows")


if __name__ == "__main__":
    main()
