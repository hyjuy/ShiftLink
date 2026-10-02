-- ShiftLink 이력·분석 DB (Aiven MySQL 8.4)
-- 출처: docs/planning/최종 통합본(고도화 v1.1)(codex).md §4.11 — 7개 테이블, ID·해시·지표·메타만 (원문·judge 코멘트 미적재)
-- 중복 방지: 같은 논리 키 + 같은 해시는 무시, 같은 키 + 다른 해시는 업로드 쪽에서 충돌로 보류 (§4.11 운영 조건 3)
-- 적용: python db/apply_schema.py

CREATE TABLE IF NOT EXISTS pipeline_run (
  run_id          VARCHAR(64)  NOT NULL PRIMARY KEY,
  version         VARCHAR(64)  NOT NULL,
  stage           ENUM('P0','P1','P2','P3','P4','P5','P6') NOT NULL,
  started_at      DATETIME(3)  NOT NULL,
  ended_at        DATETIME(3)  NULL,
  git_commit      CHAR(40)     NULL,
  generator_model VARCHAR(128) NULL,
  judge_model     VARCHAR(128) NULL,
  seed            BIGINT       NULL,
  status          VARCHAR(32)  NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_version (
  version          VARCHAR(64) NOT NULL,
  split            ENUM('kb','dev','sealed') NOT NULL,
  record_count     INT         NOT NULL,
  manifest_sha256  CHAR(64)    NOT NULL,
  sealed_at        DATETIME(3) NULL,
  sealed_by        VARCHAR(32) NULL,
  PRIMARY KEY (version, split)
);

CREATE TABLE IF NOT EXISTS record_index (
  record_id       VARCHAR(32)  NOT NULL,
  kind            ENUM('card','event','artifact') NOT NULL,
  version         VARCHAR(64)  NOT NULL,
  split           ENUM('kb','dev','sealed') NOT NULL,
  tacit_type      VARCHAR(8)   NULL,
  equipment       VARCHAR(16)  NULL,
  persona_id      VARCHAR(64)  NULL,
  safety_flag     BOOLEAN      NOT NULL DEFAULT FALSE,
  status          VARCHAR(32)  NOT NULL,
  content_sha256  CHAR(64)     NOT NULL,
  uploaded_at     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (record_id, kind, version)
);

CREATE TABLE IF NOT EXISTS quality_metric (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id       VARCHAR(64)  NOT NULL,
  metric_name  VARCHAR(64)  NOT NULL,
  scope        VARCHAR(32)  NOT NULL,
  value        DOUBLE       NOT NULL,
  threshold    DOUBLE       NULL,
  passed       BOOLEAN      NULL,
  UNIQUE KEY uq_quality (run_id, metric_name, scope)
);

CREATE TABLE IF NOT EXISTS judge_log (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  record_id    VARCHAR(32)  NOT NULL,
  judge_model  VARCHAR(128) NOT NULL,
  criterion    VARCHAR(64)  NOT NULL,
  score        DOUBLE       NOT NULL,
  run_id       VARCHAR(64)  NOT NULL,
  UNIQUE KEY uq_judge (record_id, judge_model, criterion, run_id)
);

CREATE TABLE IF NOT EXISTS human_review (
  id           BIGINT AUTO_INCREMENT PRIMARY KEY,
  record_id    VARCHAR(32)  NOT NULL,
  reviewer     VARCHAR(16)  NOT NULL,  -- 코드값(R-01 등), 실명 금지
  decision     VARCHAR(16)  NOT NULL,
  reason_code  VARCHAR(32)  NULL,
  reviewed_at  DATETIME(3)  NOT NULL,
  UNIQUE KEY uq_review (record_id, reviewer, reviewed_at)
);

CREATE TABLE IF NOT EXISTS eval_result (
  id          BIGINT AUTO_INCREMENT PRIMARY KEY,
  run_id      VARCHAR(64)  NOT NULL,
  item_id     VARCHAR(32)  NOT NULL,
  mode        ENUM('query','handover') NOT NULL,
  metric      VARCHAR(32)  NOT NULL,  -- 근거적중/조건불일치/안전누락/지식없음
  value       DOUBLE       NOT NULL,
  model_plan  ENUM('A','B','C') NOT NULL,
  UNIQUE KEY uq_eval (run_id, item_id, metric, model_plan)
);

-- 인계 기록 (9/29 추가). 필드 출처: docs/design/B_data.md "HandoverRecord".
-- §4.11 원칙대로 원문(memo_text, open_items[].text)은 해시만, 정답(expected_open_items)은 적재하지 않는다.
-- 중복 키: (handover_id, version). 같은 키 + 같은 content_sha256 = 중복 무시, 다른 해시 = 충돌 보류.
CREATE TABLE IF NOT EXISTS handover_record (
  handover_id                 VARCHAR(16)  NOT NULL,  -- ^HO-\d{4}$
  version                     VARCHAR(32)  NOT NULL,
  shift_from                  ENUM('A','B','C') NOT NULL,
  shift_to                    ENUM('A','B','C') NOT NULL,
  shift_date                  DATE         NOT NULL,
  created_at                  DATETIME(3)  NOT NULL,
  author_persona_id           VARCHAR(16)  NOT NULL,  -- V-01 등 코드값
  equipment                   VARCHAR(16)  NULL,       -- 카메라 분류 클래스(HPU/GR/RT/CV)
  event_ids                   JSON         NOT NULL,
  linked_action_executed_ids  JSON         NOT NULL,
  memo_sha256                 CHAR(64)     NOT NULL,
  content_sha256              CHAR(64)     NOT NULL,
  is_synthetic                BOOLEAN      NOT NULL DEFAULT TRUE,
  uploaded_at                 DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  PRIMARY KEY (handover_id, version)
);

CREATE TABLE IF NOT EXISTS handover_item (
  handover_id  VARCHAR(16)  NOT NULL,
  version      VARCHAR(32)  NOT NULL,
  item_id      VARCHAR(32)  NOT NULL,
  status       ENUM('open','in_progress','done','withdrawn','needs_recheck') NOT NULL,
  due_shift    ENUM('A','B','C') NULL,
  basis_ids    JSON         NOT NULL,
  text_sha256  CHAR(64)     NOT NULL,
  PRIMARY KEY (handover_id, version, item_id),
  FOREIGN KEY (handover_id, version) REFERENCES handover_record (handover_id, version)
);

-- PDA 인계 원본 업로드 (10/2 추가, 시연용). Jetson SQLite handover_outbox -> shiftlink/mes/uploader.py.
-- §4.11 예외: 시연 데이터가 전부 합성(is_synthetic)이라 메모 원문(payload.memo_text)을 올려 다음 조 화면이 읽는다.
-- 실제 현장 데이터면 원문 대신 content_sha256만 올린다. 같은 ID + 같은 해시 = 중복 무시, 다른 해시 = 충돌 보류.
CREATE TABLE IF NOT EXISTS handover_upload (
  handover_id     VARCHAR(64)  NOT NULL PRIMARY KEY,  -- PDA 'HO-' + UUID
  equipment_id    VARCHAR(32)  NULL,
  created_at      DATETIME(3)  NOT NULL,              -- Jetson 로컬 저장 시각(UTC)
  payload         JSON         NOT NULL,              -- /api/handover 본문 그대로
  content_sha256  CHAR(64)     NOT NULL,
  is_synthetic    BOOLEAN      NOT NULL DEFAULT TRUE,
  uploaded_at     DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3)
);
