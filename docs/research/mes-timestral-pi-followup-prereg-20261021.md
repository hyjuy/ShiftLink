# Pi 4용 Timestral 경보 개선 추가 실험 사전 고정

2026-10-21. PC에서 실험하고 Pi 4용 CPU1thread/interop1/workers1/batch1을 유지한다. 기존 FT checkpoint·FP32·68채널·context64·horizon1·정상 임계값은 재학습하지 않는다. 실제 Pi RAM/ARM 비용은 아직 미확인이다.

후보는 정상 임계값 배수 {0.5,0.75,1,1.25,1.5,2} × 인과 확인 {1/1,2/3,3/5}, 총18개다. 매 시점 현재 점수가 threshold*scale을 엄격히 초과하면서 최근n개 중k개 이상 초과해야 경보한다. 초기에는 실제 관측만 쓰며 부족한 이력은 false로 본다. run 또는 sequence 단절 때 이력을 초기화한다. 프레임 누락/모드 단절은 원래 forecast key에서 단절된다. 미래나 고장 라벨은 경보 입력이 아니다. 추가 상태는 설비10개×최대5비트이며 추가 신경망 호출은 없다.

이전 weak validation45379..45386의35사건은 재사용한 개발셋이며 최종 일반화 근거가 아니다. 18개를 모두 보고 동시 개선 후보(detected_events>현재EWMA, wrong_alert_equipment_seconds<현재EWMA) 중 탐지수 최대→오경보 최소→p95 최소→scale/k/n 오름차순으로 하나만 고른다. 통과 후보가 없으면 탐지수 최대→오경보 최소→p95 최소→scale/k/n 순으로 진단용1개만 고르고 승격하지 않는다. 선택을 JSON과 Git에 고정한 뒤 새 데이터 생성/본문 접근을 한다.

독립 확인 자료는 frozen v7 independent, seed55371 시작, 8runs/split×300ticks, hazard.003/warmup60/response_scale.2다. validation55379..55386만 채점하고 source·normal·개발 corpus 전체 seed/run과 비중복을 확인한다. test 본문은 읽거나 해시하지 않는다. 새 train은 loader의 prefix 접근만 있고 적합에는 쓰지 않는다. 기존 checkpoint와 선정1개만 평가하며 새 결과를 보고 재탐색하지 않는다. 현재 EWMA·새정상자료통계 재적합 EWMA·기존 FT 기본경보를 대조한다.

판정은 새 validation에서도 현재 EWMA보다 탐지수가 엄격히 많고 오경보 설비·초가 엄격히 적은지다. 중복·p95·사건 손실/획득·배경 경보·경보 합집합 시간은 모두 함께 보고한다. p95는 탐지 성공건만의 지연이며 추론p95와 구분한다. 개발통과와 독립확인통과를 구분하고 어떤 결과도 개선을 보장하지 않는다. 새자료 factual replay·runtime/코드/checkpoint/선정/예측 해시·공식 예측 실행을 검사한다. 모델 추론과 causal경보 처리만의 PC비용을 기록하며 Pi속도라고 표시하지 않는다.

표와 그림은 개발18후보·독립확인 비교 막대·경보 시계열·탐지 지연 분포를 포함한다. 합성 running 한모드의 결과이며 현장 적용과 Jetson/Pi 배포는 범위 밖이다.
