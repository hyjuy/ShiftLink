# v14 실제 기기 테스트 준비

이번 작업은 로컬 합성 평가와 기기 테스트 준비다. Pi/Jetson 파일 설치, 서비스 변경, 운영 MES 시작, 사용자 경보 연결은 하지 않는다. 후보 결과를 먼저 보고한 후 별도 디렉터리의 오프라인 재생부터 진행한다. 실제 기기의 현재 상태는 아래 읽기 전용 확인을 실행하기 전까지 미확인이다.

## 고정 후보와 입력 경계
- 후보: output/mes-causal-v14c-20261023. candidate-lock.json과 final-audit.json의 SHA256 보존 확인 후 사용한다.
- 원본 센서69항목 중 고정 분석 입력63채널을 (equipment_id,signal)로 매핑한다. 기존68채널 Timestral 브리지와 호환된다고 가정하지 않는다.
- docs/data/reference/mes-causal-v8-signals.json의 합성 계약과 정상 통계를 사용한다. 실제 Jetson MES의 config_id·측정 의미·정상 분포가 동등한지는 별도 검증한다. config_id 덮어쓰기/검사 제거는 하지 않는다.
- Timestral/Torch 로딩 없이 NumPy 기반이다. Python/NumPy 버전·CPU 아키텍처·32/64비트를 실기에서 기록한다. 설치/업그레이드는 이번에 수행하지 않는다.
- 현재 재생 평가는 배치다. 1024프레임 처리 시간/1024는 1Hz 서비스의 프레임별 p95나 최악 처리 시간을 입증하지 않는다.

