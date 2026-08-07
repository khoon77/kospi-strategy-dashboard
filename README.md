# KOSPI Strategy Dashboard

코스피 5,900 / 5,500 / 5,200 분할매수와 6,500 / 6,800 / 7,050 분할매도 전략을 장 마감 데이터와 비교하는 GitHub Pages 대시보드입니다.

## KRX 승인 후 설정

저장소 `Settings > Secrets and variables > Actions`에 `KRX_AUTH_KEY` Secret을 등록합니다. 키는 코드나 로그에 저장하지 않습니다. 필요하면 `KRX_INDEX_ENDPOINT` Repository variable로 API 주소를 덮어쓸 수 있습니다.

매매동향 API 상품이 승인되면 해당 URL을 `KRX_INVESTOR_ENDPOINT` Repository variable에 등록합니다. `collect.yml`은 지수와 투자자별 매매동향을 함께 수집하며, 승인 전에는 사용자 제공 CSV 데이터를 보존합니다. 실제 응답 필드가 다르면 `scripts/collect_investor.py`의 `FIELDS` 매핑만 API 명세에 맞춰 조정합니다.

## 자동화

- `collect.yml`: 평일 17:20 KST에 KRX 종가를 수집하고 JSON을 누적합니다.
- `backfill.yml`: 승인 후 수동 실행하여 2016년부터 현재까지 공식 일봉과 거래대금을 채웁니다. 누락된 날짜만 요청합니다.
- `pages.yml`: 테스트 통과 후 GitHub Pages에 배포합니다.
- 최초 한 번 `Settings > Pages > Source`를 **GitHub Actions**로 선택합니다.

## 로컬 검증

```powershell
python -m unittest discover -s tests -v
python -m http.server 8000
```

## BTC 5개 거래소 통합 체결 매물대

`crypto.html`은 Binance, Bybit, Bitget, OKX, Gate.io의 BTC/USDT 현물과
USDT 무기한선물 공개 체결을 거래소별 또는 통합해서 보여줍니다. 15분, 30분,
1시간, 4시간 구간과 현물/선물 필터를 지원합니다. 캔들은 CCXT로 조회한 Binance
USDT 무기한선물 OHLCV이며, 오픈소스 Lightweight Charts로 확대·축소와 드래그를
지원합니다. 우측 매물대와 POC·VAH·VAL은 로컬 체결 DB에서 별도로 계산합니다.

수집기는 무료·오픈소스 CCXT Pro WebSocket을 사용하며 거래소 API 키가 필요하지
않습니다. 원시 체결을 그대로 쌓지 않고 1분·거래소·시장·가격구간별 매수/매도
체결량과 거래대금을 SQLite에 저장합니다. 기본 가격구간은 25 USDT입니다.
선물 체결수량은 거래소별 `contractSize`를 적용해 BTC 단위로 정규화한 뒤
합산합니다.

```powershell
Copy-Item crypto_collector\config.example.json crypto_collector\config.json
powershell -ExecutionPolicy Bypass -File crypto_collector\run.ps1
```

수집기는 `data/crypto_trades.sqlite3`에 기록하고 매분
`data/crypto_profile.json` 정적 스냅샷을 갱신합니다. 로컬 API는
`http://127.0.0.1:8765/api/profile`과 `/api/candles`에서 제공됩니다. GitHub Pages는 정적
호스팅이므로 PC 또는 별도 무료 서버에서 수집기가 계속 실행되어야 데이터가
누적됩니다. 공개 페이지에 최신 스냅샷을 표시하려면 생성된 JSON만 커밋·푸시하면
됩니다. 데이터베이스와 로컬 설정은 Git에서 제외됩니다.

수집 상태가 2분 이상 지연된 피드는 대시보드에서 경고합니다. 서버 중단 구간은
체결량 0이 아니라 **수집 누락**이므로 분석 전에 거래소별 수집 범위를 확인해야
합니다.

### 4시간 용량 측정 시험

Firebase 이전에 실제 데이터 크기를 측정하려면 전용 설정으로 4시간만 실행합니다.

```powershell
.\.venv\Scripts\python.exe crypto_collector\collector.py `
  --config crypto_collector\config.4h-test.json --duration 14400
.\.venv\Scripts\python.exe crypto_collector\report.py
```

시험 DB와 보고서는 Git에 포함되지 않습니다. 보고서는 실제 수집시간, 체결 수,
가격구간 행 수, 피드별 누락 여부와 3일·7일 저장용량 추정치를 계산합니다.

### 24/7 무료 운영

4시간 시험(384,251건, 8/10 피드 에러 0건)으로 안정성을 확인한 뒤, Firebase 대신 무료 VM
(Oracle Cloud Always Free 또는 Google Cloud e2-micro) + systemd + 5분 주기 GitHub push로
운영하는 방법을 `crypto_collector/deploy/`에 정리했습니다. 자세한 내용과 위험 요소는
[`crypto_collector/deploy/DEPLOY.md`](crypto_collector/deploy/DEPLOY.md) 참고. 캔들은 이제
Binance 공개 REST를 브라우저에서 직접 호출하므로 `api.py` 없이도 항상 뜹니다.

대시보드 차트는 2016년 이후 일봉, 일별 거래대금, 5·10·20·60·120·240일 이동평균선을 지원합니다. 승인 후 `Backfill KOSPI history` Action을 한 번 수동 실행하면 공식 KRX 자료를 적재합니다. 현재는 KRX 승인 전이므로 빈 데이터로 시작하며 화면에 `연결 대기`로 표시됩니다. 외국인 현물·KOSPI200 선물은 승인 후 실제 API 명세를 확인해 연결합니다. 이 앱은 자동 주문을 하지 않는 전략 검증 도구입니다.
