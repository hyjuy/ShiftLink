# Unity 제조 공정 초기 구현 검증 — 2026-10-06

사용자 요청: 현재 MES 등록 장비 전체를 구현할 Unity 팀을 구성하고 제조 공정부터 시작한다. 후속 질문의 1주일 일정은 단순 모형·합성 이미지 학습·가상 환경 인식·PDA 시연을 목표로 한다. 실제 현장 정확도 보장은 포함하지 않는다.

## 구현 범위

- MES 기준정보·API 조사, Unity 공간·장비 담당, 통합·검증 담당으로 역할을 나눴다.
- 기본 장비 10대, 유형 6종, 소재 주경로와 스크랩 분기를 확인했다.
- scripts/export_unity_mes.py는 기존 Configuration 변환·검증을 재사용한다.
- --mes-url을 지정하면 실제 /api/config의 활성 구성과 고유 ID를 보존한다. 실패 시 기본 카탈로그로 대체하지 않는다.
- Unity 코드는 유형별 시연 모형, 경로·공급 관계선, 카메라 이동, 장비 정보 선택, MES 상태·코일 위치 조회를 구현했다. 비활성 장비도 배치하되 실시간 상태와 구분한다.
- 실제 Unity 에디터에서 메뉴로 장면을 생성하는 방식이다. 아직 저장된 .unity 장면 및 실행 빌드는 생성하지 않았다.

## TDD 증거

| 단계 | 실행 명령 | 실제 결과 |
|---|---|---|
| RED | python -B -m unittest tests.test_unity_mes_export -v | 7 tests, FAILED (failures=12); exporter 미구현으로 실패. 추가 실패 수는 subTest 포함 |
| GREEN | python -B -m unittest tests.test_unity_mes_export -v | 7 tests, OK |
| CLI·URL 오류 검증 추가 | 아래 coverage 실행 | 9 tests, OK |
| 기본 JSON 생성 | python -B scripts/export_unity_mes.py | Exported 10 equipment (catalog) |

커버리지는 기존 .test-deps의 coverage를 사용했다.

```powershell
python -B -c "import sys; sys.path.insert(0, '.test-deps'); from coverage.cmdline import main; raise SystemExit(main())" run --data-file artifacts/unity-manufacturing.coverage --include "*/scripts/export_unity_mes.py" -m unittest tests.test_unity_mes_export -v
python -B -c "import sys; sys.path.insert(0, '.test-deps'); from coverage.cmdline import main; raise SystemExit(main())" report --data-file artifacts/unity-manufacturing.coverage -m
```

結果: scripts/export_unity_mes.py 54 statements, 1 missed, 98% line coverage. 이 수치는 Python 내보내기 도구만 대상으로 하며 Unity C# 커버리지나 프로젝트 전체 커버리지가 아니다.

## 검증한 보장

| 보장 | 검증 종류 |
|---|---|
| 기본 장비 10대, 주경로와 분기를 빠짐없이 내보냄 | 단위 + 파일 왕복 |
| 실제 MES HTTP 응답의 활성 구성 우선, 추가 장비 11대 구성 보존 | HTTP 통합 |
| 장비·자산 ID와 비활성 장비 보존 | 단위 |
| 잘못된 경로·중복 ID·잘못된 응답 거부 | 단위 |
| 연결 실패 시 자동 카탈로그 대체 금지 | 오류 경로 |
| 잘못된 구성·없는 카탈로그로 기존 출력 훼손 금지 | 오류 경로 |
| 명령행 성공 실행 및 오류 종료 코드 | CLI 종단간 |
| HTTP(S) 외 주소 및 잘못된 출처 거부 | 단위 |

## 알려진 제한

실행 가능한 Unity.exe와 C# 컴파일러가 없어 Unity 컴파일·렌더링·조작·상태 조회를 실행 검증하지 못했다. 2021.3.17f1 설치 폴더는 modules.json만 포함한다. Unity 설치 후 메뉴로 장면을 생성하고 Play 동작, 상태 변경, 연결 끊김, config_id 불일치 처리를 검증해야 한다.

장비 외형·좌표는 가상 모형이다. 기본 MES는 압연 본체를 제외한 보조설비를 다룬다. MES 코일 엔진은 주경로를 사용하므로 스크랩 분기의 실제 이송 동작은 포함되지 않는다. AI 학습용 촬영·정답 라벨 생성·모델 학습·PDA 영상 전송은 이후 단계다.

기존 저장소에 진행 중인 병합이 있어 새 브랜치 생성이 fatal: cannot switch branch while merging으로 거부됐다. 기존 병합과 사용자 수정 파일은 건드리지 않았으며 TDD 단계 커밋은 만들지 않았다. 이번 작업 파일은 모두 새 파일이다.

