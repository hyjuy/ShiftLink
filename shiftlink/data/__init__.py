"""Legacy stage planner; reviewed draft generation lives in .generation."""

import argparse
import json
from collections.abc import Sequence

# 실행 순서를 정의한다. 문서의 소수점 단계(P1.5 등)는 승인 전 제안이므로 제외한다.
STAGES = ("P0", "P1", "P2", "P3", "P4", "P5", "P6")


def main(argv: Sequence[str] | None = None) -> int:
    # argv=None이면 터미널 인자를 읽고, 테스트에서는 인자 목록을 직접 전달한다.
    parser = argparse.ArgumentParser(
        prog="python -m shiftlink.data",
        description="Print a pipeline plan only; no data is generated or saved.",
        allow_abbrev=False,
    )
    parser.add_argument("command", choices=("all",), help="plan stages through P6")
    # --from은 파일 경로가 아닌 재개 단계다. 내부에서는 start_stage라는 이름으로 쓴다.
    # choices로 잘못된 단계 입력을 거부하고, 생략하면 P0부터 전체 계획을 만든다.
    parser.add_argument(
        "--from", dest="start_stage", choices=STAGES, default="P0",
        help="resume at this stage, inclusive (default: P0)",
    )
    # 현재는 생성 설정만 전달한다. --version은 프로그램 버전 조회가 아닌 데이터셋 버전이다.
    parser.add_argument("--seed", type=int, default=0, help="generation seed (default: 0)")
    parser.add_argument("--version", default="0.9", help="dataset version (default: 0.9)")
    # 인자 오류는 argparse가 stderr에 설명을 출력하고 종료 코드 2로 처리한다.
    args = parser.parse_args(argv)
    # 아직 생성·저장은 수행하지 않는다. planned 상태로 실행 계획임을 명시한다.
    print(
        json.dumps(
            {
                "status": "planned",
                "command": args.command,
                "from": args.start_stage,
                # 시작 단계를 포함해 마지막 P6까지 순서대로 선택한다.
                "stages": STAGES[STAGES.index(args.start_stage):],
                "seed": args.seed,
                "version": args.version,
            },
            ensure_ascii=False,
        )
    )
    # 0은 계획 출력 성공을 뜻하며, 실제 데이터 생성 완료를 뜻하지 않는다.
    return 0
