# A 파이프라인 · B Ollama 어댑터 통합 확인 — 2026-09-24

기준 브랜치: `fix/ollama-validation-boundaries-20260924` (`fd3f982`에서 시작). 아래 결과는 이번 작업에서 실제 실행한 명령만 기록한다. `docs/planning/demo-deliverables-and-acceptance-20260924.md`는 A/B 1~6단계가 아닌 별도 데모 계획이므로 변경하지 않았다.

## 1. 호출 계약 확인

- `FixedPipeline.run(payload)`이 `route_request()`로 `QueryRequest` 또는 `HandoverRequest`를 만든다. `request`는 Pydantic 객체이며 `observations`는 `Observation` 객체 목록이다.
- 도구 호출 후 `model(mode=..., request=..., tool_results=..., retry=False)`를 호출한다. `OllamaModel`은 현재 `query`만 지원하고 `{"answer": str, "cited_card_ids": list[str]}`를 반환한다.
- A가 이번 검색 카드에 있는 인용 ID, ID 형식, 중복·빈 목록, 조건 미확인 여부를 검증한다. 빈 query 검색 결과는 모델 호출 없이 `no_knowledge`로 끝난다.
- `ValueError` 또는 출력 검증 실패는 `retry=True`로 최대 한 번 재호출한다. `TimeoutError`, `ConnectionError`, `NotImplementedError`는 재시도하지 않고 보류한다. 총 모델 호출 상한은 2회다.

## 2~3. A와 B의 독립 테스트

`.test-deps`를 Python 경로에 추가하고 pytest 캐시를 끈 상태에서 실행했다.

| 대상 | 명령의 테스트 파일 | 결과 |
|---|---|---|
| A 파이프라인·검색·응답 | `tests/test_router_pipeline.py tests/test_retrieval_response.py` | 107 passed |
| B Ollama 어댑터·CLI | `tests/test_edge_ollama.py tests/test_edge_cli.py` | 23 passed |

정상 출력, 형식 오류, 잘못된 인용, 타임아웃, 연결 오류, 재시도 분기가 포함된다. 이 테스트들은 모델 서버 대신 결정적 대역을 사용한다.

```powershell
python -X utf8 -c "import sys; sys.path.insert(0, '.test-deps'); import pytest; raise SystemExit(pytest.main(['tests/test_router_pipeline.py', 'tests/test_retrieval_response.py', '-q', '-p', 'no:cacheprovider', '--tb=short']))"
python -X utf8 -c "import sys; sys.path.insert(0, '.test-deps'); import pytest; raise SystemExit(pytest.main(['tests/test_edge_ollama.py', 'tests/test_edge_cli.py', '-q', '-p', 'no:cacheprovider', '--tb=short']))"
```

## 4. PC 실모델 질의

`F-e2e-001`을 `python -m shiftlink.edge --case F-e2e-001 --timeout 3`에 해당하는 진입점으로 실행했다. 결과는 **모델 연결 실패**였다. 종료 코드 1, `모델 출력: null`, `review_queue=True`, `wall_s=4.203`을 확인했다. `ollama` 명령이 PATH에 없고 `http://localhost:11434/api/tags`는 `WinError 10061`로 연결을 거부했다. 따라서 실제 모델의 답변·digest·지연은 이 실행에서 검증되지 않았다.

이후 PC에 Ollama 0.34.1이 설치됐다. `C:/Users/hyjuy/AppData/Local/Programs/Ollama/ollama.exe --version`과 `http://localhost:11434/api/version`이 모두 `0.34.1`을 반환했다. `ollama pull qwen2.5:3b-instruct-q4_K_M`이 `success`로 끝났고 `ollama list`의 ID `357c53fb659c`가 `models.lock`과 일치한다.

