# Unity 사진 → 설비 분류 CNN → 파이 → Jetson (10/7)

10/7 결정: 설비 인식 입력은 Unity 작업자 시점(PDA) 사진, 모델은 기존 CNN 분류(MobileNetV3-Small 6클래스)를 재사용한다. 웹캠은 얼굴 로그인 전용이다.

```
[Unity PDA 촬영 PNG+JSON] --send_unity_captures.py--> [파이 classify.py --listen 8090] --클래스명--> [Jetson MES /api/equipment/scan]
```

## 1. 데이터 (유현준)

최신 모델로 장비별 600장을 촬영한 뒤 전경 60장·특징 근접 300장을 추가했다. 후보 9,600장 중 8,951장(학습 7,178·검증 893·평가 880)을 유지한다. 최종 폴더는 `artifacts/equipment-dataset-20261008-combined/cnn-curated/{train,val,test}`이며, [Drive](https://drive.google.com/drive/folders/1CxBqCGu8sweYRiwg3DbIQAxNqONbPhBm?usp=drive_link)는 공유 대상 폴더다. 전체 ZIP은 로컬에서 검증 완료했지만 연결 도구의 파일당 512MiB 제한으로 업로드 대기 중이다. 웹에서 ZIP을 올린 뒤 내려받아 동일한 구조로 사용할 수 있다. 제외 원본과 복사본은 삭제했다. [촬영·선별 기준](../testing/equipment-recognition-dataset.md)을 따른다.

```powershell
python -m shiftlink.vision.unity_dataset --captures <촬영 폴더> --out data/vision/unity-yolo   # 누수 없는 train/val/test 분할
python -m shiftlink.vision.unity_cls --dataset data/vision/unity-yolo --captures <촬영 폴더> --out data/vision/unity-cls  # 촬영 대상 라벨의 분류 폴더
```

`unity_cls --captures`는 사진 전체를 쓰고 JSON의 `target_equipment_id`를 정답으로 삼는다. 타깃 메타데이터가 누락되면 내보내기를 거부한다. `--captures`가 없는 기존 변환에 한해 가장 큰 설비 상자의 클래스를 쓰며, 상자가 사진의 2% 미만이면 제외한다.

## 2. 학습·양자화·평가 (PC, torch 필요)

GPU 서버(vast.ai 등)에서는 1·2절 전체를 한 번에: `bash scripts/train_unity_cnn.sh <촬영 zip 또는 구글 드라이브 링크>` → `~/cnn/result.tgz`(모델 3종·평가 json·장수·학습 로그). 사진 읽기는 `--workers`(스크립트는 vCPU 수, 최대 8)로 병렬화한다.

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

**PDA 스캔 화면 (10/8 기본)**: 스캔 화면에 Unity 실시간 영상과 「촬영」 버튼이 나온다. 누르면 PDA 서버가 그 순간 프레임 한 장을 분류해 0.8 이상이면 Jetson에 보내고, 스캔 화면은 그 기록으로 설비를 고른다(시간 제한 없음). 실시간 프레임을 계속 분류하면 입구처럼 여러 설비가 보이는 장면도 확정돼서(입구 RT → CAU 0.90) 촬영 한 장만 쓴다.

```bash
python -m shiftlink.pda --cnn ~/shiftlink/models/cnn --unity http://127.0.0.1:8090 --jetson http://<jetson>:8000 --save-shots ~/shiftlink/data/scan-shots   # --min-conf 0.8 --device-id pi-01
```

- 모델: FP32(10/8 시험셋 0.994, INT8 두 종은 0.14·0.11로 쓰지 않음). `venv-face`에 `onnxruntime==1.20.1`이 있어야 한다.
- `--min-conf 0.8`은 검증셋 893장에서 정했다: 맞는 891장 중 889장 통과, 틀린 2장(0.51·0.76)은 모두 막힘.

**사진 한 장 수신 모드** (Unity 저장 사진·W3-1 측정용):

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
