# BTC 수집기 24/7 무료 운영 가이드

## 0. 지금까지 모은 데이터 점검 결과

- 진짜 운영 DB(`data/crypto_trades.sqlite3`)는 거의 비어 있음(약 1분 분량, 784건) — 대시보드에
  보이는 스냅샷이 바로 이 데이터입니다. 즉 지금까지 유의미하게 쌓인 데이터는 없고, 이제 진짜
  24/7 수집을 시작해야 하는 단계입니다.
- 별도로 돌렸던 `data/crypto_4h_test.sqlite3`(4시간 용량 측정용)는 103분간 **384,251건** 체결을
  10개 피드(5거래소 × 현물/선물)에서 정상 수집했고, 8개 피드는 에러 0건, OKX 2개 피드만
  각각 2건/6건의 일시적 에러(자동 재시도로 해결, `last_error`도 비어있음) — 수집기 자체는
  안정적으로 검증됨.
- 용량: 3일 ≈ 9.4MB, 7일 ≈ 22MB(SQLite, bin 집계 방식이라 원시 체결을 그대로 쌓지 않음).
  하루 약 3.1MB 페이스면 `store.prune()`의 기본 90일 보관 정책 기준으로도 최대 ~300MB 수준 —
  아래 어떤 무료 티어의 디스크에도 전혀 부담 없음.

## 1. 어디서 24/7 돌릴 것인가 (무료)

| 옵션 | 상태(2026-08 기준 확인) | 비고 |
|---|---|---|
| **Oracle Cloud Always Free — Ampere A1(ARM)** | 2026-06-15부로 스펙이 4 OCPU/24GB → **2 OCPU/12GB**로 조용히 축소됨(공지 없이 변경). 여전히 완전 무료. | 1순위 추천. 우리 워크로드(웹소켓 10개 + SQLite 집계)엔 축소된 스펙으로도 넉넉함. 다만 무료 ARM 인스턴스는 생성 시 "Out of capacity" 에러가 흔함 — 리전을 바꿔가며 재시도 필요할 수 있음. |
| **Google Cloud Always Free — e2-micro** | 2026-08 기준 여전히 무료 유지 확인됨(미국 리전 한정: us-west1/us-central1/us-east1). 디스크 30GB, 아웃바운드 1GB/월. | 2순위(백업). RAM 1GB로 빠듯하지만 이 워크로드는 CPU/메모리보다 네트워크 I/O 위주라 가능. Oracle 생성이 계속 실패하면 이쪽으로. |
| 집 PC/라즈베리파이 24시간 가동 | 전기요금만 들어 사실상 무료 | 절전모드·재부팅·정전·와이파이 끊김에 취약해서 애초에 "PC 꺼져도 도는 시스템"을 원하는 목적과 안 맞음. 참고용. |

두 클라우드 모두 가입 시 카드 등록이 필요하지만 **Always Free 자원만 쓰면 과금되지 않습니다.**
(Oracle은 가입 시 30일/300불 체험 크레딧이 별도로 함께 붙는데, 체험판이 끝나도 Always Free
리소스는 자동으로 계속 무료로 유지됩니다. "Pay As You Go로 업그레이드"만 누르지 않으면 됩니다.)

**계정 생성과 VM 프로비저닝은 본인 신원/결제수단 확인이 필요해서 제가 대신 할 수 없습니다.**
아래는 그 다음부터, 즉 VM에 SSH로 접속한 이후에 실행할 것들입니다.

## 2. 이번에 바꾼 구조 (핵심 아이디어: VM은 인바운드 포트를 아예 열지 않는다)

기존 구조는 `collector.py`(수집) + `api.py`(라이브 조회 서버)가 분리돼 있었는데, GitHub Pages는
정적 호스팅이라 `api.py`를 공개로 열려면 고정 IP·방화벽 인바운드 개방·HTTPS 인증서까지
세팅해야 해서 복잡해집니다.

대신 이번에 다음과 같이 단순화했습니다.

