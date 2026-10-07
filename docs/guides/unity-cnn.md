# Unity 사진 → 설비 분류 CNN → 파이 → Jetson (10/7)

10/7 결정: 설비 인식 입력은 Unity 작업자 시점(PDA) 사진, 모델은 기존 CNN 분류(MobileNetV3-Small 6클래스)를 재사용한다. 웹캠은 얼굴 로그인 전용이다.

```
[Unity PDA 촬영 PNG+JSON] --send_unity_captures.py--> [파이 classify.py --listen 8090] --클래스명--> [Jetson MES /api/equipment/scan]
```

## 1. 데이터 (유현준)

클래스당 약 100장. 같은 장면만 찍으면 val·test가 비므로 위치·각도·조명을 바꾼 여러 세션으로 찍는다.

```powershell
python -m shiftlink.vision.unity_dataset --captures <촬영 폴더> --out data/vision/unity-yolo   # 누수 없는 train/val/test 분할
python -m shiftlink.vision.unity_cls --dataset data/vision/unity-yolo --out data/vision/unity-cls  # 분류용 폴더
```

`unity_cls`는 사진 전체를 쓰고 라벨은 가장 큰 설비 상자의 클래스로 정한다. 설비가 없거나 상자가 사진의 2% 미만이면 빼고 개수를 출력한다.

## 2. 학습·양자화·평가 (PC, torch 필요)

```powershell
python -m shiftlink.vision.train --data data/vision/unity-cls/train --val-data data/vision/unity-cls/val --out data/vision/model --epochs 15
python -m shiftlink.vision.quantize --model data/vision/model --calib data/vision/unity-cls/train            # → data/vision/model-int8
python -m shiftlink.vision.quantize --model data/vision/model --calib data/vision/unity-cls/train --conv-only # → data/vision/model-int8conv
python -m shiftlink.vision.evaluate --model data/vision/model/model.onnx --data data/vision/unity-cls/test --json fp32.json
```

- test 폴더는 학습·보정에 쓰지 않는다. 발표의 클래스별 정확도(G5)는 test 결과이고, "Unity 이미지 기준"이라고 적는다.
- **INT8 주의**: 10/7 합성 데이터 시험에서 전체 INT8은 정확도가 크게 떨어졌다(0.69 → 0.28). Conv만 양자화하면 덜 떨어졌다(0.58, 크기 5.9MB → 3.5MB). 실제 데이터로 FP32·INT8·INT8(Conv) 세 가지를 같은 test로 비교하고, 파이 지연과 함께 고른다. 합성 데이터와 작은 모델이라 실제 결과와 다를 수 있다.
- 모델 파일(`*.onnx`)은 `.gitignore` 대상이다. 저장소 밖으로 전달한다.

## 3. 파이

```bash
python -m shiftlink.vision.classify --model ~/shiftlink/models/cnn --listen 8090 --server http://<jetson>:8000 --device-id pi-01
PYTHONPATH=. python bench/pi_classify_timing.py --model ~/shiftlink/models/cnn   # 1프레임 시간(W3-2), 모델별로
```

`--min-conf`(기본 0.8) 미만이면 답만 돌려주고 Jetson에는 보내지 않는다.

## 4. Unity PC

```powershell
python scripts/send_unity_captures.py --dir <Unity 촬영 폴더> --pi http://<파이>:8090
```

PNG와 JSON이 모두 저장된 사진만 보낸다. 시작 전부터 있던 사진은 건너뛴다(`--all`이면 보낸다).

## TensorRT

파이(ARM CPU)에는 TensorRT가 없다. 비교용으로 Jetson에서 `trtexec --onnx=model.onnx --fp16`과 INT8(QDQ) 모델의 지연을 잰다. LLM 두 개가 올라가 있으니 메모리를 보면서 하고, 10/14 채점일에는 하지 않는다.
