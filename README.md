# KOSPI Strategy Dashboard

코스피 5,900 / 5,500 / 5,200 분할매수와 6,500 / 6,800 / 7,050 분할매도 전략을 장 마감 데이터와 비교하는 GitHub Pages 대시보드입니다.

## KRX 승인 후 설정

저장소 `Settings > Secrets and variables > Actions`에 `KRX_AUTH_KEY` Secret을 등록합니다. 키는 코드나 로그에 저장하지 않습니다. 필요하면 `KRX_INDEX_ENDPOINT` Repository variable로 API 주소를 덮어쓸 수 있습니다.

## 자동화

- `collect.yml`: 평일 17:20 KST에 KRX 종가를 수집하고 JSON을 누적합니다.
- `pages.yml`: 테스트 통과 후 GitHub Pages에 배포합니다.
- 최초 한 번 `Settings > Pages > Source`를 **GitHub Actions**로 선택합니다.

## 로컬 검증

```powershell
python -m unittest discover -s tests -v
python -m http.server 8000
```

현재는 KRX 승인 전이므로 빈 데이터로 시작하며 화면에 `연결 대기`로 표시됩니다. 외국인 현물·KOSPI200 선물은 승인 후 실제 API 명세를 확인해 연결합니다. 이 앱은 자동 주문을 하지 않는 전략 검증 도구입니다.
