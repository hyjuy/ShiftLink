# Pi 통지 사건 통합 후보 검증 — 2026-10-24

현재 상태: **새 평가의 중복 0 기준 미달 → 운영 배포 보류**. 기존 중복 3건의 회귀는 해결했으나 새 평가에서 변동성 이상 재통지 1건이 남았다. 기존 운영 r5·모델·settings·정상 profile·이전 주입 결과는 보존했다. 모델·회귀·평가·전송 검사는 모두 Raspberry Pi에서 실행했다. PC에서는 편집·Git·전송 검증·보고서 작성만 수행했다.

## 원인과 별도 후보

기존 무작위 주입 시험의 중복 3건은 마찰 2건의 온도 상승/일반 센서 경로 분리 발행, 변동 증가 1건의 회복 후 재무장에서 발생했다. 기존 OnlineDetector·ContextDetector를 수정하지 않고 `scripts/mes_causal_episode.py`의 EpisodeDetector/EpisodeSource를 추가했다. 원본 점수와 최초 통지 조건은 그대로 두고 설비별 통지 사건을 합친다. 관측했던 이상 근거가 유효한 상태에서 5개 연속 프레임 동안 2/3 경계 아래로 회복돼야 새 통지를 허용한다. 불량·알 수 없는 측정과 고착 이력 재구축은 회복으로 계산하지 않는다.

episode의 활성 상태·누적 근거·회복 카운터는 기존 context checkpoint 경로로 직렬화한다. 후보 코드 해시를 fingerprint에 추가해 운영 원본 체크포인트를 조용히 혼용하지 않는다. 원본 worker의 factory 선택은 변경하지 않았다. 실제 서비스에 후보를 연결하는 작업과 운영 배포는 하지 않았다.

## Pi RED → GREEN

- RED d6dfdc9b: 원본에서 3테스트·3실패. 통지 sequence는 마찰 [149,152], [133,135], 변동 증가 [136,156]. 첫 프레임 보존과 사건당 한 통지 기대를 검증했다.
- GREEN 791b0a1: 별도 후보의 최초 11개 테스트 통과. 첫 프레임은 각각149·133·136으로 같고 두 번째 이벤트가 사라졌다.
- 확장 회귀: **57개 통과, 실패·오류·skip 0**, 113.220초. 새 후보 검사13개 + 기존 회귀44개이며 최초 11개와 중복 합산하지 않는다.
- 후보 코드 실행 줄 확인 **78/78=100%**, import를 포함한 stdlib trace 기준이다. 분기 커버리지나 모든 현장 조건의 증명을 뜻하지 않는다.
- 체크포인트 실제 저장/복원 뒤 같은 프레임 재수신·이어지는 원래 중복 경로를 검사했다. 전체 측정 반복 hold, 수동 정지의 같은 감지 유지와 reader·재시작 통과, 불량/재구축이 회복 카운터가 되지 않는 경계, 새 설비의 독립 첫 통지, 5개 유효 정상 근거 후 새 통지, 잘못된 체크포인트 거부를 포함했다.

## 데이터 분리와 후보 고정

[사전 계획](../research/mes-causal-episode-prereg-20261024.md)을 따랐다. 이전 주입 평가의 source sequence 1~1724와 겹치지 않는 후속 1,109프레임을 사용했다. 준비 중 MES run이 바뀌어 현재 run에 after_sequence=1724 조회가 빈 결과였고 첫 도구가 IndexError를 냈다. 빈 응답을 보존하고, 저장된 원래 run의 후속 구간을 읽었다. MES reset이나 제어 요청은 하지 않았다.

- 개발 원본 시각 블록: 1725~2246.
- 사용하지 않는 간격: 2247~2310, 64프레임.
- 봉인한 평가 원본 시각 블록: 2311~2833.
- underlying source run은 공유한다. 새 run_id·seed·nonce는 파생 합성 사례를 구분하며 실제로 서로 다른 공장의 독립성은 뜻하지 않는다. 같은 split 안에서는 원본 창이 겹칠 수 있다.
- 새 주입은 이전 고정 생성기를 재사용한다. PATTERNS나 고장 규칙을 모델 입력과 공유하지 않지만, 개발·평가의 주입 메커니즘 종류와 합성 정상 생성기는 공유한다.
- 모델 학습이나 점수 임계값 조정은 하지 않았다. 개발 기준을 통과한 최초 후보를 선택했고 같은 후보·테스트·하니스·개발 입력 manifest·split 해시를 고정한 후에만 새 시험 난수를 생성했다.

