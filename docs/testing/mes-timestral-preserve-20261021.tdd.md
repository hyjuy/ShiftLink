# 이전 결합 보존형 실험 검증

2026-10-21. 사용자 요청은 이전 결합의 탐지율과 오경보를 보존하며 중복·지연을 줄이는 것이다. [사전 고정](../research/mes-timestral-preserve-prereg-20261021.md), [선정 고정](../research/mes-timestral-preserve-selection-20261021.md)을 따른다.

## RED → GREEN

- `e7ed8ee`: 새6개 테스트를 미구현 경로에서 실행해 `FAILED(errors=6)`을 확인했다. 원본ON보존·연결상한·증거실패/초기화·미래역채움금지·earlyanchor예산·원본대조일치·사건/오경보/지연보존선정을 다룬다. 로그 `output/mes-timestral-preserve-red-20261021.txt`다.
- `40ff837`: 최소구현 후40개테스트(새6+기존34)가통과했다. early테스트는EWMA OFF시점을명시해원본ON과새early분기를구분했다. 로그 `output/mes-timestral-preserve-green-20261021.txt`다. 코드·선정JSON해시를commit한뒤에만새seed75371을생성했다.

세개발자료에서원본변경없는대조의전체metrics가이전결과와일치하는지검사했다.127후보×세자료를실제frozen scorer로채점하며 매시점원본ON subset 새ON과 wrong>=원본을assert했다. 후보선정은기존탐지사건손실0·공통사건지연증가0·오경보/중복/p95비악화를동시에요구했다. 선정보존성은개발자료에서의결과이며새자료일반화로부르지않는다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_preserve tests.test_mes_timestral_stateful tests.test_mes_timestral_pi_followup tests.test_mes_timestral_finetune tests.test_mes_timestral_comparison
```

## 최종 확인

고정 코드와 선정값으로 새47사건을 실제 추론·채점했다. 최초 실행은1665/1888창 출력 후 중단돼 저장 예측이 없었다. 같은 설정을 새 폴더에서 다시 실행했고 exit0으로 완료했다. 완료 원본은 `output/mes-timestral-preserve-confirmation-retry-20261021/result.json`과 `confirmation-predictions.npz`다.

- 이전 결합→보존형: 탐지40/47→40/47, 오경보19→19설비·초, 중복118→62회, p959→9초.
- 기존 탐지 사건 손실0·지연 증가0, 조기2·동일38건. `original_preserved=true`다.
- 현재 EWMA 대비 탐지36→40건·오경보22→19설비·초로 `requested_improvement_vs_ewma=true`다. 중복20→62회는 EWMA보다 여전히 많다.
- 독립 scalar 재구현으로5방법 전체 alerts/metrics/background/paired/gates와 전체 provenance 해시가 일치했다. savedq3→점수/ratio/rawZ/reset을 별도로 계산했으며 모델 재실행·파일 변경·test 접근0이다.
- 원본ON은 모든 시점에서 새ON의 부분집합이다. 추가ON142설비·초 중 활성 원인142·비활성0이다. fill_only134·early_only8·동시0이다.
- factual replay2400프레임·prefault795프레임 동일, test 본문0행, 새 확인 grid=null이다.
- 줄 커버리지120/121문장(99%). DB `output/mes-timestral-preserve-coverage-20261021`, export `output/mes-timestral-preserve-lines-20261021.json`이다. branch coverage는 측정하지 않았다.
- 공용 그림 생성기를 새3방법 결과와 이전4방법 결과 양쪽에서 실제 실행했다. 탐지건수와 nearest-rank p95가 frozen 결과와 일치하는 assertion이 통과했다. 새3그림과 이전 비교그림을 시각 확인했다. 출력은 `output/mes-timestral-preserve-figures-20261021`과 `output/mes-timestral-stateful-plot-regression-20261021`이다.

실행코드 SHA256 `b3a2074f6e0c42a961ddd3c7daecb5bd2f6b183e48e12d6b0d0ee45aca2276a6`, 선정 `2e778dd68a0de39055680c06eba38242c551e9bebdaea159e18bc5806b3780b1`, 예측NPZ `273398bf344dfdbed4c7db06919dc1413b9a4895b43ea25b8a900463c3544518`을 확인했다.

새 후보는 고정 모델의 경보 후처리이며 Pi4 실측은 아니다. 원본 p95의 엄격한 감소는 확인하지 못했다. 결과·사용 방법·현장/실시간 제한은 [결과 보고서](../research/mes-timestral-preserve-result-20261021.md)에 기록했다.
