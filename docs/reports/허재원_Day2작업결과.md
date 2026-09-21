## Day2 (9/15) 작업 결과 요약 — 허재원

### 1. Ollama 설치·구동

- Ollama 설치 완료, systemd 서비스로 정상 기동 확인 (active (running))
- CUDA GPU 정상 인식 로그 확인 (library=CUDA, VRAM 7.4GB)

### 2. 모델 pull 및 GPU 오프로드 확인

- qwen2.5:3b-instruct-q4_K_M (플랜 B) pull 완료 (2.2GB)
- ollama ps 결과: **PROCESSOR 100% GPU** ✅

**특이사항**: GUI(GNOME 데스크톱) 켜진 상태에서는 cudaMalloc failed: out of memory로 실행 실패. GUI를 끈 상태(multi-user.target)에서만 성공. → 4.3 전환 조건 판단에 참고할 실측 데이터.

### 3. Jetson 기본 정보

| 항목 | 값 |
| --- | --- |
| 모델 | NVIDIA Jetson Orin Nano Engineering Reference Developer Kit Super |
| L4T | R36 (release), REVISION 4.7 |
| JetPack | 6.2.1 |
| 전력 모드 | **15W(0) · 25W(1, 기본값) · MAXN_SUPER(2) · 7W(3)** — 계획서(4.3)엔 3개만 언급됐으나 실제 4개 확인 → N-6 보고 필요 |
| RAM | 7.4GiB (물리) |
| 저장장치 | eMMC 119.1G, 루트 116G 중 32G 사용 |

**RAM "89GB" 의혹 해소**: 실제 RAM은 7.4GiB로 확인. 89GB는 저장공간(eMMC) 수치 오기로 판단됨.

### 4. 유휴 메모리 실측 (GUI 켬/끔) — VSCode 완전 종료 후 순수 SSH로 재측정

| 상태 | used | available |
| --- | --- | --- |
| GUI 켠 상태 | 2.1Gi | 5.0Gi |
| GUI 끈 상태 | 1.6Gi | 5.6Gi |

→ VSCode Remote-SSH 접속 자체가 약 100MB 점유함을 확인 (계획서가 "끊고 재라"고 한 이유 실증).

### 5. jtop 동작 확인

- 설치·실행 정상. 모델명·JetPack 버전·실시간 메모리/전력/GPU 확인 가능.

### 6. 구조화 출력 (F-02 스키마: 요청·조건·부정·철회·원문 위치)

**테스트 목적**: Ollama가 자유 형식 텍스트가 아니라 **정해진 JSON 틀(pydantic 스키마)로만 답하도록 강제**할 수 있는지 검증.

**방법**: request·condition·negation·withdrawal·source_location 5개 필드로 구성된 틀을 정의 → 가상의 인수인계 메모 예시를 넣어 "이 틀대로만 답하라"고 요청 → 결과를 파이썬으로 재검증 → 소요 시간 기록.

**결과**: pydantic 검증 **성공** — 플랜 B 모델이 강제된 JSON 형식을 깨지 않고 답변함을 확인.

| 구분 | load_duration | 전체 응답 시간 |
| --- | --- | --- |
| 콜드 스타트(모델 최초 로딩 포함) | 30.02초 | 35.24초 |
| 웜 상태(모델 상주 후) | 0.01초 | **4.94초** |

→ keep_alive: -1 상주 시 응답 5초 내외로 p95 15초 목표에 충분한 여유 확인.

**품질 이슈(참고 기록)**: 형식은 지켰지만 원문의 명백한 부정 표현("조정은 하지 마세요")을 negation: false로 놓침 — 정확도는 3주차 P5 검증(judge·사람 검수)에서 다듬을 부분.

### 7. 발열·전력 (tegrastats)

| 구분 | tj(최고온도) | 전력(VDD_IN) |
| --- | --- | --- |
| 유휴 상태 | ~45.2°C | ~3.1W |
| 구조화 출력 요청 처리 중(피크) | **~48.5°C** | **~18.8W** |
| 처리 후 안정화(2~3초 내) | ~45.4°C | ~3.5W |
- 단발 요청 하나로도 GPU가 풀가동(GR3D_FREQ 99%)되며 유휴 대비 온도 +3.3°C, 전력 약 6배 상승 확인
- 요청 종료 직후 빠르게 유휴 수준으로 복귀 — 단발 요청 기준으로는 쓰로틀링 우려 없음
- 다만 이는 "1건" 기준이며, 연속 부하 시 열 누적 여부는 별도 확인 필요 → **연속 20건 발열 측정은 계획대로 Day3(9/16)에서 진행**

---

### Day2 완료 기준 대조

- ✅ Jetson 기록표 게시용 데이터 확보 (L4T·전력모드·유휴메모리·jtop)
- ✅ 플랜 B 구조화 출력 1건 성공 (지연·온도·메모리 포함)
- ⏳ models.lock 작성은 아직 — PC 쪽에서 같은 digest pull 후 최재영과 함께 확인 필요 (Day2 최재영 담당 항목)