#!/usr/bin/env bash
# Unity PDA 사진 → 설비 분류 CNN 한 번에: (필요하면) 분할 → 학습 → INT8 2종 → 시험셋 평가 → 결과 묶음.
# Linux GPU 서버(vast.ai PyTorch 템플릿 등)에서, 저장소 루트에서 실행한다. docs/guides/unity-cnn.md 1·2절과 같은 명령이다.
#
#   bash scripts/train_unity_cnn.sh <zip | 구글 드라이브 파일·폴더 링크 | 푼 폴더> [작업 폴더, 기본 ~/cnn]
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

# 입력: zip 파일, 구글 드라이브 파일 링크, 드라이브 폴더 링크(안의 zip을 받는다), 또는 이미 푼 폴더
rm -rf "$W/captures" "$W/unity-yolo" "$W/unity-cls" "$W/dl"
if [ -d "$SRC" ]; then ln -s "$(cd "$SRC" && pwd)" "$W/captures"
else
  if [ -f "$SRC" ]; then Z="$SRC"
  elif [[ "$SRC" == *"/folders/"* ]]; then "$PY" -m gdown --folder "$SRC" -O "$W/dl"; Z="$(find "$W/dl" -name '*.zip' | head -1)"
    S="$(find "$W/dl" -name 'SHA256SUMS*' | head -1)"; [ -n "$S" ] && (cd "$(dirname "$Z")" && sha256sum -c "$S" --ignore-missing)
  else "$PY" -m gdown --fuzzy "$SRC" -O "$W/captures.zip"; Z="$W/captures.zip"; fi
  "$PY" -m zipfile -e "$Z" "$W/captures"
fi

# (가) 이미 나뉜 분류 데이터셋(train|val|test/<클래스>/*.png + manifest.jsonl, 10/8 현준 데이터): 그대로 쓴다.
# (나) Unity 촬영 원본(PNG+JSON): unity_dataset으로 그룹 분할 → unity_cls. 같은 scene_id·session_id·이미지는 한 split에 들어가므로
#      scene/session이 몇 개뿐이면 split이 비거나 쏠린다.
CLS="$(dirname "$(find -L "$W/captures" -maxdepth 3 -type d -name train | head -1)")"
if [ -f "$CLS/manifest.jsonl" ] && [ -d "$CLS/val" ] && [ -d "$CLS/test" ]; then
  "$PY" - "$CLS" <<'EOF' | tee "$W/counts.txt"
import json, sys
from collections import Counter, defaultdict
from pathlib import Path
root = Path(sys.argv[1])
rows = [json.loads(l) for l in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
c = Counter((r["split"], r["class_name"]) for r in rows)
for s in ("train", "val", "test"):
    print(s, {k: c[(s, k)] for k in ("HPU", "GR", "RT", "CV", "CAU", "PDP")}, "합", sum(v for (sp, _), v in c.items() if sp == s))
for key in ("group", "sha256"):
    sp = defaultdict(set)
    for r in rows:
        sp[r[key]].add(r["split"])
    cross = sum(len(v) > 1 for v in sp.values())
    print(f"{key} {len(sp)}개, 여러 split에 걸친 것 {cross}")
    if cross:
        sys.exit(f"누수: {key}가 여러 split에 있다")
print("디스크 PNG", sum(1 for _ in root.glob("*/*/*.png")), "· manifest", len(rows))
EOF
else
  "$PY" -m shiftlink.vision.unity_dataset --captures "$W/captures" --out "$W/unity-yolo" | tee "$W/counts.txt"
  grep -q "WARNING: empty split" "$W/counts.txt" && { echo "split이 비었다 — scene/session을 늘리거나 dataset_split을 정한 뒤 다시"; exit 1; }
  "$PY" -m shiftlink.vision.unity_cls --dataset "$W/unity-yolo" --out "$W/unity-cls" | tee -a "$W/counts.txt"
  CLS="$W/unity-cls"
fi

M="$W/model"
"$PY" -m shiftlink.vision.train --data "$CLS/train" --val-data "$CLS/val" --out "$M" \
  --epochs "$EPOCHS" --workers "$WORKERS" 2>&1 | tee "$W/train.log"
"$PY" -m shiftlink.vision.quantize --model "$M" --calib "$CLS/train"
"$PY" -m shiftlink.vision.quantize --model "$M" --calib "$CLS/train" --conv-only
for v in model model-int8 model-int8conv; do  # test는 학습·보정에 쓰지 않았다. 발표 수치(G5)는 여기서 나온다
  "$PY" -m shiftlink.vision.evaluate --model "$W/$v/model.onnx" --data "$CLS/test" --json "$W/eval_$v.json"
done

tar -C "$W" -czf "$W/result.tgz" model model-int8 model-int8conv eval_model.json eval_model-int8.json eval_model-int8conv.json counts.txt train.log
echo "끝: $W/result.tgz — PC로 받은 뒤 서버를 삭제(Destroy)한다"
