# Gemini·Veo 작업 지시문 (팀원 AI에게 그대로 붙여 넣기)

아래 `## 지시문` 아래쪽을 통째로 복사해 Gemini(또는 Google Flow 에이전트)에 붙여 넣는다. 사람은 승인 버튼과 결과 검수만 한다.

사람이 먼저 할 일
- Google Flow(flow.google.com)에 로그인하고 새 프로젝트를 만든다. 동의·약관 창은 사람이 직접 처리한다.
- 설정(톱니바퀴) → 동영상 생성 기본값: **16:9, x1, Veo 3.1 - Fast**. 품질 확인용 재생성만 Quality로 바꾼다.
- 생성 전 확인은 **"항상"** 으로 둔다. 컷당 약 20 크레딧(Veo 3.1 Fast, 8초 기준)이 든다. "항상 승인"은 누르지 않는다.
- 결과 영상을 내려받아 `output/video/clips/<컷 이름>.mp4`로 저장하고 `python -X utf8 docs/demo/video/tools/build_rough_cut.py`를 실행하면 러프컷에 들어간다.

---

## 지시문

너는 ShiftLink 시연 영상(5분)의 **AI 생성 컷 17개**를 Google Flow의 Veo 3.1로 만든다. 아래 규칙과 컷별 프롬프트를 그대로 쓰고, 마음대로 장면을 바꾸지 마라.

### 배경
ShiftLink는 냉연 코일 라인의 베테랑 노하우를 신입에게 잇는 현장 AI 시스템이다. 영상은 베테랑의 마지막 근무 → 신입의 문제 상황 → ShiftLink로 해결 → 지식 순환 순서다. 너는 이야기 속 현장 장면(사람과 설비)만 만든다. 화면 녹화, 모션그래픽, 자막, 내레이션은 다른 사람이 처리한다.

### 절대 규칙
1. 프레임 안에 **읽을 수 있는 글자, 로고, 자막, 그래픽을 넣지 않는다**(한글은 깨진다. 글자는 편집에서 얹는다). 모든 프롬프트 끝에 `No readable text, logos, subtitles or graphics anywhere in the frame. No dialogue, no music.` 를 붙인다.
2. 모든 컷 프롬프트 앞에 아래 **공통 블록(스타일 + 설비 + 해당 인물)** 을 그대로 복사해 붙인다. 문장을 요약하거나 바꾸지 마라. 컷마다 얼굴과 설비가 달라지지 않게 하는 유일한 방법이다.
3. 한 번에 **1컷, 1영상**만 생성한다(16:9, x1). 마음에 안 들면 같은 프롬프트로 최대 2번까지 다시 만든다. 그래도 안 되면 멈추고 사람에게 어떤 점이 틀렸는지 보고한다.
4. **크레딧 확인 창은 사람이 승인한다.** 스스로 "항상 승인"을 켜지 마라. 컷 하나를 시작하기 전에 지금까지 쓴 크레딧과 남은 컷 수를 한 줄로 알려라.
5. 생성 영상의 길이는 컷 길이보다 길어도 된다(Veo는 보통 8초). 편집에서 앞부분만 쓴다.
6. 결과를 받으면 **저장 파일명 = `컷 이름.mp4`** 로 정리한다(아래 표의 이름을 그대로).

### 공통 블록

**스타일(전 컷)**
`Grounded semi-realistic cinematic look of a premium industrial brand film, cold-rolling steel coil line, steel grey with cool blue-green fluorescent light and warm amber machine lamps, soft haze, slow dolly or slider moves, no handheld shake, no speed ramps.`

**설비(HPU, 모든 컷에서 같은 기계)**
`The hydraulic power unit (HPU) is always the same machine: dark blue steel tank, round pressure gauge, tank sight glass, filter housing, cage frame.`

