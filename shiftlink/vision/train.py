"""PC 전이학습: 사전학습 MobileNetV3-Small → 6클래스 → ONNX + labels.txt.

    python -m shiftlink.vision.train [--data data/vision/raw] [--out data/vision/model] [--epochs 10]
    python -m shiftlink.vision.train --data data/vision/unity-cls/train --val-data data/vision/unity-cls/val  # Unity (unity_cls.py)

입력 전처리(224x224 리사이즈, ImageNet 정규화)는 classify.preprocess()와 같아야 한다.
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms

from shiftlink.vision import MODEL_DIR, RAW_DIR

SIZE = 224
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path(RAW_DIR))
    parser.add_argument("--out", type=Path, default=Path(MODEL_DIR))
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--val-data", type=Path, help="검증 폴더를 따로 줄 때(Unity split). 없으면 --data를 무작위로 나눈다")
    parser.add_argument("--workers", type=int, default=0, help="사진 읽기 프로세스 수(GPU 서버에서 vCPU 수만큼). 0=한 줄로 읽기")
    parser.add_argument("--seed", type=int, default=0, help="섞기·초기화 시드(다시 돌려도 같은 순서)")
    args = parser.parse_args()
    torch.manual_seed(args.seed)

    base = [transforms.Resize((SIZE, SIZE))]
    norm = [transforms.ToTensor(), transforms.Normalize(MEAN, STD)]
    train_tf = transforms.Compose(base + [transforms.ColorJitter(0.3, 0.3, 0.3), transforms.RandomRotation(10)] + norm)
    val_tf = transforms.Compose(base + norm)
    train_all = datasets.ImageFolder(args.data, transform=train_tf)
    val_all = datasets.ImageFolder(args.data, transform=val_tf)
    labels = train_all.classes  # 폴더 이름 알파벳순 = 모델 출력 순서

    if args.val_data:
        val_set = datasets.ImageFolder(args.val_data, transform=val_tf)
        if val_set.classes != labels:  # 클래스 폴더가 다르면 출력 번호가 어긋난다
            raise SystemExit(f"검증 클래스 {val_set.classes} != 학습 클래스 {labels}")
        train_set = train_all
    else:
        # ponytail: 무작위 분할이라 연속 촬영한 비슷한 사진이 양쪽에 섞여 검증 정확도가 높게 나온다.
        # 발표용 수치는 다른 날·다른 조명으로 따로 찍은 사진으로 다시 잰다.
        order = torch.randperm(len(train_all), generator=torch.Generator().manual_seed(0)).tolist()
        n_val = max(1, int(len(order) * args.val_ratio))
        train_set, val_set = Subset(train_all, order[n_val:]), Subset(val_all, order[:n_val])
    n_val = len(val_set)
    # 9,600장이면 PNG 읽기·늘리기가 GPU보다 느리다(10/8). 읽기만 병렬로 하고 학습 방식은 같다.
    loader = {"num_workers": args.workers, "persistent_workers": args.workers > 0}
    train_dl = DataLoader(train_set, batch_size=32, shuffle=True, **loader)
    val_dl = DataLoader(val_set, batch_size=64, **loader)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(labels))
    model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss()

    best_acc, best_state = -1.0, None
    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss_fn(model(x), y).backward()
            opt.step()
        model.eval()
        correct = 0
        with torch.no_grad():
            for x, y in val_dl:
                correct += (model(x.to(device)).argmax(1).cpu() == y).sum().item()
        acc = correct / n_val
        print(f"epoch {epoch}: val_acc={acc:.3f} ({correct}/{n_val})")
        if acc > best_acc:
            best_acc, best_state = acc, copy.deepcopy(model.state_dict())

    model.load_state_dict(best_state)
    model.to("cpu").eval()
    args.out.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(model, torch.zeros(1, 3, SIZE, SIZE), str(args.out / "model.onnx"),
                      input_names=["input"], output_names=["logits"], opset_version=17,
                      dynamo=False)  # 기존 TorchScript 내보내기: 파이의 ONNX Runtime과 opset 17 그대로 맞춘다
    (args.out / "labels.txt").write_text("\n".join(labels) + "\n", encoding="utf-8")
    print(f"best val_acc={best_acc:.3f} (seed {args.seed}, device {device}) -> {args.out / 'model.onnx'}, labels={labels}")


if __name__ == "__main__":
    main()
