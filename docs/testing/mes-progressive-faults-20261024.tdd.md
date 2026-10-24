# 점진 고장 모드 TDD 및 Pi 검증

2026-10-24 KST. 사용자가 선택한 “가끔 발생 → 점진 악화 → 수리 전까지 유지”를 구현했다. 기존 정상/랜덤 동작·원본·이전 결과를 보존하며 운영 배포는 하지 않는다. 경로는 별도 브랜치 `codex/mes-progressive-faults`다.

## 검증한 사용자 동작

| 보장 | 검증 |
|---|---|
| 정상 180~420 tick 뒤 고장 시작, 120 가동 tick에 걸쳐 악화 | 동일 사건 ID·단조 증가하는 강도·최대 영향 유지 단위 검사 |
| 네 고장 유형과 센서 관계 | HPU 누설·냉각·공압·구동 마찰 및 오일 회로 관계 검사 |
| 정지·불량 측정 보호 | pause 때 sequence/강도 고정, 비가동 설비 영향 중단, bad 측정 불변 |
| 명시적 수리만 해제 | 운전 중 수리·다른 설비 수리·진행 중 시나리오 교체 거부, pause 후 수리 성공 |
| 재현/새 실행 | seed·nonce 재현 및 reset의 새 run·깨끗한 상태 확인 |
| 공개 입력에 고장 정답 없음 | 센서 69채널과 replay 일치, state/export에서 타깃·강도 등 비공개 필드 부재, 정답의 비공개 저장 |
| 실제 HTTP 경로 | Pi loopback의 별도 ThreadingHTTPServer에서 시작→운전 중 수리 400→일시정지→수리→재가동→상태 조회 |
| 기존 경로 보존 | 기존 random_factory 및 simulation_labels 회귀 통과, 두 모드 CLI 동시 지정 거부 |

새 검사 10개와 기존 회귀 10개, 총 **20개 통과**, 실패·오류·skip 0. 36.289초(추적 포함). 새 모듈 줄 실행 관측 104/104=100%; 분기 커버리지는 측정하지 않았다. 운영 PDA JS·reader·분석 unit 해시 불변, worker PID20799·active·NRestarts=0 유지. 기존 모듈 random_factory.py·fault_schedule.py도 수정하지 않았다.

모든 실행 검증은 Raspberry Pi의 `/home/pi/shiftlink/analytics/validation/mes-progressive-20261024`에서 수행했다. 서비스·기존 가상환경은 바꾸지 않고 별도 검증 venv에 pydantic을 설치했다. 운영 MES나 PDA를 재시작하거나 실제 MES에 주입하지 않았다.

```sh
cd /home/pi/shiftlink/analytics/validation/mes-progressive-20261024/source
../test-venv/bin/python -m unittest tests.test_mes_progressive_faults tests.test_mes_random_factory tests.test_mes_random_labels -v
```

## RED → GREEN 기록

- RED 체크포인트 `27b7990`: 새 모듈과 CLI 플래그 부재를 재현. 의존성/실행 경로를 보완한 원본 소스 재검사에서도 의도한 미구현 실패를 확인했다.
- 최초 Pi 시스템 Python에는 pydantic이 없어 일부 연동 검사가 환경 오류였다. 별도 venv를 만들고 원본 소스를 다시 검사했다. 최초 로그도 보존했다.
- GREEN 1: 단위 동작은 통과했으나 소스 전달 목록에서 기존 KB 시나리오 JSON이 누락돼 연동 실패. 기존 자료를 그대로 전달했다.
- GREEN 2: 기존 from_catalog/expand 테스트 구성에는 `normal`이라는 시나리오가 없었다. 테스트의 수리 후 수동 전환 대상을 실제 구성에 있는 시나리오 ID로 바꾸고 동일한 전환·기록 검사를 유지했다.
- 최종: 20개 통과. HTTP 검사를 추가해 API로도 동일 동작을 확인했다. 기대값을 완화하거나 테스트를 비활성화하지 않았다.

수리 전 유지는 동일 실행 안의 계약이다. reset·구성 교체·프로세스 재시작은 새 시뮬레이션이며 이전 고장 영속 복원은 미구현이다. 이 결과는 생성/저장/제어 기능 검증이며 기존 AI의 탐지율·오통지·지연 평가가 아니다. 새 UI 버튼·운영 배포·실제 장비 고장은 검증하지 않았다.

상세 사용법: [점진 고장 모드](../guides/mes-progressive-faults.md). 초기 실패와 최종 로그는 Pi 검증 폴더와 로컬 output 근거 ZIP에 보존한다. 운영 로그·화면을 GitHub에 새로 게시하지 않는다.

GREEN 체크포인트: `893ef616`. 검증한 소스 4파일과 보존한 기존 생성 모듈 2파일의 Pi/PC SHA256가 모두 일치했다. 근거 ZIP: `D:/obsd/Projects/ShiftLink/output/mes-progressive-20261024-evidence.zip`; SHA256 `d25ef30e6e6e75515366902fd336be8898dcc95d4f2f55216e9afb81926a7492`. Pi ZIP CRC 및 전송 후 해시 검증 통과.
