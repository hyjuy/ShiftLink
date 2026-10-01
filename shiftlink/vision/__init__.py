"""웹캠 설비 분류(CNN). 경량 계획 1절 A안: 라즈베리파이에서 분류하고 Jetson에는 클래스명만 보낸다.

    python -m shiftlink.vision.capture     # 촬영 (숫자키 1~6 = 클래스)
    python -m shiftlink.vision.train       # PC 전이학습 → ONNX
    python -m shiftlink.vision.classify    # 파이에서 실시간 분류

파이에는 torch가 없으므로 이 패키지는 shiftlink.agent 등 다른 모듈을 import하지 않는다.
"""

# shiftlink.agent.schemas.Equipment에서 COMMON을 뺀 값. 일치 여부는 tests/test_vision.py가 검사한다.
CLASSES = ("HPU", "GR", "RT", "CV", "CAU", "PDP")

RAW_DIR = "data/vision/raw"
MODEL_DIR = "data/vision/model"
