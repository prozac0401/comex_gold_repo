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

---


## 네트워크 이슈 대응

업데이트가 프록시/네트워크 환경에 따라 실패할 수 있어 `fetch_gold_stocks.py`는 아래 환경변수를 지원합니다.

- `GOLD_STOCK_NETWORK_MODE=auto` (기본): 환경 프록시 경로를 먼저 시도하고, `ProxyError`일 때 direct 연결로 재시도
- `GOLD_STOCK_NETWORK_MODE=proxy`: 환경 프록시만 사용
- `GOLD_STOCK_NETWORK_MODE=direct`: 환경 프록시를 무시하고 direct 연결만 사용

운영 환경(GitHub Actions, 사내망 등)에서 어떤 경로가 실제로 동작하는지 모드별로 확인해두면 장애 원인을 빠르게 분리할 수 있습니다.