1. **캔들 차트는 서버가 필요 없습니다.** `assets/crypto.js`가 이제 Binance 공개 REST
   (`fapi.binance.com/fapi/v1/klines`)를 브라우저에서 직접 호출합니다(CORS 확인 완료 —
   `crypto_collector/api.py`의 `/api/candles` 프록시와 동일한 데이터를 서버 없이 받습니다).
2. **매물대(체결 프로필)는 VM이 5~10분마다 GitHub로 push만 합니다.** VM은 거래소
   웹소켓(아웃바운드)과 GitHub push(아웃바운드)만 하면 되므로 **인바운드 포트를 하나도
   열 필요가 없습니다.** TLS 인증서, 공인 IP, 방화벽 설정이 전부 필요 없어집니다.
   대신 "완전 실시간"이 아니라 "5~10분 지연 스냅샷"이 됩니다 — 개인용 의사결정 보조
   대시보드로는 충분한 수준입니다.
3. 로컬 개발 시(`api.py`를 직접 띄운 경우)에는 여전히 `http://127.0.0.1:8765`를 먼저 시도하고
   실패하면 정적 JSON으로 자동 폴백하는 기존 로직을 그대로 씁니다(포트 불일치 버그도 이번에
   8765로 통일해서 수정).

## 3. 배포 절차

```bash
# VM에서
git clone https://github.com/khoon77/kospi-strategy-dashboard.git
cd kospi-strategy-dashboard
cp crypto_collector/deploy/push.env.example crypto_collector/deploy/push.env
nano crypto_collector/deploy/push.env   # GH_TOKEN=ghp_... 붙여넣기
bash crypto_collector/deploy/setup.sh
```

`push.env`에 넣을 토큰은 GitHub에서 **Settings > Developer settings > Fine-grained tokens**로
발급하고, 이 저장소 하나에만 **Contents: Read and write** 권한만 줍니다(다른 권한 불필요).

`setup.sh`가 하는 일:
- venv 생성, `ccxt`/`aiohttp` 설치
- `crypto_collector/config.json`이 없으면 example에서 생성
- 3개의 systemd 타이머/서비스를 등록하고 즉시 시작:
  - `collector@<사용자>.service` — 수집기 본체, `Restart=always`로 크래시 시 자동 재시작
  - `push-snapshot@<사용자>.timer` — 5분마다 `data/crypto_profile.json`을 GitHub에 push
  - `healthcheck@<사용자>.timer` — 5분마다 점검, **10개 피드가 전부** 5분 이상 조용하면
    (개별 피드 하나가 잠깐 끊기는 건 정상 재시도 범위라 무시) 수집기 서비스를 강제 재시작

## 4. 확인 방법

```bash
systemctl status collector@$(whoami).service      # active (running) 인지
journalctl -u collector@$(whoami).service -f       # 실시간 로그 (connected Binance ... 등)
systemctl list-timers | grep -E 'push-snapshot|healthcheck'
```

며칠 뒤 `git log --oneline -- data/crypto_profile.json`으로 자동 커밋이 꾸준히 쌓이는지 확인하면
전체 파이프라인이 살아있다는 뜻입니다.

## 5. 알아둘 리스크

- 무료 티어 조건은 실제로 예고 없이 바뀝니다(이번 조사에서 Oracle이 2026-06에 스펙을 절반으로
  줄인 사례를 확인했습니다). 1~2년 주기로 이 표를 다시 확인하는 걸 권합니다.
- Oracle 무료 ARM 인스턴스는 리전에 따라 생성 자체가 안 될 때가 있습니다(용량 부족) — 안 되면
  리전을 바꿔보거나 Google e2-micro로 바로 전환하세요. 코드/배포 스크립트는 두 곳 모두 동일하게
  씁니다(Ubuntu 기준이면 그대로 동작).
- `push.env`는 절대 커밋하지 마세요(`.gitignore`에 이미 등록해뒀습니다). 토큰이 새면 즉시
  GitHub에서 revoke하고 재발급하세요.