개발 비교의 원본과 후보는 완전히 같은 입력을 사용했다.

| 개발 지표 | 운영 원본 | 별도 후보 |
|---|---:|---:|
| 이상 사건 탐지 | 25/28 | 25/28 |
| 중복 통지 | 9 | 0 |
| 정상/단발/불량 통지 | 0/0/0 | 0/0/0 |
| 기간·대상 밖 통지 | 0 | 0 |
| 탐지된 사건의 지연 p95 | 10프레임 | 10프레임 |

공통 탐지 25건의 최초 프레임 차이는 모두0이었다. 36조건(단일 이상20, 정상·단발·불량 각4, 가까운 이상4조건·각2사건), 모델별11,520프레임이다. 5프레임 간격의 한 사례는 둘째 사건을 원본·후보 모두 놓쳤다. 새 후보 때문에 줄어든 탐지는 없지만 가까운 사건을 모두 잡는다는 증거는 아니다.

고정 시점 코드·재현 경로 커밋은 0e1b76f4be108aa877813ce6bb9b22ec077fc9ba다. 코드·테스트·하니스 해시는 Pi candidate-lock.json에 기록한다. 새 평가 결과를 본 뒤 임계값·episode 기준·시험 난수를 바꾸지 않는다.

## 새 미사용 평가

새 난수로 60조건을 생성했다. 단일 이상32사건, 정상8·단발8·불량4, 가까운 이상8조건·각2사건으로 총48개 이상 사건을 평가한다. 모델별19,200프레임이다. 원본과 후보를 같은 입력으로 비교한다. 원본 탐지 사건 보존·최초 프레임 동일·중복0·정상/단발 통지0·불량 및 기간/대상 밖 통지 증가 없음·p95 악화 없음이 사전 기준이다. 절대 탐지율95% 달성이나 통계적 비열등성 증명으로 확대하지 않는다.

| 새 미사용 평가 지표 | 운영 원본 | 고정 후보 |
|---|---:|---:|
| 이상 사건 탐지 | 43/48 · 89.6% | 43/48 · 89.6% |
| 미탐 | 5 | 5 |
| 중복 통지 | 10 | 1 |
| 정상 오통지 (8조건) | 0 | 0 |
| 단발 통지 (8조건) | 0 | 0 |
| 불량 측정 통지 (4조건) | 0 | 0 |
| 기간·대상 밖 통지 | 0 | 0 |
| 탐지 지연 p95 | 15프레임 | 15프레임 |

60조건·모델별19,200프레임, 원본·후보 프로세스 모두 종료0. 공통 탐지43건의 첫 프레임 차이는 전부0, 잃은 탐지0이다. 사전 기준 8개 중 중복0만 실패해 전체 판정은 **FAIL**이다. 개발 p95 10과 평가 p95 15는 입력 난이도가 다른 집합의 값이며 성능 저하로 직접 비교하지 않는다. 같은 새 평가 안에서는 두 모델의 탐지·최초 프레임·지연이 같다.

탐지 지연의 기본 지표는 1초 입력 프레임의 주입 시작부터 최초 통지 프레임까지이며 추론·대기·통신·화면 시간을 포함하지 않는다. 탐지된 사건만으로 계산한 p95이며 미탐5건을 제외한다.

미탐5건은 약한 마찰·센서 편향·변동 증가 각1건과 같은 설비에서 5프레임 간격으로 발생한 둘째 사건2건이다. 모두 원본에서도 미탐이다. 후보가 새 미탐을 만들지 않았다는 결과이며 절대 탐지율 목표 달성을 뜻하지 않는다.

