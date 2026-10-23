# v14c 상태 재사용 및 Pi 검증 (2026-10-23)

현재 선택한 후보는 Timestral을 제외한 통계 기반 경로다. 새 `scripts/mes_causal_v14_stream.py:OnlineDetector`는 NumPy와 센서 스키마만 가져온다. 설정의 `no_timestral`은 기존 고정 설정을 읽는 키이며 신경망 실행을 뜻하지 않는다. 기존 v14c, 원본 stage5, 학습·개발·평가 산출물과 과거 부하 실패 기록은 수정하지 않는다.

## 변경 범위

매 프레임 누적 과거 전체를 `prepare`/`predict`로 다시 계산하던 시험 경로를, 중앙값5·고착16·온도 상승37개 배열과 EWMA 및 경보 상태기를 유지하는 별도 실행기로 대체한다. 프레임 원문과 누적 통지 이력을 저장하지 않는다. 경보 상태기의 지속 카운터는 판단에 필요한 상한까지만 유지한다. 임계값·4회 지속·5회 정상 회복·원인 채널의 측정 유효성·온도 회복 밴드와 독립 근거 보존 규칙은 고정 후보와 같다.

새 인스턴스·run 변경·sequence/시각 단절은 준비 구간을 다시 시작한다. 직전64개 연속 가동 프레임이 있어야 현재 프레임을 판단한다. 준비 완료 전에는 사용자 통지를 반환하지 않는다. 중복/역순/오래된 시각 프레임은 상태를 갱신하지 않는다. config_id·69채널 전체 순서·단위·시각 계약 오류는 상태 변경 전에 거부한다. 설정이 선택한63개 채널과69개 전송 채널은 구분한다. 불량·결측·오래된 개별 센서값은 보간하지 않고 미확인으로 처리한다.

반환값은 첫 통지 대상 설비 ID 집합이다. MES/PDA 쓰기, 기존 active_alarms, 화면 표시·진동 경로에 연결하지 않는다. 프로세스 간 영속 경보 저널은 구현하지 않았다. 재시작/단절 뒤 준비 구간을 거쳐 재통지할 수 있으므로 운영 중복 억제를 보장하는 배포 서비스로 해석하지 않는다.

## 검증과 보존

실행 장비는 Raspberry Pi 4다. PC에서는 코드 작성·Git 체크포인트·압축·전송·결과 보관만 한다. RED는 Pi의13건 모두 NotImplementedError, GREEN은 동일13건 통과로 확인했다. 체크포인트는 a2a9938 → fb775e6이며 원본 코드 대신 별도 모듈만 추가했다.

`python3 -B -m unittest tests.test_mes_causal_v14_stream -v`는 정상·냉각 상승·독립 전류·고착/불량 측정·전체 수집 고정·가동 중단·run 변경·sequence 단절·중복·시각·계약 오류·상한 이력을 검사한다. 기존 통계 회귀도 Pi에서 실행한다. 과거 Timestral 예측 전용 검사와 이전 하이브리드 tail-guarded 검사는 현재 후보 범위에 포함하지 않으며 신경망 패키지를 설치하지 않는다.

현재 고정 개발2048프레임과 v14c에서 이미 소비한 평가 입력을 프레임별 기대 통지와 비교한다. 이 재생은 실행 방식의 동치 회귀이며 새 미사용 평가나 탐지율 개선의 근거가 아니다. 동일 통지 행이면 탐지·오통지·중복·합성 사건 지연 결과도 그대로다. 정답 장부를 새 실행기의 입력으로 사용하지 않는다.

1초 시험은 단독 및 실제 YuNet/SFace·CNN 동시 실행을 각각256프레임 측정한다. 비전은 합성 JPEG를 사용하며 얼굴 검증/설비 사진 정확도는 측정하지 않는다. 파싱→증분 판단 시간, 입력 예정 시각→완료 시간, 큐·마감·통지 일치·RAM·온도·스로틀링·기존 PDA GET을 기록한다. 실제 Jetson 네트워크와 PDA 경보 렌더링 시간은 포함하지 않는다. 이전 단독147/256·동시138/256의 전체 p95는 완료 구간 길이가 다르므로 엄밀한 동일 구간 속도비와 구분한다.

Pi의 독립 시험 폴더는 `/tmp/shiftlink-v14c-test.eOqMDX/stream-runtime-v1`다. `validate.py`는 저장소의 `scripts/mes_causal_v14_stream_validate.py` 복사본이며 기존 보존 측정 도구를 명시적으로 읽는다. 모든 결과는 새 파일로 저장한다. 감독기는75℃·가용RAM512MiB 미만·스로틀링·기존 서비스 실패·시간 초과에 시험 프로세스만 종료한다. 해당 폴더의 `STOP_STREAM`은 중지 표식이다. 기존 systemd·패키지·서비스 설정·모델·경보는 변경하지 않는다.

최종 실측 결과와 원자료는 `output/mes-causal-v14-stream-20261023`에 별도로 보존한다. 새 경로의 장시간 안정성, 현장 센서 탐지 성능, 실제 전송/표시 지연과 영속 재시작 중복 억제는 별도 검증 대상이다.

## 호출과 재현

프레임마다 같은 인스턴스의 `step`을 호출한다. 프레임마다 객체를 새로 만들면 준비 구간과 경보 상태를 재사용할 수 없다.

```python
import json
from scripts.mes_causal_v14_stream import OnlineDetector

with open('settings.json', encoding='utf-8') as source:
    detector = OnlineDetector(json.load(source))
with open('frames.jsonl', encoding='utf-8') as source:
    for line in source:
        equipment_first_notices = detector.step(json.loads(line))
        # 독립 검증 출력으로만 사용한다. 운영 경보 API는 호출하지 않는다.
```

