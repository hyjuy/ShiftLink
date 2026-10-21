# ShiftLink 아키텍처 다이어그램 (2026-10-21)

발표·보고서용 그림 11장(D0~D10). 장마다 HTML 원본, SVG, PNG(2배)가 있다. 그림 안의 "근거 기반 답변 엔진"은 코드의 S30h(`shiftlink/rag2`)다.

| # | 파일 | 내용 |
|---|---|---|
| D0 | `d0-overview` | 전체 파이프라인 |
| D1 | `d1` | 현장 배치도 |
| D2 | `d2` | 질의 한 건의 흐름 |
| D3 | `d3` | 답변 엔진의 판단 |
| D4 | `d4` | MES 구성 |
| D5 | `d5` | PDA 사용 흐름 |
| D6 | `d6` | 얼굴 로그인 |
| D7 | `d7` | 설비 인식 |
| D8 | `d8` | 데이터 적재 |
| D9 | `d9` | 모듈 구성 |
| D10 | `d10` | 모델 개발과 평가 |

## 근거 대조표 (origin/main 6b7b7e4 기준)

D0~D4도 같은 방식으로 코드·설정을 보고 그렸지만, 이 표에는 아직 D5~D10만 있다.
재생성: `python gen.py d1 … d10`(D0은 `d0-overview.html` 직접 수정) → diagram-design 스킬의 `self_check.py`, `export_png.py <f>.html <f>.png 2`, `export_svg.py`.

### D5 PDA 사용 흐름
| 요소 | 근거 |
|---|---|
| 화면 순서 ①~⑥ | `shiftlink/mes/web/pda.html` 화면 id: s-login·s-face → s-scan·s-manual → s-ctx → s-chat → s-resolve → s-reportWrite·s-hoNew → s-outbox |
| 답 보류 | s-empty "해당 지식 없음 … 추측으로 답하지 않습니다" |
| 작업자 B 흐름, Unity 2인 | 사용자 확인 (10/21), s-handover "인계 사항" |

### D6 얼굴 로그인
| 요소 | 근거 |
|---|---|
| YuNet 2023mar, 검출 점수 0.8 | `shiftlink/face/engine.py` `FaceEngine.load(score_threshold=0.8)` |
| SFace 2021dec | `face/__init__.py` `MODEL_VERSION`, `engine.py` |
| 코사인 ≥ 0.363 | `face/__init__.py` `DEFAULT_THRESHOLD` (현장 튜닝 전 값) |
| 5장 중 3장 | `FACE_FRAMES=5`, `FACE_NEED=3`, `verify.py` |
| 임베딩만 저장, 사번.npz, 권한 600 | `face/store.py` docstring |
| 등록 8장, 동의 철회 삭제 | `face/__main__.py` `enroll --shots 8`, `delete` |
| 프록시 경유 | `pda/__main__.py` `_MAX_FACE_JPEG` |
| 사번 로그인 대체 | pda.html s-account |

### D7 설비 인식
| 요소 | 근거 |
|---|---|
| 숫자키 1~6 촬영 | `vision/capture.py` |
| MobileNetV3-Small → ONNX, 6클래스 | `vision/train.py`, `vision/__init__.py` `CLASSES` |
| INT8 정적 양자화, 보정은 train 사진 | `vision/quantize.py` |
| 평가 항목 | `vision/evaluate.py` |
| 0.8 · 5프레임, :8090, `/api/equipment/scan` | `vision/classify.py` `Stabilizer`, `--listen 8090`, `post_scan` |
| Jetson에는 클래스명만 | `vision/__init__.py` docstring |

### D8 데이터 적재
| 요소 | 근거 |
|---|---|
| 테이블 묶음 | `mes/storage.py` CREATE TABLE 목록 (묶음 이름은 그림용) |
| 업로드 대상 2개, 재시도, 해시 conflict | `mes/uploader.py` 1~6행, `upload_pending` |
| 해결 기록 실린 인계 로컬 보류 | `mes/uploader.py` 20행 (10/13 결정) |
| 30초 주기 | `mes/uploader.py` `--interval` 기본 30, `deploy/install_uploader.sh` `INTERVAL=30` |
| 인계 보드 :8810 읽기 전용 | `mes/handover_board.py` |

### D9 모듈 구성
| 요소 | 근거 |
|---|---|
| 줄 수, import 화살표 | `imports.py` 실행 결과 (origin/main `shiftlink/`) |
| 생략한 연결 | data→rag 1, rag→edge 1, edge→rag 1. 패키지 내부 상대 import(mes→configuration 등)는 집계 오류로 제외 |
| 역할 이름 | 각 `__init__.py` docstring (rag2 = S30h 엔진, agent = route·retrieval·검증) |

### D10 모델 개발·평가
| 요소 | 근거 |
|---|---|
| 합성 질문 655개·0~3점, LoRA r=16·3에폭, Q4_K_M 1.5GB, llama.cpp | `docs/guides/sft-judge-model.md` |
| 사전 등록, 블라인드 셋 | 같은 문서 "채택 근거" |
| 60문항 동결, Codex는 해시만 | 저장소 밖 봉인 셋 기록 (10/20 동결) |
| X/Y 이름 가린 비교표 | `make_review.py` (blind_key 분리) |
| ollama create | 같은 문서 "Jetson에 등록" |
| 레인 배치(누가 무엇을) | 작업 기록 기준. 사용자 확인 필요 |
