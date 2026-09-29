# KB-20260929-A 검수 수정 노트 (review-fix-20260930)

| card_id | 판정 메모 | 무엇을 고쳤나 | 확인한 원문(파일 p.) | 남은 문제 |
|---|---|---|---|---|
| K-1001 | G3: ST-04 YES 분기가 '원문 흐름도를 직접 보라'로 끝나 조치 없음 | ST-04 stop_conditions를 "동작이 있으면(YES) 동작이 멈춘 상태에서 압력을 확인한다(Check pressure when motion has stopped)"로 교체 | 100980172-Logical-Troubleshooting PDF p.17 Algo A.1 흐름도(이미지 렌더링으로 확인) | ST-08은 YES/NO 두 분기가 모두 종료 조치인데 expected_result에 들어 있음(메모 범위 밖이라 두었음) |
| K-1002 | G6: 노하우 번호(1~6)와 단계(ST-01~07)가 어긋남 | know_how를 1)~7)로 다시 번호 매겨 ST-01~07과 맞춤. 1) 유온 너무 높음 → 3), 아니면 2). 2) 입·출구 온도차: 있음=정상 작동, 없음=작동 온도 도달 후 재확인. 단계(steps)는 이미 원문과 같아서 바꾸지 않음 | 같은 PDF p.29 Algo J.2 흐름도(이미지 렌더링) | ST-02 YES·ST-07 YES/NO의 종료 조치가 expected_result에 있음(메모 범위 밖). '너무 높다'의 기준값은 원문에 없음 |
| K-1004 | G2: 핵심 증상 위치 PDF p.27/인쇄 p.28이 출처 범위에서 빠짐. '가장 먼저 드러나는' → '가장 두드러진' | 첫 출처 locator를 "PDF p.24~27 / 인쇄 p.25~28"로 넓힘. rationale 문구를 '가장 두드러진'으로 교체 | HY29-0022-UK PDF p.25(인쇄 26) "most noticeable fact is an unusual noise level", PDF p.27(인쇄 28) 소음·유량/압력 미달·"milky" 거품 | 없음 |
| K-1005 | G3: ST-02 프리차지 틀림(NO) 분기는 종료 조치 | ST-02 expected_result에서 NO 분기를 빼고 stop_conditions에 "프리차지 압력이 틀리면(NO) 질소로 정상 압력까지 충전한다(Charge with nitrogen to correct pressure)"를 넣음 | 같은 PDF p.28 Algo J.1 흐름도(이미지 렌더링). 질소 충전 상자에서 나가는 화살표 없음 확인 | ST-08 YES/NO 종료 조치가 expected_result에 있음(메모 범위 밖) |
| K-1010 | G3·G6: ST-01 잠금+운전 모순. 잠금을 ST-02 앞으로, ST-03 재기동 전 해제. safety_flag=true | ST-01 action에서 잠금 문구 삭제. ST-02 preconditions에 개폐기 회로 개방·OFF 자물쇠 잠금 추가. ST-03 action에 "스위치 자물쇠를 풀어 잠금을 해제한 뒤 재기동" 추가. safety_flag=true, safety_basis에 두 번째 CAUTION 원문과 페이지 기재 | Martin_C4_CR_18_09_4_Manual PDF p.7 / 인쇄 p.5 Belt Training 첫머리 CAUTION, 2번 아래 두 번째 CAUTION | 잠금 해제 행위 자체는 원문에 명시되지 않음. 원문 "restart conveyor"를 잠금과 이어 주려고 메모대로 넣음. ST-02의 "벨트가 똑바로 돌 때까지 옮긴다"는 조정 중 운전 확인이 필요해 보여 잠금 상태와 긴장이 있음(원문도 이 부분은 명시하지 않음) |
| K-1012 | G4: 직접구동형 한정이 제목·근거에 없음 | 제목 앞에 '직접구동형'을 붙이고, rationale에 §8.3.1(직접구동형) 한정과 센터·일체형 드라이브는 §8.3.2·§8.3.3을 따른다는 문장 추가 | conveyor-manual-0323-en PDF p.62 / 인쇄 p.58 §8.3, §8.3.1 Alignment Correction Direct Drive Conveyors | symptom·know_how에는 한정 문구를 넣지 않음(메모가 제목 또는 근거를 지정) |
| K-1020 | G1: 노하우·근거가 p.6·p.17 CAUTION을 드는데 출처 목록에 없음 | provenance.sources에 p.6(Dangers, Warnings & Cautions, UP 버튼 CAUTION)과 p.17(Operating Instructions, UP 버튼·릴리프 CAUTION) 추가 | 830CC-V1 PDF p.6, p.17 | 없음 |

공통: 모든 카드 `provenance.extraction_method` 끝에 `; 사람 검수 수정 요청 반영(review-fix-20260930)`를 덧붙임. card_id·tacit_type·equipment·scenario·split·grade(L0)·status(draft)·confidence는 그대로. 7장 모두 `KnowledgeCard.model_validate` 통과.
