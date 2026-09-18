#!/usr/bin/env bash
# 플랜 B 연속 20건 예비측정 — 변수는 power_mode 하나만 변경 (15W / 25W)
# 사용: ./bench/run_power_mode_bench.sh 25W
#       ./bench/run_power_mode_bench.sh 15W
set -euo pipefail

MODE="${1:?usage: $0 15W|25W}"
MODEL="qwen2.5:3b-instruct-q4_K_M"
N_RUNS=20
OUT_DIR="${OUT_DIR:-$HOME/shiftlink-bench}"
TSV_LOCAL="${TSV_LOCAL:-}"  # 비우면 stdout에 TSV 한 줄만 출력
mkdir -p "$OUT_DIR"
RAW="$OUT_DIR/power_${MODE}_$(date +%Y%m%d_%H%M%S).jsonl"

case "$MODE" in
  15W) MODE_ID=0 ;;
  25W) MODE_ID=1 ;;
  *) echo "MODE must be 15W or 25W" >&2; exit 1 ;;
esac

echo "== preflight ==" >&2
free -h >&2
ps aux | grep -E 'vscode-server|cursor-server' | grep -v grep >&2 || echo "(no vscode/cursor-server)" >&2
who >&2 || true

echo "== set power mode $MODE (id=$MODE_ID) ==" >&2
CUR_MODE="$(nvpmodel -q 2>/dev/null | awk -F': ' '/NV Power Mode/{print $2; exit}')"
if [[ "$CUR_MODE" == "$MODE" ]]; then
  echo "already in $MODE — skip nvpmodel" >&2
else
  if sudo -n nvpmodel -m "$MODE_ID" 2>/dev/null; then
    echo "switched to $MODE" >&2
  else
    echo "ERROR: need sudo to switch $CUR_MODE -> $MODE (passwordless sudo nvpmodel required)" >&2
    exit 2
  fi
fi
nvpmodel -q >&2

# 모델 warm-load (성공률 측정에서 제외)
echo "== warm load ==" >&2
curl -sS http://127.0.0.1:11434/api/generate \
  -d "{\"model\":\"$MODEL\",\"prompt\":\"ping\",\"stream\":false,\"keep_alive\":\"10m\"}" \
  >/dev/null || true
sleep 2

SCHEMA='{"type":"object","properties":{"equipment":{"type":"string"},"symptom":{"type":"string"}},"required":["equipment","symptom"]}'
PROMPT='다음 관측을 JSON으로만 답하라. equipment는 RT-01, symptom은 이상 소음 발생.'

ok=0
declare -a LATENCIES=()
temps=()

echo "== runs n=$N_RUNS ==" >&2
: > "$RAW"
for i in $(seq 1 "$N_RUNS"); do
  # 온도 샘플 (가능하면)
  TEMP=""
  if command -v tegrastats >/dev/null 2>&1; then
    TEMP=$(timeout 2 tegrastats --interval 1000 | head -1 | grep -oE 'cpu@[0-9]+' | head -1 | tr -dc '0-9' || true)
  fi

  START_NS=$(date +%s%N)
  RESP=$(curl -sS http://127.0.0.1:11434/api/generate \
    -H 'Content-Type: application/json' \
    -d "{\"model\":\"$MODEL\",\"prompt\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$PROMPT"),\"stream\":false,\"format\":$SCHEMA,\"options\":{\"num_predict\":64},\"keep_alive\":\"10m\"}" \
    || echo '{"error":"curl_failed"}')
  END_NS=$(date +%s%N)
  LAT_S=$(python3 -c "print( ($END_NS-$START_NS)/1e9 )")

  # 구조화 성공 판정: response 필드가 파싱 가능한 JSON이고 equipment/symptom 키 존재
  PASS=$(python3 - <<'PY' "$RESP"
import json,sys
raw=sys.argv[1]
try:
    o=json.loads(raw)
    if o.get("error"):
        print(0); raise SystemExit
    text=o.get("response","")
    j=json.loads(text) if isinstance(text,str) else text
    ok=isinstance(j,dict) and "equipment" in j and "symptom" in j
    print(1 if ok else 0)
except Exception:
    print(0)
PY
)

  echo "{\"i\":$i,\"pass\":$PASS,\"latency_s\":$LAT_S,\"temp_c\":\"$TEMP\",\"raw\":$RESP}" >> "$RAW"
  LATENCIES+=("$LAT_S")
  if [[ -n "$TEMP" ]]; then temps+=("$TEMP"); fi
  if [[ "$PASS" == "1" ]]; then ok=$((ok+1)); fi
  echo "run $i/$N_RUNS pass=$PASS lat=${LAT_S}s temp=${TEMP:-NA}" >&2
done

RATE=$(python3 -c "print(round($ok/$N_RUNS, 4))")
P95=$(python3 - <<'PY' "${LATENCIES[@]}"
import sys
xs=sorted(float(x) for x in sys.argv[1:])
if not xs: print(""); raise SystemExit
# nearest-rank p95
k=max(0, min(len(xs)-1, int(0.95*(len(xs)-1)+0.5)))
print(round(xs[k], 4))
PY
)
TEMP_AVG=""
if ((${#temps[@]})); then
  TEMP_AVG=$(python3 -c "import sys; xs=[float(x) for x in sys.argv[1:]]; print(round(sum(xs)/len(xs),1))" "${temps[@]}")
fi

VERDICT="discard"
# 주 지표: 구조화 출력 성공률. 예비측정 keep 기준: >=0.9
python3 -c "import sys; sys.exit(0 if float(sys.argv[1])>=0.9 else 1)" "$RATE" && VERDICT="keep" || VERDICT="discard"

DATE=$(date +%F)
LINE=$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$DATE" "cursor" "power_mode" "$MODE" "15" "$N_RUNS" \
  "structured_output_success_rate" "$RATE" "$P95" "$TEMP_AVG" "$VERDICT" \
  "planB $MODEL; raw=$RAW; preflight check done")

echo "$LINE"
if [[ -n "$TSV_LOCAL" ]]; then
  echo "$LINE" >> "$TSV_LOCAL"
fi

echo "== done rate=$RATE p95=${P95}s temp_avg=${TEMP_AVG:-NA} verdict=$VERDICT ==" >&2