**인물(필요한 컷에만 해당 줄을 붙인다)**
- Veteran: `Korean man in his early sixties, short grey-white hair, deep smile lines, faded navy work jacket with worn reflective strips and a name patch, old scuffed white helmet, worn leather pocket notebook in his chest pocket.`
- New Hire: `Korean man in his early twenties, slim, short black hair, brand-new bright white helmet (from sheet 2 on: one small scuff), stiff clean navy work jacket, safety glasses pushed up, work gloves.`
- Shift Lead: `Korean woman in her thirties, hair tied back under a yellow helmet, navy work jacket with sleeves rolled once, clipboard.`
- Next-Shift Worker: `seen only from behind, orange helmet, navy work jacket, at night.`

**초록 화면 컷(★)** 은 프롬프트 끝에 추가: `camera locked off, completely static, the screen is a plain, evenly lit solid green rectangle with sharp edges and no reflections`

### 컷별 프롬프트 (순서대로 만든다)

각 항목 = `[스타일] + [설비] + [필요한 인물] + [아래 장면 문장] + [끝 문장]`.

| 컷 이름 | 쓸 길이 | 인물 | 장면 문장 |
|---|---|---|---|
| s1-01_GEN | 6초 | Veteran | Wide establishing shot at dawn, eye level, slow lateral slide right to left along the coil line. Huge silver coils on saddles, the HPU in the foreground, a wall clock above the control booth. By the booth a few workers gather around the Veteran with a small bouquet and a blank farewell banner; he bows slightly and smiles. Audio: low pump hum, distant coil clank, soft polite applause. |
| s1-02_GEN | 5초 | Veteran | Medium shot, slightly low angle, very slow push-in. The Veteran stands alone beside the HPU, rests one bare hand flat on its painted housing, tilts his head and closes his eyes, listening. Amber indicator light on his grey hair and smile lines. Audio: pump rhythm rises, faint pressure tick, slow exhale. |
| s1-03_GEN | 4초 | Veteran | Close-up on the Veteran's weathered hands closing the worn leather notebook (pages dense with handwritten sketches and arrows) and sliding it into his chest pocket as he turns away. Behind him, softly out of focus, a locker with its nameplate removed. Static camera, focus racks from notebook to empty locker. |
| s1-04_GEN | 7초 | New Hire | Medium shot, eye level, cooler colour temperature, weeks later. The New Hire stands alone before the HPU. The tank sight glass shows milky foam, the pump sounds rougher, a small amber warning lamp blinks. He lifts his gloves halfway, stops, looks around for someone who is not there. Slow dolly-in that stops short, leaving space around him. |
| s1-05_GEN | 6초 | New Hire | Close-up, three-quarter view of the New Hire's face, brand-new white helmet, safety glasses pushed up. His eyes move from the foaming sight glass to a thick English-language equipment manual binder on a nearby shelf and back. He swallows. Static camera with a slow rack focus from eyes to binder and back. |
| s1-06_GEN | 6초 | Shift Lead | Over-the-shoulder shot from behind the Shift Lead's yellow helmet. She reads a handwritten handover sheet on her clipboard with one short vague line; her pen hovers; she tilts the clipboard toward the light and frowns. The handwriting stays soft and unreadable. Gentle slide to the right over her shoulder. |
| s1-08_GENMG ★ | 6초 | Shift Lead | High-angle shot looking down at the Shift Lead standing at a plant-floor terminal. She looks at the screen, exhales, lowers her clipboard. The camera is locked off and does not move at all. (★ 초록 화면 문장 추가) |
| s1-09_GENMG ★ | 5초 | 없음 | Dynamic low-angle shot rising toward a small fanless edge computer and a rugged handheld PDA mounted beside the line, its screen dark. The haze thins slightly and the light warms a touch; the frame ends with clean empty space above the device. Smooth crane-up from floor level to eye level, ending centred on the device. |
| s2-05_GEN | 5초 | Shift Lead, New Hire(안전모에 작은 흠집) | Wide shot, shift change on the cold-rolling line, daylight from high windows. The Shift Lead, clipboard under her arm, walks out and gives a tired nod to the arriving New Hire. Between them a rugged handheld PDA kiosk stands on a pole mount near the line, the HPU in the background. Slow lateral dolly. |
| s2-09_GEN | 4초 | New Hire | Medium shot. The New Hire lowers the PDA, looks across the floor toward the HPU, jaw set, and this time pulls his work gloves on. Slow push-in. |
| s3-04_GEN | 6초 | New Hire | Close-up. The New Hire's eyes shift from the handheld PDA to the round pressure gauge on the HPU, the needle sitting low, then to the milky foam in the sight glass. Static camera, rack focus from his eyes to the gauge to the sight glass. |
| s3-11_GEN | 7초 | New Hire | Medium shot. Kneeling by the HPU with a small flashlight, the New Hire checks the suction pipe joint, then opens the filter housing and frowns at a dark clogged filter element, glancing around the floor. Slow slide, shallow depth of field. |
| s3-14_GEN | 5초 | New Hire, Shift Lead | Medium shot. The New Hire speaks into a handheld radio; a small inset frame shows the Shift Lead in a site office answering her radio with a nod. (대사는 편집에서 합성 음성으로 얹으므로 `no spoken dialogue`) |
| s4-05_GEN | 5초 | New Hire | Medium shot. Carrying a new filter element from a storeroom shelf, the New Hire fits it into the open filter housing of the HPU, gloved hands steady. Static or slow slide, daylight from high windows. |
| s4-09_GENREC ★ | 7초 | Shift Lead | Over-the-shoulder shot from behind the Shift Lead at a site-office computer, calm neutral office, her yellow helmet set down on the desk. Camera locked off; the monitor shows a plain solid green rectangle. |
| s4-11_GEN | 6초 | Next-Shift Worker | Wide shot at night, cooler blue light with amber machine lamps. From behind, the Next-Shift Worker in an orange helmet stands at the HPU and raises a handheld PDA. Slow dolly-in. |
| s5-06_GEN | 4초 | New Hire | Close-up in golden late-afternoon light. The New Hire rests one bare hand flat on the painted housing of the HPU, head tilted, eyes closed, listening, warm amber light on his face. **s1-02와 같은 구도·각도·거리**. Very slow push-in. |

