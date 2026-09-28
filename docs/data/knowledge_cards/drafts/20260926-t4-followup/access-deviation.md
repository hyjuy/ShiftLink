# 정보 접근 편차 기록

2026-09-26 연구 작업 중 최초 설계 담당 `/root/experiment_design`이 `functions.exec` → `exec_command`의 전체 `Get-Content`로 `docs/data/reference/00_plant_and_relations.json`을 읽었다. 출력에 `event_prototypes`의 sealed 지정 프로토타입 요약 메타데이터 1건이 우발 노출됐다고 보고했다. 이 접근은 사용자의 기존 sealed/holdout 비열람 제약에 맞지 않는다. sealed 사건 원문·holdout 파일을 열람했다는 보고는 없다. 그렇다고 비노출을 충족했다고 보고하지 않는다.

노출을 보고받은 즉시 해당 에이전트의 설계 작업을 중단했다. 에이전트는 산출 파일이 없음을 보고하고 종료했다. 요약의 사건 내용은 상위 에이전트에게 재전송하지 않았으며 이 문서에도 재현하지 않는다. 오염된 컨텍스트의 설계·실행 결과는 사용하지 않았다.

상위 에이전트는 JSON에서 `equipment_types`, `equipment`, `relations` 세 키만 기계적으로 투영한 [catalog-projection.json](catalog-projection.json)을 생성했다. 원본 전체 내용을 모델 출력으로 재노출하지 않았다. 대체 작성자 `/root/experiment_design_fresh`는 `fork_turns=none`의 새 컨텍스트로 시작했고 원본 카탈로그·sealed/holdout 열람을 금지했으며 장비 투영본만 허용했다. 카드 내용 검토자도 같은 비열람 제한을 받았다.

따라서 최종 설계에 이 요약을 재료로 사용한 근거는 없고 노출된 작성자의 산출물도 없다. 다만 이번 작업 전체에 대해 “기존 sealed 메타데이터를 한 번도 보지 않았다”라고 주장할 수 없다. 접근 제한은 도구 사용 지시와 새 컨텍스트 분리에 기반하며 OS 보안 격리가 아니다. 이후 실행 역할에도 원본 카탈로그를 제공하지 않는다.
