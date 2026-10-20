# ShiftLink 상단 아이콘

제공된 스크린샷을 참고해 다시 그린 SVG 5종입니다. 원본 벡터 추출물이 아니므로 미세한 형태 차이가 있습니다.

| 파일 | 용도 |
| --- | --- |
| equipment-scan.svg | 설비 스캔 |
| equipment-list.svg | 설비 목록 |
| mes.svg | MES |
| home.svg | 홈 |
| notification.svg | 알림 |

- 공통 viewBox: `0 0 32 32`, 기본 크기: 32 × 32px
- 투명 배경, 외부 폰트·이미지·라이브러리 의존성 없음
- `currentColor` 사용: SVG를 인라인으로 넣으면 부모의 CSS `color`를 따릅니다.
- `<img src="home.svg" width="32" height="32" alt="홈">`으로도 사용 가능합니다. 이 경우 기본 검정색이며 부모의 CSS `color`는 전달되지 않습니다.
- 아이콘만 있는 버튼에는 `aria-label="홈"` 등 접근 가능한 이름을 붙이고, 옆에 같은 텍스트가 있으면 이미지의 `alt=""`를 사용하세요.
- `preview.html`을 브라우저에서 열면 5개 아이콘과 상단 메뉴 적용 예시를 볼 수 있습니다.

범위: 상단 메뉴의 설비 스캔, 설비 목록, MES, 홈, 알림. ShiftLink 브랜드 로고와 본문 아이콘은 포함하지 않았습니다.
