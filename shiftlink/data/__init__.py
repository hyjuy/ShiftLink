"""Plan the data pipeline; generation and storage are not implemented yet.

Contract (통합본 v1.1 §4.7.1 단계 구성, §4.7.10 재현성 시연, 개발계획 §2):
- `python -m shiftlink.data all [--from Pn] [--seed n] [--version v]` prints a
  plan as JSON. Nothing is generated, validated, or saved.
- **Exit code 0 means the plan was printed, never that data was produced.**
  Every stage therefore reports `implemented: false` in the detailed plan.
- Stage numbers P0~P6 are the approved set. The decimal stages proposed in
  docs/design/B_data.md §B7 (P1.5·P2.5·P3.5) are `[신규 제안]` and are rejected
  with that reason rather than silently accepted.
- Seed is recorded, not a reproducibility claim: §4.7.10 states that fixing the
  seed does not make a new LLM run byte-identical.
"""

import argparse
import json
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class StageSpec:
    """One row of the 4.7.1 pipeline table."""

    stage: str
    title: str
    outputs: tuple[str, ...]
    owner: str
    # Every stage is still planning-only (개발계획 §2 "P1~P6 실행·저장·재개·QC 구현" 남음).
    implemented: bool = False


# 4.7.1 표 그대로. B7의 확장 산출물 목록은 [신규 제안]이라 반영하지 않는다.
STAGE_SPECS: tuple[StageSpec, ...] = (
    StageSpec("P0", "공개 시드 수집", ("seeds/",), "전혜민"),
    StageSpec("P1", "가상 설비 사전", ("plant/L1.yaml",), "유현준·전혜민"),
    StageSpec("P2", "베테랑 페르소나", ("personas/*.yaml",), "전혜민·유현준"),
    StageSpec(
        "P3",
        "사건·지식 원장",
        ("ledger/events.jsonl", "ledger/cards.jsonl"),
        "최재영(생성)·전혜민(검수)",
    ),
    StageSpec("P4", "산출물 생성", ("artifacts/*.jsonl",), "최재영"),
    StageSpec("P5", "품질 검증", ("qc/report.json",), "전혜민(주)·최재영"),
    StageSpec(
        "P6",
        "분할·버전·데이터 카드",
        ("splits/{kb,dev,sealed}.json", "DATASET_CARD.md", "manifest.json"),
        "유현준·허재원",
    ),
)

# 실행 순서를 정의한다. 문서의 소수점 단계(P1.5 등)는 승인 전 제안이므로 제외한다.
STAGES = tuple(spec.stage for spec in STAGE_SPECS)
SPEC_BY_STAGE = {spec.stage: spec for spec in STAGE_SPECS}

# docs/design/B_data.md §B7-1 [신규 제안]. 거부하되 왜 거부하는지 말해 준다.
PROPOSED_STAGES: dict[str, str] = {
    "P1.5": "관계·매뉴얼 기준정보 (B7 신규 제안, 미승인)",
    "P2.5": "원형 사건 카탈로그·분할 사전 배정 (B7 신규 제안, 미승인)",
    "P3.5": "행동·결과·인계·개정 후보 (B7 신규 제안, 미승인)",
}


def main(argv: Sequence[str] | None = None) -> int:
    # argv=None이면 터미널 인자를 읽고, 테스트에서는 인자 목록을 직접 전달한다.
    parser = argparse.ArgumentParser(
        prog="python -m shiftlink.data",
        description="Print a pipeline plan only; no data is generated or saved.",
        allow_abbrev=False,
    )
    parser.add_argument("command", choices=("all",), help="plan stages through P6")
    # --from은 파일 경로가 아닌 재개 단계다. 내부에서는 start_stage라는 이름으로 쓴다.
    # choices 대신 직접 검증해서 미승인 제안 단계와 오타를 구분해 알린다.
    parser.add_argument(
        "--from", dest="start_stage", default="P0", metavar="STAGE",
        help=f"resume at this stage, inclusive: {' '.join(STAGES)} (default: P0)",
    )
    # 현재는 생성 설정만 전달한다. --version은 프로그램 버전 조회가 아닌 데이터셋 버전이다.
    parser.add_argument("--seed", type=int, default=0, help="generation seed (default: 0)")
    parser.add_argument("--version", default="0.9", help="dataset version (default: 0.9)")
    parser.add_argument(
        "--detail", action="store_true",
        help="add the 4.7.1 stage table (title, outputs, owner, implemented)",
    )
    # 인자 오류는 argparse가 stderr에 설명을 출력하고 종료 코드 2로 처리한다.
    args = parser.parse_args(argv)

    if args.start_stage not in SPEC_BY_STAGE:
        if args.start_stage in PROPOSED_STAGES:
            parser.error(
                f"--from {args.start_stage}: 미승인 제안 단계 — "
                f"{PROPOSED_STAGES[args.start_stage]}. 승인된 단계: {' '.join(STAGES)}"
            )
        parser.error(
            f"--from {args.start_stage}: unknown stage. 승인된 단계: {' '.join(STAGES)}"
        )

    # 시작 단계를 포함해 마지막 P6까지 순서대로 선택한다.
    stages = STAGES[STAGES.index(args.start_stage):]
    # 아직 생성·저장은 수행하지 않는다. planned 상태로 실행 계획임을 명시한다.
    plan = {
        "status": "planned",
        "command": args.command,
        "from": args.start_stage,
        "stages": list(stages),
        # 기록용이며 새 생성의 바이트 동일성을 뜻하지 않는다(4.7.10).
        "seed": args.seed,
        "version": args.version,
    }
    if args.detail:
        plan["plan"] = [_stage_detail(stage) for stage in stages]
    print(json.dumps(plan, ensure_ascii=False))
    # 0은 계획 출력 성공을 뜻하며, 실제 데이터 생성 완료를 뜻하지 않는다.
    return 0


def _stage_detail(stage: str) -> dict[str, object]:
    spec = SPEC_BY_STAGE[stage]
    return {
        "stage": spec.stage,
        "title": spec.title,
        "outputs": list(spec.outputs),
        "owner": spec.owner,
        "implemented": spec.implemented,
    }