남은 중복은 `variance-01`의 EQ-0009 `cv_vib_rms`다. 주입 구간의 frame index137~198 안에서 최초 sequence153 통지, sequence171~175의 유효한 낮은 점수 5개 후 episode 해제, sequence188 재통지가 발생했다. sequence175의 점수/한계 비율은0.494, 재통지 때6.270이었다. 측정 불량이나 고착 이력 문제 대신 **간헐적으로 낮아진 변동성 신호를 완전 회복으로 판단한 것**이 이번 잔여 원인이다. 평가 후 읽기 전용 추적만 추가했고 후보·임계값·입력·난수는 변경하지 않았다. 이 평가셋은 이제 소비됐으므로 향후 수정의 최종 미사용 평가로 다시 쓰지 않는다.

## 전송 경로 및 운영 경계

별도 1Hz HTTP 재생에서는 이전에 소비한 냉각·공압·마찰 3사례를 사용한다. 후보 worker는 격리 프로세스에서만 EpisodeSource factory를 주입하고 별도 체크포인트·출력 경로를 사용한다. 실제 PDA proxy/reader 코드의 API를 3초 간격으로 조회해 첫 이벤트와 중복을 확인한다. 이 세 사례를 새 평가48건에 합산하지 않는다. 실제 Jetson 네트워크·Chromium/물리 화면·진동 장치 지연은 검증 범위 밖이다. 이전 headless HTTP 탐색 실패를 해결했다고 주장하지 않는다.

이번 작업에서 패키지 설치·Pi 운영 파일 교체·서비스 재시작·MES 고장 주입·실제 경보 확인 조작을 하지 않는다. 원본과 이전 평가 자료는 보존하고 최종 결과를 보고한 뒤 운영 적용 여부를 별도로 결정한다.

## 1Hz 전송 결과와 검증 도구 오류

320/320프레임을 1초 간격으로 격리 HTTP 경로에 제공했고, 실제 r5 PDA proxy/reader의 API를 3초 간격으로 조회했다. 냉각·공압·마찰 모두 감지, 중복0, API에서3건 모두 관측했다. 체크포인트 binding이 별도 후보 fingerprint와 일치함을 검증했다. worker 분석 오류0이었다.

| 기존 3사례 회귀 | 첫 통지 프레임 지연 | 주입→worker 관측 | 주입→PDA API 관측 |
|---|---:|---:|---:|
| 냉각 | 8 | 9.001초 | 11.188초 |
| 공압 | 8 | 9.001초 | 11.191초 |
| 마찰 | 6 | 7.001초 | 8.205초 |

이 값은 샘플링을 포함한 loopback 관측 지연이다. 실제 Jetson 통신·물리 화면·진동의 끝단 간 p95가 아니며 3표본에서 일반적인 p95를 주장하지 않는다.

원래 전송 검증 스크립트는 종료1이었다. 109회의 최초 API 조회가 worker 파일 생성 전이어서 optional `ai_insights` 키가 없었는데, 관측기가 필수 키로 읽어 KeyError를 기록했다. 기존 overlay는 opt-in 파일이 없으면 원본 응답을 유지하도록 구현되어 있다. 최초 오류가 첫 프레임 제공보다 앞섰고 이후108회는 정상 응답·기존 경보0·operational_notifications=false임을 Pi에서 저장 자료로 재확인했다. 실패한 스크립트·로그·전체 관측과 별도 `transport/reanalysis.json`을 함께 보존했다. 이를 전송 하니스 전체 통과로 바꾸어 표현하지 않는다.

## 보존과 배포 판정

- 고정 후보·하니스·테스트·개발 manifest·split 해시 재검증 통과. 이전52·개발36·새 평가60조건의 입력 파일 해시를 전부 확인했다. 세 집합의 파생 run_id·seed·nonce는 겹치지 않았다.
- 이전 evidence.zip SHA-256 `3fae2ed75dabb50c4d7d4afa27365390e98351a4cc2ef9539a0dcf2574da2643` 일치. 이전 계획·생성기·replay·HTTP 입력도 일치한다.
- 운영 r5 release의 manifest16개 파일 모두 보존됐다. 기존 worker는 PID7066·active/running·NRestarts0 유지. 최종 PDA 조회 AI ready·기존 경보0. 최종 온도47.7°C·throttled=0x0이며 연속 발열/부하 시험의 최댓값을 뜻하지 않는다.
- 이전 평가의 live pin10개 중9개가 일치한다. 현재 app의 PDA proxy에는 이번 작업 전(19:01, 이번 before 기록19:40)에 이미 추가된 POST `/api/query` 첨부 코드3줄이 있어 이전 pin과 다르다. 해당 코드는 덮어쓰지 않았다. GET `/api/state`와 reader는 r5 경로와 동일하다. 별도 전송 검사는 저장된 r5 proxy를 사용했으므로 현재 app 전체 UI를 검증했다고 주장하지 않는다.
- 이번 작업은 운영 파일 교체·서비스 재시작·MES 제어·실제 경보 연결을 하지 않았다. 후보 선택 factory도 운영 worker에 연결하지 않았다. **현재 운영 AI에는 이번 수정이 적용되지 않았다.**

