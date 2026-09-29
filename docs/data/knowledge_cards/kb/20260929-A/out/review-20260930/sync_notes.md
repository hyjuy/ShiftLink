# review-20260930 반영 노트

출처: `review_20260930_reviewed.md`. 원본: `out/{CV,RT,GR}.json`. 모든 카드는 `provenance.extraction_method`에 반영 문구를 덧붙였다.

- K-1015: rationale 변경. steps는 문구 변화 없음(stop_conditions가 없던 단계에 빈 목록만 명시). ST-04의 "; "로 이어진 중지 조건은 두 항목으로 나눴다.
- K-1018: safety_basis 변경.
- K-1021: symptom, know_how, rationale, safety_basis, provenance.sources, steps(4단계 유지, ST-01·ST-03에 중지 조건 추가, 문구 갱신).
- K-1023: title, symptom, know_how, rationale, safety_basis, provenance.sources, steps(2단계 유지, ST-01에 중지 조건 추가, 문구 갱신).
- K-1025: title, component, know_how, rationale, safety_basis, provenance.sources, steps(5단계 유지, 기존 ST-03(교환 이력)·ST-04(오일 채취)를 ST-03(이력 확인+채취)·ST-04(교환 판단)로 재구성).
- K-1027: title, symptom, know_how, rationale, provenance.sources, steps(4단계 유지, ST-04에 중지 조건 추가, 문구 갱신).

## 판단이 애매했던 점

- 출처 locator: 검수본 표기를 그대로 따랐다. 그래서 K-1021·K-1023·K-1025는 "PDF p.N" 대신 "p.N"이 되었다. 두 번째 출처에 파일명이 없으면(K-1021 p.6, K-1025 p.42–43) 앞 출처의 source_id를 이어받았다. document_version은 기존 값을 유지했다.
- K-1021: 링크 하나가 출처 두 개(p.34·p.6)를 감싸고 있어서 두 locator 모두 끝에 URL을 붙였다.
- expected_result 안의 에스컬레이션: K-1021 ST-04의 "문제가 해결되지 않으면 Autoquip에 문의한다."와 K-1023 ST-02의 "문제가 계속되면 Autoquip에 후속 지시를 요청한다."는 `중지:` 표시 없이 `→` 뒤에 있어서 expected_result에 그대로 두었다.
- 검수본에 드러나지 않는 단계 필드(preconditions, escalation_target)는 같은 step_id의 기존 값을 그대로 두었다. 모두 검수본 내용과 맞는다. K-1021 ST-01·ST-03, K-1027 ST-04에 새로 생긴 에스컬레이션에는 escalation_target을 새로 만들지 않았다.
