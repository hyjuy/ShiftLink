# MES 설비 시각화 독립 평가

평가일: 2026-09-20. 대상은 현재 작업 트리의 ShiftLink 모의 MES이며, 기존 미커밋 UI 변경을 포함한다. 세 평가 서브에이전트가 각각 소스와 문서를 읽었다. 브라우저 실측·현장 사용자 시험·표준 인증 점수가 아닌 설계 휴리스틱 평가다. 테스트 통과율이나 커버리지와 별개다.

각 영역은 서로 다른 지표 5개 × 20점이다. 합계의 동일 가중 평균은 (67 + 75 + 63) / 3 = 68.3점이다. 이는 평가자 간 동일 문항 합의도나 통계적 신뢰도를 뜻하지 않는다.

## 평가 점수

| 평가자 | 지표 | 점수 |
| --- | --- | ---: |
| evaluate_process | 설비 식별 | 17/20 |
| evaluate_process | 소재 흐름 명확성 | 16/20 |
| evaluate_process | 공급·의존 관계와 영향 원인 | 9/20 |
| evaluate_process | 개요→상세 계층 | 15/20 |
| evaluate_process | 규모 확대 적합성 | 10/20 |
| **공정·설비 구조 합계** | | **67/100** |
| evaluate_response | 이상 발견 명확성 | 16/20 |
| evaluate_response | 자체 이상과 파급 대기 구분 | 17/20 |
| evaluate_response | 조치·정상 복귀 안내 | 17/20 |
| evaluate_response | 제품 보류·추적성 | 13/20 |
| evaluate_response | 부품 상태 해석 가능성 | 12/20 |
| **이상 대응·정비 합계** | | **75/100** |
| evaluate_usability | 시각적 위계·운전자 탐색 | 12/20 |
| evaluate_usability | 가독성·색상 대비 | 7/20 |
| evaluate_usability | 상태 표현·접근성 | 15/20 |
| evaluate_usability | 조작 효율·복구 흐름 | 13/20 |
| evaluate_usability | 반응형·움직임 제어 | 16/20 |
| **사용성·접근성 합계** | | **63/100** |

## 관찰 근거

- `shiftlink/mes/web/app.js`: 유형별 장비 SVG, 경로 순번·코일 위치, 자체 고장과 파급 대기 문구, 다음 조치·정상 복귀 단계, 기록 재생 제어 분리.
- `shiftlink/mes/web/index.html`: 요약→큰 설명형 설비 맵→상세·건전도·추이→시연 제어→복구 패널→알람 순서. 알람·조치와 관련 장비를 함께 보기 위한 화면 구조 개선 필요.
- `shiftlink/mes/web/style.css`: 부품 카드의 밝은 배경에 루트의 밝은 글씨가 상속되는 대비 결함. 정적 sRGB 계산으로 기본 부품 카드 약 1.12:1, 열화 카드와 다음 조치 제목 약 1.09:1. 실제 브라우저 렌더링 검사는 하지 않았다.
- `docs/design/mock-mes-domain.md`: 스크랩 경로는 시연에서 제외되지만 화면에서는 다른 지원 설비와 함께 표시된다. 실제 이송 분기와 유틸리티는 의미를 나누어 표현할 필요가 있다.
- `docs/guides/mock-mes-recovery.md`: 부품 건전도와 정상 확인은 합성 모델이다. 모의값 명시는 장점이나 실제 잔여수명 판단 근거로 사용할 수 없다.

## 기사에서 참고할 형태

[FA저널 기사](https://www.fajournal.com/news/articleView.html?idxno=4556)는 2017-05-26 발행된 미라콤아이앤씨 소개 기사다. 도판은 생산 현황 차트, 생산지표, 2D 라인 배치, 비스듬한 시점의 SMT 장비 행을 함께 보여준다. 집계 정보와 현장 배치를 연결하는 구성은 참고할 만하다. 도판만으로 실제 3D 엔진·실시간 모델·상호작용 방식은 확인할 수 없으며 언리얼 사용 여부도 확인되지 않는다.

ShiftLink에는 다음 구성을 권장한다.

1. 상단: 라인 상태, 중요 이상, 보류 코일, 처리량. 계산 근거 없는 OEE는 표시하지 않는다.
2. 중앙: 설비를 연결한 2D 공정도 또는 고정 시점의 간결한 입체 도식. 소재 경로와 구동·유압 공급 경로를 구분하고 원인→영향 연결을 선택적으로 강조한다.
3. 우측: 선택 설비의 이상, 관련 측정값·정상 범위, 부품 상태, 다음 조치, 복귀 조건.
4. 하단: 시간순 알람·조치 이력과 재생. 중요 알람은 하단 목록 외에도 상단에 노출한다.

생산 관리자용 집계 대시보드, 운영자용 공정·설비 관제, 정비자용 부품·측정값 상세를 계층화한다. 정상 설비는 차분하게, 이상은 색·아이콘·문구로 함께 표시한다. [Inductive Automation HMI 안내](https://inductiveautomation.com/resources/article/design-like-a-pro-optimizing-your-hMI), [실제 MES/HMI 사례](https://links.inductiveautomation.com/resources/casestudy/dohler).

## 언리얼 적용 판단

기술적으로 적용 가능하다. 현재 MES Python 엔진을 상태·조치 판정의 기준으로 유지하고, 웹 관제와 Unreal 3D 뷰가 같은 관측 데이터를 읽도록 연결하는 구조를 권장한다. Unreal 내부에서 별도로 코일 이동·고장·복귀 규칙을 계산하면 웹·기록 재생과 불일치하기 쉽다.

| 항목 | 도입 시 고려할 점 |
| --- | --- |
| 3D 활용 가치 | 공장 공간 탐색, 부품 분해도, 정비 동선, 교육·훈련에는 이점. 기사와 같은 고정 입체 배치만 필요하면 가벼운 웹 도식으로도 표현 가능 |
| 자산 | 설비·부품 모델과 MES equipment_id/component_id 매핑, 모델 수정·최적화 작업 필요 |
| 배포 | 로컬 패키지 실행 또는 Pixel Streaming 등 방식 선택. 후자는 서버에서 렌더링·인코딩하고 브라우저로 전송 |
| 인프라 | Pixel Streaming은 지원 GPU와 신호 서버가 필요. 네트워크 환경에 따라 STUN/TURN 추가, 영상 지연·끊김 표시 필요 |
| 데이터 일관성 | run_id·sequence·시각으로 동일 스냅샷을 표시하고 데이터가 오래되면 애니메이션을 멈춤. 재생 데이터와 실시간 데이터 혼합 방지 |
| 내구도 | 사실적인 3D 모델이 부품 건전도의 정확도를 높이지는 않음. 실측 데이터와 검증된 열화 모델은 별도 |
| 라이선스 | 조직 매출·사용 목적·배포 방식에 따라 무료·좌석·로열티 조건이 달라지므로 공식 조건 확인 |

공식 근거: [Epic Pixel Streaming 개요](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-pixel-streaming-in-unreal-engine), [요구사항](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-pixel-streaming-reference), [라이선스](https://www.unrealengine.com/license).

현재 우선순위는 대비 결함 → 이상/영향/조치의 한 화면 연결 → 실제 관계를 표현하는 공정도다. 3D 도입 전후 효과는 별도 프로토타입과 사용자 과제로 검증해야 하며, 구현되지 않은 Unreal 화면에는 실측 점수를 부여하지 않았다.
