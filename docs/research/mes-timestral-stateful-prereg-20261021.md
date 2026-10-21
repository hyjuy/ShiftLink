# 경보 상태 유지·빠른 해제 개선 사전 고정

2026-10-21. 사용자 요청은 Pi4용 자원 설정을 유지하며 중복 경보와 탐지 지연을 줄이고 탐지율·오경보도 현재 EWMA보다 개선되는지 확인하는 것이다. CPU1thread/interop1/worker1/B1, 기존 FP32 FT checkpoint27,821,184 parameters·68채널·context64·horizon1을 유지한다. 실제 Pi RAM/ARM 비용 미확인은 유지한다. 기존 frozen scorer와 정상 통계를 그대로 쓰고 운영 코드는 바꾸지 않는다.

## 규칙과 탐색 범위

기존 매시점 TS gate가 EWMA 경보를 끊던 방식을 상태 유지로 대체한다. 원본 측정의 rawZ=abs(value-train_mean)/train_scale 설비별 최댓값을 별도로 계산한다. 정상 통계는 기존2371..2378 train만이며 고장 라벨을 보지 않는다.

- OFF→ON: 현재 rawZ>=off_z이고, ((현재 EWMA ON이고 (gate=0 또는 현재 TSratio>gate)) 또는 (현재 TSratio>on_scale이고 rawZ>=on_z)). TSratio는 기존 FT 점수/정상 임계값이다. gate0일 때는 TS 준비 전에도 EWMA 분기를 허용한다.
- ON 유지: rawZ>=off_z이면 TS 점수가 줄어도 유지한다. rawZ<off_z가 release회 연속이면 해당 현재 프레임부터 OFF다. rawZ가 누락이면 즉시 OFF이며 누락을 정상으로 간주해 계속 유지하지 않는다. OFF 진입에도 rawZ 하한이 있어 잔류 EWMA 기억만으로 재시작하지 않는다.
- run/sequence/time 단절·비가동에서 상태를 초기화한다. TS 예측 key의64준비 단절도 초기화한다. 고장 종료 라벨을 reset에 쓰지 않는다. 후처리 상태는 설비별 boolean·카운터이며 새로운 모델 호출은 없다.
- gate {0,.1}×on_scale{.75,1,1.5}×on_z{2.5,3,3.5}×off_z{1.5,2,2.5}×release{1,2}, 총108개다. 모든 조합 on_z>=off_z다. 시드나 고장 유형별 parameter는 없다.

이전35사건(validation45379..45386)과 이전독립45사건(validation55379..55386)은 이제 모두 개발 자료다. 108개를 두 개발자료에서 재채점한다. 두 자료 각각에서 detected>EWMA, wrongEqSec<EWMA, duplicate<=EWMA, p95<=EWMA를 만족한 후보만 통과다. 통과 중 합계탐지 최대→합계오경보 최소→합계중복 최소→최대p95 최소→gate/on_scale/on_z/off_z/release 오름차순으로 하나를 선정한다. 통과가 없으면 각자료4조건 위반개수 합 최소→최악중복비율 최소→최악p95비율 최소→합계오경보 최소→합계탐지 최대→parameter순으로 진단용 하나만 선정하며 승격하지 않는다. 탐지0의p95 None은 무한대로 취급한다.

선정과 코드를 고정한 뒤 frozen v7 independent seed65371 시작, 8runs/split×300ticks, hazard.003/warmup60/response_scale.2를 생성한다. validation65379..65386만 한 번 평가한다. 이전 모든 source/normal/development/확인 corpus의 전체 seed/run과 비중복을 확인한다. test 본문은 읽거나 해시하지 않는다. 새 train은 prefix loader 접근 외에 학습·채점에 쓰지 않는다. 새 결과를 보고 다시 탐색하지 않는다.

대조군: 현재 EWMA, 이전 gate.1/scale1.5/1of1 결합, 기본 FT, 정상통계 재적합 EWMA. 추가로 동일 off_z/release를 쓰고 TS gate와 추가 분기를 없앤 EWMA 상태 유지 ablation을 기록한다. TS가 없어도 나오는 이득을 TS 기여로 부르지 않는다. 최종판정은 현재 EWMA대비 탐지율·오경보 두 지표 엄격개선 여부와 중복·지연의 비악화 여부를 구분한다. 이전 결합 대비 중복·지연 감소도 별도로 표시한다. 사건별 손실/획득·지연 분포·경보 시계열·PC추론p95와 메모리를 보고하고 Pi측정값이라고 부르지 않는다.
