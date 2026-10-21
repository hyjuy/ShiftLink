# 재무장 결합 검증 근거

2026-10-21. [사전 고정](../research/mes-timestral-rearm-prereg-20261021.md)과 [결과](../research/mes-timestral-rearm-result-20261021.md)를 따른다.

## RED → GREEN

- `f2ae2c1`: 신규7개 테스트를 미구현 함수로 실행해 `FAILED (errors=7)`을 확인하고 고정했다. 로그는 `output/mes-timestral-rearm-red-20261021.txt`다.
- `24f2c15`: 재무장과선정 최소 구현을 적용했다. 신규7+기존40개 관련 테스트47개가통과했다(`Ran 47 tests in 16.678s`, `OK`). 로그는 `output/mes-timestral-rearm-green-20261021.txt`다.
- 참조 provenance 검사까지 포함한 최종 코드로 신규7개를 다시 실행해통과했다. 로그 `output/mes-timestral-rearm-final-green-20261021.txt`이며 최종 커버리지DB는 `output/mes-timestral-rearm-final-coverage-20261021`다. 이전 단계DB와 혼용하지 않았다.

보장은 경보해제 후 정상복귀 없는 반복진입 차단, ON연장 없음, 해제프레임 quiet미포함, 재무장완료 다음프레임 진입, EWMA OFF와TSratio<=.1의정상증거, 누락으로재무장하지않기, run/time단절초기화, 미래역채움금지, 조기진입의억제우회금지, 자료별보존·EWMA중복수준·최근자료strict지연선정, 잘못된계약거부다. 개별지연증가를하드조건으로추가하지않는것도선정테스트로고정했다.

```powershell
$experimentPython = Join-Path $env:TEMP 'shiftlink-timestral-20261021/Scripts/python.exe'
& $experimentPython -m unittest tests.test_mes_timestral_rearm tests.test_mes_timestral_preserve tests.test_mes_timestral_stateful tests.test_mes_timestral_pi_followup tests.test_mes_timestral_finetune tests.test_mes_timestral_comparison
```

## 실제 개발 실행

최종 코드와72개후보를고정한뒤개발CLI를실행해exit0으로완료했다. 네자료각각에서현재결합과EWMA전체지표가참조JSON과같고, prefix/예측NPZ 해시가이전기록과같음을검사했다. 결과는 `output/mes-timestral-rearm-development-20261021/result.json`, 진단snapshot은 `latest-result.json`이다. 새학습·모델추론·test본문읽기없이 저장예측으로288개지표세트를채점했다.

줄커버리지는99/101문장(98%)이며 `output/mes-timestral-rearm-lines-20261021.json`에내보냈다. branch coverage는측정하지않았다. 72개모두최근자료p959초로strict감소조건실패, 전체통과0개다. 사전조건을완화하지않고새seed85371생성·추론을생략했다.

진단후보는최근47건탐지40·오경보4설비초·중복16·p959초다. 현재결합40/19/62/9와비교해지연개선은없다. 고장중경보시간487→226설비초감소를별도보고해중복억제의손실을숨기지않았다. 모델조건유지를Pi하드웨어검증으로부르지않는다.

새개발그림3개를실제생성하고시각확인했다. 각탐지수와nearest-rank p95 assertion이통과했다. 기존보존형결과도별도출력경로 `output/mes-timestral-rearm-plot-regression-20261021`에서그림생성exit0을확인했다.

기존그림3개는원본 `output/mes-timestral-preserve-figures-20261021`의동명PNG와SHA가모두같았다. `git diff --check`도통과했다.

## 독립 감사

별도 scalar 보존+재무장 엔진과직접점수수식으로4×72전체metrics/lost/delayed,72parameter집합,제약·선정순위,최신3방법전체alerts/metrics/paired/background를재현했다.4자료prefix/NPZ·참조JSON·실행코드·preserve·helper·checkpoint·runtime48파일해시가모두일치했다. 모델재실행·파일수정·test본문접근0으로PASS했다.

최신공통40사건은earlier0/same40/later0이다. 억제한ON276설비초는활성원인261·비활성원인15이며추가ON0이다. 비활성원인15초중전체라인정상라벨시점은1초뿐이다. 활성고장경보시간487→226감소를독립확인했고, 최초탐지와지속고장표시를같은성능으로해석하지않았다. 통과0개·지연strict조건실패를유지하며이후추가탐색/새seed/배포는없다.