기존 중복3건 해결과 새 평가 중복10→1 감소는 확인됐다. 그러나 사전에 약속한 중복0 기준에 실패했으므로 **운영 배포 보류**다. 남은 변동성 재발의 회복 조건은 별도 다음 개발 주기에서 다루고, 또 다른 후보 고정과 새로운 미사용 평가가 필요하다. 이번 평가를 보면서 숫자만 바꾸어 통과시키지 않는다.

## 재현과 근거

코드·명령은 Pi validation 격리 경로에서 실행한다. `P`는 `/home/pi/shiftlink/analytics/validation/episode-notices-20261024`다. 아래 평가는 새 실행 전용 출력 폴더를 요구하므로 보존된 폴더에 그대로 덮어 실행하지 않는다.

```sh
cd "$P/source"
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase setup
# Pi 회귀 및 별도 개발 비교를 먼저 통과시킨 후
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase freeze
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase make-test
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase evaluate --role test --model original
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase evaluate --role test --model candidate
python3 -B -m scripts.mes_causal_episode_validate --out NEW_VALIDATION_DIR --phase compare --role test
```

새 setup은 고정된 이번 source 범위로 설계돼 있으므로 **다음 개발 주기의 새 원본 범위·봉인 계획을 먼저 별도 작성해야 한다**. 위 명령은 이번 구현의 단계 설명이며 소비된 입력을 다시 미사용이라고 부르기 위한 절차가 아니다. 실행된 상세 명령·wrapper·전체 로그는 전체 evidence.zip에 있다. 회귀 결과는 `green-full-result.json`, 비교는 각 `comparison.json`, 최초 프레임·미탐은 각 모델 `result.json`, 보존 결과는 `final-integrity.json`, 잔여 중복 프레임 추적은 `heldout-duplicate-diagnostic.json`으로 확인한다.
## 결과 파일

- [Pi 회귀 57개·실행 줄 결과](evidence/mes-causal-episode-20261024/green-full-result.json)
- [개발 비교](evidence/mes-causal-episode-20261024/development/comparison.json), [새 미사용 평가 비교 — 전체 실패](evidence/mes-causal-episode-20261024/test/comparison.json)
- [새 평가 원본 사건 장부](evidence/mes-causal-episode-20261024/test/original/result.json), [후보 사건 장부](evidence/mes-causal-episode-20261024/test/candidate/result.json)
- [전송 관측 재확인](evidence/mes-causal-episode-20261024/transport/reanalysis.json), [잔여 중복 추적](evidence/mes-causal-episode-20261024/heldout-duplicate-diagnostic.json)
- [후보 고정](evidence/mes-causal-episode-20261024/candidate-lock.json), [보존·운영 상태](evidence/mes-causal-episode-20261024/final-integrity.json), [전체 보관 정보](evidence/mes-causal-episode-20261024/archive.json)

전체 입력·실패/성공 로그·격리 wrapper·실행 코드·checkpoint를 포함한 Pi 보관본은368파일·25,825,356바이트다. SHA-256은 `a2f490a57ee421e8c24616b8ede84c7ba110c1f4ba4af75c29f9928efd53574c`. Pi ZIP CRC 검사와 PC 전송 후 SHA-256 일치를 확인했다. PC 보관 위치는 `D:/obsd/Projects/ShiftLink/output/episode-notices-20261024/evidence.zip`이다. 확인 종료 시 격리 평가·전송 자식 프로세스는 남아 있지 않았다. 이번 요청에서는 push·PR 변경·운영 적용을 수행하지 않았다.