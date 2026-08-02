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

대시보드 차트는 2016년 이후 일봉, 일별 거래대금, 5·10·20·60·120·240일 이동평균선을 지원합니다. 승인 후 `Backfill KOSPI history` Action을 한 번 수동 실행하면 공식 KRX 자료를 적재합니다. 현재는 KRX 승인 전이므로 빈 데이터로 시작하며 화면에 `연결 대기`로 표시됩니다. 외국인 현물·KOSPI200 선물은 승인 후 실제 API 명세를 확인해 연결합니다. 이 앱은 자동 주문을 하지 않는 전략 검증 도구입니다.
