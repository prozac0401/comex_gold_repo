# COMEX Gold Stocks Collector

이 리포지토리는 CME/COMEX에서 제공하는 `Gold_Stocks.xls` 파일을  
GitHub Actions를 통해 **매일 자동으로 수집/아카이브**하고,  
각 날짜별 **창고 재고 요약(`summary.csv`)을 자동으로 생성**하기 위한 구조입니다.

---

## 디렉토리 구조

```text
.
├─ data/                    # 일일 Gold_Stocks_YYYYMMDD.xls 파일이 쌓이는 위치
├─ scripts/
│  ├─ fetch_gold_stocks.py  # CME에서 Gold_Stocks.xls 다운로드
│  └─ build_summary.py      # data/ 아래 xls들을 읽어 summary.csv 생성
├─ summary.csv              # 날짜별 재고 요약 테이블 (자동 생성/갱신)
├─ requirements.txt         # Python 의존성 (requests, pandas, xlrd 등)
└─ .github/
   └─ workflows/
      └─ fetch_gold_stocks.yml  # GitHub Actions 워크플로우 설정