## 첫 단계: 읽기 전용 접속 및 환경 확인
기존 계정·호스트 키 확인을 유지한다. 비밀번호·키 본문을 보고서에 남기지 않는다. 아래 명령은 준비된 절차이며 실행한 것으로 간주하지 않는다.

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes pi@raspberrypi true
ssh -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 -o StrictHostKeyChecking=yes jetson@jetson-06.tail0a6af3.ts.net true
```

접속 성공 후 읽기 전용으로 uname -m, getconf LONG_BIT, python3 --version, NumPy 버전, /proc/meminfo, /proc/loadavg, 디스크 여유, 열 센서와 vcgencmd get_throttled 지원 여부, 기존 PDA/얼굴/CNN 프로세스의 메모리·CPU 상태를 확인한다. 실패하면 장비 성능을 추정해 통과 처리하지 않는다.

## 순서별 실제 기기 시험과 통과 기준

| 순서 | 시험 | 기록 및 통과 기준 |
|---|---|---|
| 1 | 고정 자료 오프라인 재생 | 코드/설정/입력 SHA 일치. 로컬과 장비의 사건별 첫 통지 및 전체 통지 행 일치. 운영 API 쓰기와 경보 파일 쓰기 없음 |
| 2 | 키오스크·얼굴·설비 CNN 동시 부하 | 별도 후보 프로세스로30분 이상. CPU/RSS/가용 RAM/온도/스로틀링을 주기 기록. OOM·지속 적체·지속 메모리 증가·추가 스로틀링 없음. 기존 화면/인식 기능 유지 |
| 3 | 실제1Hz 전달 경로 | run_id·sequence·source 시각·config_id·69항목/63입력·단위·품질 검사. 3초 PDA 폴링으로 입력을 수집하지 않음. 연속 프레임 전달/재생 버퍼에서 순번 누락0 확인 |
| 4 | 프레임별 처리 및 지연 | 수신·대기·전처리·탐지·결과 기록 시각을 각각 저장. 1초 입력 주기를 지속 처리하고 큐가 증가하지 않음. 실제 p95와 최대값을 보고. 기존 합성 p95와 구분 |
| 5 | 단절·오래된 값·재시작 | 결측/순번 점프/구성 변경/불량/정지 설비를 이상 증거로 대치하지 않음. 이력 부족·미확인 상태를 표시. 예전 run의 경보 재전송 없음. 현 후보 reset은 새 에피소드이며 재시작 중복 방지의 영속 정책은 추가 설계 필요 |
| 6 | 실제 센서 그림자 관측 | 사용자 통지 없이 EWMA 기준과 동일 원자료·가동시간·품질 정책으로 비교. 정비/운전 기록을 독립 정답으로 검수. 탐지율·오통지/시간·중복·끝단 간 p95 보고 |
| 7 | PDA 통합 검토 | 기존 active_alarms와 같은 알람창에서 사건 ID/확인 상태/진동을 한 번만 처리하는 어댑터 검증 후 별도 결정. 현재 v14는 이 연결을 구현하거나 승인하지 않음 |

30분은 처리 안정성 점검의 최소 길이이며 현장 오통지율 검증에 충분한 시간이 아니다. 장기 정상·운전 전환과 실제 고장 자료를 추가해야 한다.

## 중지와 복구
새 후보 프로세스만 종료하면 테스트를 중지할 수 있도록 별도 PID·결과 폴더를 사용한다. systemd 등록·자동 시작·기존 서비스 덮어쓰기는 하지 않는다. 기존 MES/PDA 설정과 active_alarms를 보존하고 후보 출력은 독립 JSON/로그에만 쓴다. 통지 경로는 연결하지 않는다. 인증·계약·자원·재시작 검증 중 하나라도 실패하면 실시간 연결을 보류하고 로그와 고정 후보를 보존한다.

최종 성능·실행 여부·실기 준비 파일의 로컬 검증 결과는 결과 보고서에 기록한다.

## 오프라인 재생 묶음
최종 새 평가와 감사를 통과하면 output/mes-causal-v14-device-bundle-20261023.zip을 만든다. 최소 의존 코드·고정 설정·합성 개발2실행2048프레임·기대 통지·상대 경로 SHA manifest를 담으며 모델 가중치와 정답 고장 장부는 넣지 않는다. manifest에 로컬 Python/NumPy 버전과 candidate-lock SHA를 기록한다. Python3.9 이상과 NumPy 가용성을 먼저 확인한다. 별도 폴더에서 다음 명령으로 읽기 전용 입력 재생과 새 결과 파일 기록만 수행한다.

```bash
python3 -B -c "import sys,numpy; print(sys.version); print(numpy.__version__)"
python3 -B replay.py --out ../pi-offline-parity-new.json
```

`passed=true`, v13/v14 두 통지 집합의 parity=true, Timestral/Torch 로딩=false가 기준이다. 이미 있는 결과 경로를 덮어쓰지 않는다. 이는 합성 고장 성능을 새로 평가하거나 실시간1Hz를 검증하는 명령이 아니다. 서비스 등록·네트워크 요청·PDA/경보 파일 쓰기를 하지 않는다. 배치 시간은 기기별 재생 비용 참고값으로만 사용한다.

## 2026-10-23 11:55 KST 접속 확인 결과
Pi와 Jetson 모두 기본 SSH에서 exit255, `Permission denied (publickey,password).`였다. 인증 단계가 끝나지 않아 원격 true·Python/NumPy·RAM·온도 조회는 실행되지 않았다. 잘못된 비밀번호라고 단정하지 않으며 새 키 등록·호스트 키 검사 해제·인증 설정 변경을 하지 않았다. 기록은 output/mes-causal-v14-device-ssh-20261023.json이다.

따라서 로컬 성능/무결성과 재생 묶음은 검증할 수 있지만 Pi의 설치 의존성·실행 비용·동시 부하·실측 센서 성능은 미확인이다. 기존 계정의 인증 수단을 확보한 뒤 위 읽기 전용 확인부터 진행한다. 이번에는 장비 파일 복사/설치와 서비스 변경·PDA/운영 경보 연결을 하지 않았다.

## 로컬 준비 검증 완료
최종 새 평가와 감사가 통과했고 재생 묶음을 생성했다.2048프레임 독립 로컬 재생에서 passed=true·두 방법 parity=true·Timestral/Torch 로딩=false를 확인했다. ZIP SHA256은 fe08ae15376b6c25a6eea99fa3590ec647b7a175184c4d1d69f0b35b3b44c3aa다. 이는 Windows AMD64 결과이며 Pi 실행 결과가 아니다. 최신 성능과 잔여 막힘 미탐은 docs/research/mes-causal-v14-result-20261023.md를 따른다.