기본 서버(포트 11434)로 실행한 첫 질의는 종료 코드 1, `모델 출력: null`, `review_queue=True`, `wall_s=39.187`이었다. `ollama run qwen2.5:3b-instruct-q4_K_M 안녕하세요`로 원인을 분리해 보니 런너가 `500 Internal Server Error`, `exit status 0xc0000409`, `CUDA error: the provided PTX was compiled with an unsupported toolchain`으로 종료됐다. 이 기본 GPU 경로는 검증 실패다.

GPU는 NVIDIA GeForce MX150(2GB), 드라이버 560.94, 드라이버가 보고한 CUDA 12.6이었다(`nvidia-smi`). 별도 포트 11436에서 `OLLAMA_LLM_LIBRARY=cuda_v12`, `CUDA_VISIBLE_DEVICES=0`, `OLLAMA_VULKAN=0`으로 CUDA 12 런너를 지정해 재실행했지만 `F-e2e-001`은 종료 코드 1, `wall_s=22.625`로 다시 실패했다. 서버 로그는 `libdirs=ollama,cuda_v12`로 선택을 확인했고 같은 `unsupported toolchain` 오류를 기록했다. 시험용 GPU 서버는 종료했다.

별도 서버를 `CUDA_VISIBLE_DEVICES=-1`, `OLLAMA_VULKAN=0`, `OLLAMA_HOST=127.0.0.1:11435`로 시작했고 서버 로그의 `inference compute id=cpu library=cpu`, `ollama ps`의 `100% CPU`를 확인했다. 이 CPU 서버에서 실제 `FixedPipeline` + `OllamaModel` 질의가 성공했다. 실행 명령은 아래와 같다. `.test-deps`에 테스트용 Python 의존성이 있는 현재 저장소 환경을 사용했다.

```powershell
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:CUDA_VISIBLE_DEVICES = '-1'
$env:OLLAMA_VULKAN = '0'
Start-Process -FilePath 'C:/Users/hyjuy/AppData/Local/Programs/Ollama/ollama.exe' -ArgumentList 'serve' -WindowStyle Hidden
Start-Sleep -Seconds 5  # 서버 시작 대기
python -X utf8 -c "import sys; sys.path.insert(0, '.test-deps'); from shiftlink.edge.__main__ import main; raise SystemExit(main(['--case', 'F-e2e-001', '--host', 'http://127.0.0.1:11435', '--timeout', '120']))"
```

종료 코드 0, 모델 출력 `{"answer": "제조 현장에서 안전을 위해 중요한 규칙 중 하나는 이동 중인 블레이트를 만지지 않는 것이다.", "cited_card_ids": ["K-0108"]}`, `retry=false`, `latency_s=22.985`, `load_duration_s=7.125`, `eval_count=54`, `wall_s=23.000`이었다. 최종 `## 답변` 블록까지 표시됐고 `review_queue`는 걸리지 않았다. 다만 `블레이트`라는 표현은 현장용 문장으로 검수해야 한다.

같은 CPU 서버에서 `F-e2e-002`를 실행하니 모델 출력 `null`, `wall_s=0.016`, 종료 코드 0으로 `해당 지식 없음`을 반환했다. `F-e2e-001 --timeout 0.001`은 모델 출력 `null`, `wall_s=0.109`, 종료 코드 1, `review_queue`의 `모델 요청 시간 초과`로 끝났다. 두 실행 모두 CLI 진입점에 `--host http://127.0.0.1:11435`를 지정했다. 초단기 타임아웃은 오류 분기 확인용 설정이며 정상 운영 타임아웃이 아니다.

재시도 경로는 첫 번째 모델 응답만 `{"answer": "재시도 확인용 첫 응답", "cited_card_ids": ["K-9999"]}`로 주입하고 두 번째 호출을 실제 CPU Ollama에 전달해 확인했다. 파이프라인 호출의 `retry` 값은 `[false, true]`였고, 실제 모델의 두 번째 응답은 `K-0108`을 인용해 `review_queue=false`로 끝났다. 실모델 호출의 `latency_s=23.469`, `load_duration_s=7.911`, `eval_count=54`였다. 이 결과는 **실모델이 스스로 잘못된 인용을 생성했다는 뜻이 아니다**.

