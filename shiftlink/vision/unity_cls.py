"""Unity YOLO 데이터셋(unity_dataset.py 출력) → 분류 학습용 폴더(split/클래스/사진).

    python -m shiftlink.vision.unity_cls --dataset data/vision/unity-yolo --out data/vision/unity-cls

사진 전체를 사용한다. --captures를 주면 JSON의 촬영 대상 장비를 정답으로 사용한다.
촬영 대상 메타데이터가 없는 기존 데이터만 가장 큰 설비 상자의 클래스로 정한다.
split(train/val/test)은 unity_dataset.py가 나눈 그대로 쓴다(같은 장면·세션은 같은 split → 누수 없음).
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

from shiftlink.vision import CLASSES

# ponytail: 가장 큰 상자 하나로 라벨을 정한다. 사진에 설비가 둘 이상 크게 잡히면 틀린 라벨이 될 수 있다.
# 그런 사진이 많으면 두 번째 상자와의 면적 비로 애매한 사진을 빼는 규칙을 더한다.
MIN_AREA = 0.02  # 사진 면적 대비. 이보다 작으면 겨냥한 설비로 보지 않고 뺀다


def dominant_class(label_text: str) -> str | None:
    """YOLO 라벨(줄마다 `class cx cy w h`, 0~1 정규화)에서 가장 큰 상자의 클래스. 없거나 작으면 None."""
    best_area, best = 0.0, None
    for line in label_text.split("\n"):
        if line.strip():
            class_id, _, _, w, h = line.split()
            area = float(w) * float(h)
            if area > best_area:
                best_area, best = area, CLASSES[int(class_id)]
    return best if best_area >= MIN_AREA else None


def convert(dataset: Path, out: Path, captures: Path | None = None) -> dict[str, Counter]:
    if out.exists():
        raise SystemExit(f"출력 폴더가 이미 있습니다(덮어쓰지 않음): {out}")
    targets = {}
    if captures is not None:
        if not captures.is_dir():
            raise ValueError(f"촬영 폴더 없음: {captures}")
        for path in sorted(captures.rglob('*.json')):
            row = json.loads(path.read_text(encoding='utf-8-sig'))
            objects = [obj for obj in row.get('objects', []) if obj.get('equipment_id') == row.get('target_equipment_id')]
            name = row.get('capture_id')
            if not name or name in targets or len(objects) != 1 or objects[0].get('equipment_type') not in CLASSES:
                raise ValueError(f"촬영 대상 메타데이터 오류: {path}")
            targets[name] = objects[0]['equipment_type']
    counts: dict[str, Counter] = {}
    records = []
    for split in ("train", "val", "test"):
        counts[split] = Counter()
        for image in sorted((dataset / "images" / split).glob("*.png")):
            if captures is not None:
                cls = targets.get(image.stem)
                if cls is None:
                    raise ValueError(f"촬영 대상 라벨 없음: {image.name}")
            else:
                label = dataset / "labels" / split / (image.stem + ".txt")
                cls = dominant_class(label.read_text(encoding="utf-8")) if label.exists() else None
            if cls is None:
                counts[split]["(제외)"] += 1
                continue
            records.append((image, split, cls))
            counts[split][cls] += 1
    for image, split, cls in records:
        target = out / split / cls / image.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image, target)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", type=Path, required=True, help="unity_dataset.py 출력 폴더")
    parser.add_argument("--out", type=Path, required=True, help="새 폴더(있으면 중단)")
    parser.add_argument("--captures", type=Path, help="촬영 대상 정답이 담긴 원본 PNG/JSON 폴더")
    args = parser.parse_args()
    for split, c in convert(args.dataset, args.out, captures=args.captures).items():
        print(split, " ".join(f"{k}={c[k]}" for k in (*CLASSES, "(제외)") if c[k]))


if __name__ == "__main__":
    main()