Pi의 실행 환경에서 다음 명령을 사용했다. `results`는 존재하지 않는 새 경로여야 하며 재실행 시 기존 결과를 덮어쓰지 않는다. 감독기의75℃/RAM/PDA 보호와 `STOP_STREAM` 감시는 별도 `supervise-stream.py`가 수행한다. 재현용 감독기와 보존 측정 도구는 최종 증거 ZIP에 포함한다.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
PYTHONDONTWRITEBYTECODE=1 nice -n 10 python3 -B validate.py \
  --root /tmp/shiftlink-v14c-test.eOqMDX/stream-runtime-v1 \
  --bundle /tmp/shiftlink-v14c-test.eOqMDX/bundle \
  --replay /tmp/shiftlink-v14c-test.eOqMDX/stream-runtime-v1/consumed-replay \
  --reference-probe /tmp/shiftlink-v14c-test.eOqMDX/followup-probe.py \
  --out /tmp/shiftlink-v14c-test.eOqMDX/stream-runtime-v1/results
```

## 최종 결과

모든 검사와 아래 수치 계산은 Pi에서 실행했다. 신규 실행기13건·기존 통계 회귀117건, 총130건 통과, 신규 실행기 실행 줄 커버리지85.24%다. 과거 신경망 예측1건은 범위에서 제외했고, 이전 하이브리드 tail-guarded12건도 이번 후보의 회귀 집합에 포함하지 않았다. 기존의130건 집합과 이번130건 집합은 구성원이 다르다.

개발2,048프레임·2개 실행·5건 통지, 소비된 평가26,624프레임·26개 실행·52건 통지가 모두 원본과 행별 일치했다. 총28,672프레임 불일치0건이다. 따라서 기존 자료의 탐지·정상 오통지·중복·사건별 지연을 그대로 보존했다. 새로운 미사용 평가나 현장 일반화 개선으로 설명하지 않는다.

| Pi에서1초 간격 측정 | 분석 단독 | 얼굴·CNN 동시 |
|---|---:|---:|
| 접수/처리 |256/256|256/256|
| 통지 불일치 |0|0|
|1초 마감 초과 |0|0|
| 처리 p95 |36.968ms|19.941ms|
| 처리 최대 |49.382ms|39.350ms|
| 입력 예정 시각→완료 p95 |37.325ms|20.388ms|
| 최대 큐 대기 |0.269ms|0.397ms|
| 최대 대기열 |0|0|
| 최고 온도 |44.790℃|46.738℃|
| 최소 시스템 가용RAM |2,507,368KiB|2,269,668KiB|

동시 부하가 더 빠른 원인을 입증한 시험은 아니다. 각 조건1회 측정이며 유휴 구간의 CPU 주파수·스케줄링 등이 달라질 수 있다. 과거와 동일한 처리 구간만 비교하면 단독 첫147프레임 중 준비 이후83개의 p95가1.250126초→0.032489초, 동시 첫138프레임 중 준비 이후74개가1.284966초→0.016867초였다. 서로 다른 완료 구간의 전체 p95로 단순 속도 배수를 주장하지 않는다.

얼굴 YuNet+SFace와 CNN은 각각257회 정상 추론했다. 얼굴 추론 p95 257.440ms·최대412.624ms, CNN p95 92.187ms·최대154.310ms다. 합성640x480 JPEG와 강제 합성 얼굴 랜드마크를 사용했다. 얼굴 로그인 성공률과 실물 설비 사진 정확도는 측정하지 않았다.

분석 프로세스의 시험 구간 최대RSS는105,240KiB였다. VmHWM387,080KiB는 앞선 회귀와288MB 입력 파일 무결성 검사까지 포함한 동일 프로세스의 고수위이므로 순수 분석 메모리로 해석하지 않는다. 동시 부하의 얼굴/CNN 최대RSS는 각각188,376/100,808KiB이며 공유 페이지가 포함돼 단순 합산이 추가 물리RAM은 아니다. 단일코어100% 기준 관측 평균 CPU는 분석1.13%·얼굴64.56%·CNN20.22%였다. 각50개 표본의 해당 프로세스 평균이며 전체4코어 시스템 사용률이 아니다.

모든 감독 표본은 스로틀링0x0·PDA HTTP200이었다. 기존PDA PID14480 유지, 서비스·모델·라벨7파일과 고정 소스42개 해시 보존, 원본 묶음 SHA256 보존을 재확인했다. 새 검증·비전·CPU 관측 프로세스는 모두 종료됐다. 시스템 패키지 설치·systemd 변경·서비스 재시작·운영 경보 연결은 하지 않았다.

상태 재사용 경로의 새 시험은 조건별256프레임(약4분16초)이다. 기존30분 배치 안정성 결과는 보존하며 새 경로가30분 부하시험까지 완료했다고 주장하지 않는다. 실제 Jetson 전송·PDA 경보 표시 지연, 실측 센서 정확도 및 프로세스 재시작을 넘는 영속 중복 억제는 미검증이다.

Pi 생성 상세 보고서: [pi-result.md](../../output/mes-causal-v14-stream-20261023/evidence/pi-result.md), [verified-summary.json](../../output/mes-causal-v14-stream-20261023/evidence/verified-summary.json). 원자료·실행 코드·감독기·회귀 로그: [stream-evidence.zip](../../output/mes-causal-v14-stream-20261023/stream-evidence.zip). ZIP CRC 검증과 아래 SHA256 계산도 Pi에서 수행했다.

`18e34e1f8acdc8e4af11296d2edde8effe0f111f9ea0c0617bceafdef07c6e6c`