K-0108 픽스처 원문은 `Do not touch moving belt`이다. 두 실모델 답변에는 각각 `블레이트`, `브elt`가 나타났다. 카드 인용 검증은 통과했지만 한국어 문장 품질 검수에서는 부적합하다.

## 5. A+B 공동 통합 검증

실제 `FixedPipeline`, `OllamaModel`, `InMemoryToolProvider`와 개발용 F-e2e 픽스처를 사용하고 HTTP 응답만 제어했다. `tests/test_pipeline_ollama_integration.py`: **5 passed**.

```powershell
python -X utf8 -c "import sys; sys.path.insert(0, '.test-deps'); import pytest; raise SystemExit(pytest.main(['tests/test_pipeline_ollama_integration.py', '-q', '-p', 'no:cacheprovider', '--tb=short']))"
```

| 사례 | 관찰 결과 |
|---|---|
| 정상 `F-e2e-001` | HTTP 1회, K-0108 인용, 최종 `## 답변` 표시 |
| 빈 KB `F-e2e-002` | HTTP 0회, `no_knowledge=True` |
| 관측값 필수값 누락 | 입력 검증 오류, HTTP 0회 |
| 잘못된 인용 K-9999 | HTTP 2회, 두 번째 요청에 재시도 프롬프트, 최종 보류 |
| 타임아웃 | HTTP 1회, 재시도 없이 `모델 요청 시간 초과`로 보류 |

## 6. 미완료와 재실행

- GPU 런너는 CUDA 12 지정 후에도 같은 오류로 실패한다. 이번 성공 실측은 CPU 서버에서의 결과다. 드라이버 교체 같은 PC 시스템 변경은 이번 저장소 검증 범위에서 수행하지 않았다.
- 제어된 첫 오류 뒤 실제 모델로 재시도하는 경로는 성공했다. 실모델이 자발적으로 잘못된 인용을 낸 사례는 관측되지 않았다. 타임아웃은 위의 초단기 제한으로 실제 서버에서 확인했다.
- `블레이트`·`브elt` 표현은 원문과 대조해 부적합으로 판정했다. 한국어 카드 채택 또는 출력 문장 검수 정책이 적용되기 전에는 현장용 문장 품질을 완료로 표시할 수 없다.

## 7. 다른 PC의 GPU 실검증 인계

이 PC의 MX150(드라이버 560.94)에서는 GPU 런너가 시작하지 못했다. GPU 실검증은 Ollama 0.34.1이 지원하는 GPU와 드라이버를 갖춘 다른 PC에서 수행한다. compute capability 5.0~6.2 GPU라면 [Ollama 0.34.1 GPU 문서](https://github.com/ollama/ollama/blob/v0.34.1/docs/gpu.mdx)의 드라이버 570 이상 조건을 먼저 확인한다. 이 인계 항목은 아직 **미실행·미완료**다.

1. `ollama --version`이 `0.34.1`인지, `ollama list`의 `qwen2.5:3b-instruct-q4_K_M` ID가 `357c53fb659c`인지 확인한다.
2. 4절의 `F-e2e-001` 명령을 해당 PC의 Ollama 호스트로 실행한다. 기본 서버라면 `--host http://localhost:11434`를 사용한다.
3. 종료 코드, `모델 출력`, 인용 ID, `review_queue`, `wall_s`, `latency_s`, `ollama ps`의 `PROCESSOR`, GPU·드라이버 정보를 기록한다. CUDA 런너 오류가 없고 유효 인용이 최종 답변에 표시되는지 확인한다.
4. 결과를 CPU 실측과 별도 행으로 기록한다. 영어 개발 픽스처로 나온 한국어 문장은 현장용 품질 승인으로 간주하지 않는다.