s2-07은 이미 완료, s1-07·s4-04는 실물 촬영이라 만들지 않는다.

### 만들기 전에 판단할 것
- **s2-09, s4-11**: Unity 3인칭 녹화로 대체할 수 있다. 사람이 "Unity로 대체"라고 하면 건너뛴다.
- **s1-03**: 손·수첩이 일그러지면 억지로 재생성하지 말고 "실물 촬영으로 대체 필요"라고 보고한다.
- **s5-06**: 먼저 s1-02 결과를 시작 프레임(이미지)으로 넣거나, 안 되면 프롬프트에 `same framing, same lens, same camera angle and distance as the s1-02 shot, only the character is the young New Hire` 를 추가한다. 인물은 신입 외형으로 바꾼다.
- **글자가 보이면** 그 컷은 재생성한다(최대 2번). 프롬프트에 `all screens, labels and papers are blank and blurred` 를 추가한다.

### 시작 프레임 이미지(선택)
Flow의 "프레임 to 동영상"에 컷 이미지를 넣으면 인물이 더 일관된다. 이미지는 Nano Banana로 먼저 같은 인물 블록으로 만들고, 마음에 드는 것만 영상 시작 프레임으로 쓴다. 이미지가 없으면 텍스트만으로 시작한다.

### 보고 형식 (컷마다 한 줄)
`컷 이름 | 생성 횟수 | 사용 크레딧 | 문제(없음/글자 보임/얼굴 다름/설비 다름/기타) | 저장 파일명`

### 하지 말 것
- 한글이나 영어 문구를 화면에 넣는 프롬프트
- 공통 블록 바꾸기, 인물 외형 임의 변경
- 사람 승인 없이 크레딧 소비 설정 변경
- 얼굴이 실존 인물과 닮도록 지시하기, 실제 회사 로고 넣기
- 이 지시문에 없는 컷 만들기
