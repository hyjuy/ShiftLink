# Pi 4용 경보 추가 실험 검증 근거

2026-10-21. [단독 사전 고정](../research/mes-timestral-pi-followup-prereg-20261021.md), [결합 사전 고정](../research/mes-timestral-pi-hybrid-prereg-20261021.md), [독립 확인 전 선정 고정](../research/mes-timestral-pi-selection-20261021.md)을 따른다. 기존 Timestral-28M checkpoint와 frozen MES runtime을 재사용한다.

## RED → GREEN와 후보 고정

- `2c7115c`: 단독 경보 인과성·엄격한 threshold·현재 초과 필요·run/sequence 단절 reset·누락 처리·두 지표 선정 테스트5개가 의도한 NotImplementedError로 실패했다. `output/mes-timestral-pi-followup-red-20261021.txt`에 보존했다.
- `b55f54a`: 구현 후 새5개+기존21개, 총26개가 통과했다. 단독18후보를 개발35사건에서 비교했으며 동시개선 후보0개였다.
- `f4e5fd4`: 독립 자료를 만들기 전에 결합18후보 설계를 추가 고정하고 결합 경보 테스트를 추가했다. 기존5개는 통과하고 새1개는 NotImplementedError로 실패했다. `output/mes-timestral-pi-hybrid-red-20261021.txt`에 보존했다.
- `cd34d70`: 최소 결합 구현 후 총27개 테스트가 통과했다. 선정 JSON과 실행 스크립트 SHA256을 기록한 문서를 commit한 뒤에만 seed55371 확인 자료를 생성했다. `output/mes-timestral-pi-hybrid-green-20261021.txt`에 보존했다.

선정 이후 실행 코드와 임계값을 바꾸지 않는다. 그림 생성은 별도 스크립트이며 후보 선정에 참여하지 않는다. 독립 확인 실제 CLI는 CPU1thread/interop1/workers1/batch1에서 저장 checkpoint의 공식 forecast()를 실행하는 E2E 검사다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_pi_followup tests.test_mes_timestral_finetune tests.test_mes_timestral_comparison
& $experimentPython -m coverage report --data-file=output/mes-timestral-pi-followup-coverage-20261021 --include='*/scripts/mes_timestral_pi_followup.py'
```

## 독립 개발 감사

별도 구현으로 기존 train prefix의 정규화 통계와 FT 예측 cache의 점수를 재구성하고 설비별 deque 경보를 계산했다. 단독18+결합18 후보 전체 metrics와 선정 순서가 정확히 일치했다. 단독 통과0개, 결합 통과3개였다. 고정 gate.1/scale1.5/k1/n1의 개발 결과는32/35·오경보16설비·초·중복102·p9512초다. 두 요청 지표의 개선과 중복·지연의 악화를 모두 보존했다. checkpoint/staticthreshold 불변, 코드·선정 해시, commit 순서도 확인했다.

## 최종 확인과 독립 감사

새 validation45사건에서 실제1888개 창의 공식 forecast()를 CPU1thread/worker1/B1로 실행했다. 최종27개 테스트도 다시 통과했다. 줄 커버리지는167 statements 중3 miss, **98%**다. branch coverage는 측정하지 않았다. 로그 `output/mes-timestral-pi-followup-final-green-20261021.txt`, 커버리지 `output/mes-timestral-pi-followup-lines-20261021.json`에 보존했다.

독립 검토자는 saved q3/actual에서 비대칭점수·설비최대를 직접 재계산해 NPZ와 일치함을 확인했다. actual도 fresh validation 원천과 일치했다. 별도 deque/결합 구현으로5방법의 전체 alerts/metrics/paired events/background/개선 관문이 일치했다.1888창·8runs·2400validation행이며 test 본문0행이다. 선정·모델·실행 스크립트·runtime48파일·fresh prefix·NPZ 해시도 일치했다. confirm grid는 null이라 새 자료에서 재탐색하지 않았다.

현재 EWMA33/45·오경보15·중복20·p959초 대비 결합40/45·오경보16·중복132·p9521초다. 따라서 현재 EWMA 대비 요청한 두 지표 동시개선은 false다. 정상재적합 EWMA의오경보17보다 작다는 이유로 기준을 바꾸지 않는다. 그림 생성 코드는 py_compile과 실제 실행으로 검사했고 네 PNG를 직접 열어 확인했다.

별도 사건 분석에서 새 탐지7건 모두 탐지 시점과 직전 시점에 EWMA가 OFF였음을 확인했다. 따라서7건은 기존 EWMA 경보의 분절로 재매칭된 경우가 아니다. 중복132건의 부담은 독립적으로 남는다.

최종 수치·그림은 [결과 보고서](../research/mes-timestral-pi-followup-result-20261021.md)에 기록한다. 운영 코드·장치 배포는 변경하지 않았다.
