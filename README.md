# COMEX Gold Stocks Collector

이 리포지토리는 CME/COMEX에서 제공하는 `Gold_Stocks.xls` 파일을
GitHub Actions를 통해 **매일 자동으로 수집/아카이브**하기 위한 기본 구조입니다.

## 구조

```text
.
├─ data/               # 일일 Gold_Stocks_YYYYMMDD.xls 파일이 쌓이는 위치
├─ scripts/
│  └─ fetch_gold_stocks.py
├─ requirements.txt
└─ .github/
   └─ workflows/
      └─ fetch_gold_stocks.yml
```

## 사용 방법

1. 이 리포지토리를 GitHub에 푸시합니다.
2. `scripts/fetch_gold_stocks.py` 파일의 `GOLD_STOCK_URL` 값을
   실제 CME `Gold_Stocks.xls` 다운로드 URL로 교체합니다.
3. GitHub의 Actions 탭에서 워크플로우가 정상 실행되는지 확인합니다.
   - 매일 `cron` 스케줄에 따라 자동 실행되며,
   - 새 데이터가 있을 경우 `data/` 폴더에 파일을 추가하고 커밋/푸시합니다.
