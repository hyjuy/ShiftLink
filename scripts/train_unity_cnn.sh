#!/usr/bin/env bash
# Unity PDA 사진 → 설비 분류 CNN 한 번에: 분할 → 학습 → INT8 2종 → 시험셋 평가 → 결과 묶음.
# Linux GPU 서버(vast.ai PyTorch 템플릿 등)에서, 저장소 루트에서 실행한다. docs/guides/unity-cnn.md 1·2절과 같은 명령이다.
#
#   bash scripts/train_unity_cnn.sh <촬영 zip 경로 또는 구글 드라이브 공유 링크> [작업 폴더, 기본 ~/cnn]
#   EPOCHS=15 WORKERS=8 SKIP_INSTALL=1 bash scripts/train_unity_cnn.sh …
#
# 결과: <작업 폴더>/result.tgz (model, model-int8, model-int8conv, eval_*.json, counts.txt, train.log). PC로 받은 뒤 서버를 삭제한다.
# 사진 말고는 아무것도 올리지 않는다(.env·키·평가 문항 금지).
set -euo pipefail
SRC="$1"; W="${2:-$HOME/cnn}"; PY="${PY:-python3}"
EPOCHS="${EPOCHS:-15}"; WORKERS="${WORKERS:-$(( $(nproc) < 8 ? $(nproc) : 8 ))}"
mkdir -p "$W"

if [ -z "${SKIP_INSTALL:-}" ]; then  # requirements-vision.txt와 같은 버전(10/7 합성 시험·파이와 ONNX 내보내기를 맞춘다)
  "$PY" -m pip install -q --index-url https://download.pytorch.org/whl/cu124 --extra-index-url https://pypi.org/simple torch==2.6.0 torchvision==0.21.0
  "$PY" -m pip install -q onnx==1.18.0 onnxruntime==1.20.1 numpy==2.1.3 opencv-python-headless==4.10.0.84 gdown  # 서버엔 GUI 라이브러리가 없어 headless
fi

if [ -f "$SRC" ]; then cp "$SRC" "$W/captures.zip"; else "$PY" -m gdown --fuzzy "$SRC" -O "$W/captures.zip"; fi
rm -rf "$W/captures" "$W/unity-yolo" "$W/unity-cls"
"$PY" -m zipfile -e "$W/captures.zip" "$W/captures"

# 분할 전에 본다: 장수, 클래스, scene/session 수. unity_dataset은 같은 scene_id·session_id를 한 묶음으로 같은 split에 넣으므로
# scene이나 session이 몇 개뿐이면 split이 비거나 한쪽으로 쏠린다.
"$PY" - "$W/captures" <<'EOF' | tee "$W/counts.txt"
import json, sys
from collections import Counter
from pathlib import Path
root = Path(sys.argv[1])
pngs, metas = list(root.rglob("*.png")), [json.loads(p.read_text(encoding="utf-8")) for p in root.rglob("*.json")]
def area(o):
    x1, y1, x2, y2 = o.get("bbox_xyxy", [0, 0, 0, 0])
    return (x2 - x1) * (y2 - y1)
def cls(m):  # 가장 큰 설비 상자의 equipment_type(unity_cls와 같은 기준). 상자가 없으면 배경
    objs = [o for o in m.get("objects", []) if isinstance(o, dict)]
    return max(objs, key=area).get("equipment_type", "?") if objs else "(배경)"
print(f"PNG {len(pngs)} · JSON {len(metas)}")
print("scene_id", len({m.get("scene_id") for m in metas}), "· session_id", len({m.get("session_id") for m in metas}))
print("class(대략)", dict(Counter(cls(m) for m in metas)))
EOF

"$PY" -m shiftlink.vision.unity_dataset --captures "$W/captures" --out "$W/unity-yolo" | tee -a "$W/counts.txt"
grep -q "WARNING: empty split" "$W/counts.txt" && { echo "split이 비었다 — scene/session을 늘리거나 dataset_split을 정한 뒤 다시"; exit 1; }
"$PY" -m shiftlink.vision.unity_cls --dataset "$W/unity-yolo" --out "$W/unity-cls" | tee -a "$W/counts.txt"

M="$W/model"
"$PY" -m shiftlink.vision.train --data "$W/unity-cls/train" --val-data "$W/unity-cls/val" --out "$M" \
  --epochs "$EPOCHS" --workers "$WORKERS" 2>&1 | tee "$W/train.log"
"$PY" -m shiftlink.vision.quantize --model "$M" --calib "$W/unity-cls/train"
"$PY" -m shiftlink.vision.quantize --model "$M" --calib "$W/unity-cls/train" --conv-only
for v in model model-int8 model-int8conv; do  # test는 학습·보정에 쓰지 않았다. 발표 수치(G5)는 여기서 나온다
  "$PY" -m shiftlink.vision.evaluate --model "$W/$v/model.onnx" --data "$W/unity-cls/test" --json "$W/eval_$v.json"
done

tar -C "$W" -czf "$W/result.tgz" model model-int8 model-int8conv eval_model.json eval_model-int8.json eval_model-int8conv.json counts.txt train.log
echo "끝: $W/result.tgz — PC로 받은 뒤 서버를 삭제(Destroy)한다"
