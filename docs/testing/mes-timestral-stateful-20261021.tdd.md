# 상태 유지 경보 실험 검증 — 2026-10-21

사용자 요청은 Pi4용 자원 범위를 유지하면서 중복·지연을 낮추고, 탐지율·오경보도 EWMA보다 개선되는지 확인하는 것이다. 기존 FT 모델과 frozen runtime은 수정하지 않았다.

## RED → GREEN와 고정 순서

- `433adae`: 6개 새 테스트가 의도한 NotImplementedError로 실패했다. 경보 유지·현재 프레임 해제·잔류 EWMA 재진입 거부·현재 rawZ 추가 진입·누락/초기화·인과성/ablation·두자료 네지표 선정을 다룬다. `output/mes-timestral-stateful-red-20261021.txt`에 보존했다.
- `909f02a`: 최소 상태 구현과 기존27개를 합친33개 테스트가 통과했다. 첫108개 개발 설정은 통과0개였다.
- `6696744`: 새 확인자료 생성 전에 증거 기반 유지32후보를 선언하고 현재 EWMA가 꺼진 뒤 TS 증거까지 약해지면 해제하는 테스트를 추가했다. 기존6개는 통과하고 새1개는 NotImplementedError로 실패했다. `output/mes-timestral-stateful-release-red-20261021.txt`다.
- `aa9aaec`: 구현 후34개 테스트가 통과했다. 추가32개도 통과0개였다.
- `c992f05`: 마지막48개 진입/해제 조합을 기존과 같은 상태 코드로 실제 평가했다.34개 테스트가 다시 통과했다. 통과0개여서 사전 고정 진단 순위로 하나를 고르고 코드·선정 JSON 해시를 commit한 뒤 새 seed65371을 생성했다.

개발 자료는 기존35+45사건이며 총188개 설정을 반복 탐색했다. 독립 확인 성공 근거로 개발 성능을 쓰지 않는다. 최종 선정은 진단 후보이고 승격되지 않았다. 고정 후 실행 스크립트는 바꾸지 않는다.

## 개발 독립 감사

검토자가 원본 train prefix에서 정상 통계, 기존 q21/q3 cache에서 점수를 직접 계산하고 설비별 scalar boolean/count 상태 머신을 별도로 구현했다. 두자료4800행×188후보, 총376채점의 전체 metrics가 모두 일치했다. 단계별108/32/48의 위반개수·최악중복비율·최악p95비율·tie 순서와 선정값도 일치했다.

최종 gate0/on_scale1/on_z2.5/off_z1.5/release2/hold_ts.1, 코드 SHA97f10e...6a8, 선정 SHA3164d...ef77가 고정 문서와 같다. 예측 입력은 valid_values와 기존 정상 통계, EWMA와 현재 TS점수뿐이며 라벨 입력은 없다. 시간/run/sequence/mode/준비상태 reset·누락 즉시OFF·현재프레임 해제·해제프레임 즉시 재진입 금지를 확인했다. ablation은 TS 진입/추가/유지를 모두 제거한다. 감사 과정의 모델 재추론·파일 변경·test본문 접근은0이다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_stateful tests.test_mes_timestral_pi_followup tests.test_mes_timestral_finetune tests.test_mes_timestral_comparison
```

## 최종 확인·커버리지·그림

새51사건·1888창을 공식모델로추론하고6방법을채점했다. 독립검토자의 q3/actual→점수/rawZ/ratio/reset→별도scalar상태기 전체경보가 일치했다. metrics/paired/background/개선관문, 코드/이전코드/모델/선정/runtime48/prefix/NPZ해시도모두일치했다. test본문0행이고 새자료에서 재탐색하지 않았다.

현재EWMA42/51·오경보11·중복28·p958초 대비 새상태유지42/51·82·27·7초다. 같은42사건을잡았고 추가탐지는없다. 이전결합46/51·9·137·8초대비 추가탐지4건을잃었다. 오경보82중81은기존ON유지중이며58은해제유예였다. 이를중복/지연만의성공으로표현하지않는다.

코드를동결한뒤새 coverage DB로34개테스트와마지막48후보개발재현을실행했다. 선정/모든metrics/grid/provenance가원본과일치했다. 줄커버리지는163 statements/21 miss/**87%**다. 수정전코드의누적coverage를이수치에섞지않았다. 실제독립확인은별도E2E근거이며87%에합산하지않았다. `output/mes-timestral-stateful-frozen-lines-20261021.json`, `output/mes-timestral-stateful-final-green-20261021.txt`에보존했다.

그림생성은py_compile·실행·사건수/p95 assert로확인하고세PNG를직접열어검사했다. branch/그림코드coverage와실제ARM장치비용은측정하지않았다. 수치·그림·PC비용은[결과보고서](../research/mes-timestral-stateful-result-20261021.md)에기록한다.
