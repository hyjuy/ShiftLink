# 장비 인식 데이터셋 촬영

현재 공장의 활성 장비 10대를 각각 600장씩 촬영한다. 6종 클래스 순서는 기존 PDA 촬영과 동일한 `HPU, GR, RT, CV, CAU, PDP`다. RT 3대와 GR·CV 각각 2대를 포함하므로 클래스별 촬영 대상 수량은 다르다.

장비당 학습 480장, 검증 60장, 평가 60장으로 구성한다. 360도를 60개의 6도 방향 구간으로 나눠 구간마다 10장씩 촬영한다. 각 10개 구간 중 8개는 학습, 1개는 검증, 1개는 평가에 배정한다. 구간 내 높이·거리·카메라 기울기·조명을 무작위로 바꾸며, 운전과 일시정지 상태를 포함한다. 같은 구간의 사진을 서로 다른 분할로 나누지 않는다.

`FactoryDatasetCapture`는 기존 `FactoryCapture`의 RGB·가시 인스턴스 마스크 촬영 경로를 사용한다. 목표 장비가 보이지 않거나 바운딩 박스가 이미지 면적의 3.5%보다 작거나 화면 가장자리에서 잘리면 같은 방향 구간에서 재촬영한다. 다른 장비가 함께 보이면 함께 라벨링한다. 따라서 이미지의 촬영 대상은 장비당 600장이지만, 주변 장비의 라벨 수는 이보다 많을 수 있다.

원본 PNG는 1280×720이다. JSON에 장비 ID, 클래스, 가시 영역의 바운딩 박스, 카메라 위치·회전·시야각, 분할과 촬영 대상 ID를 기록한다. PNG/JSON 쌍을 YOLO `images/{train,val,test}`, `labels/{train,val,test}`, `data.yaml`, `manifest.jsonl`로 변환한다. 분할 지정이 같은 장면·세션·이미지 해시 그룹 내에서 충돌하면 내보내기를 거부한다.

## 실행

열린 Unity 프로젝트를 변경하지 않도록 필요한 Assets·설정·검증용 MES 스냅샷을 출력 폴더의 별도 프로젝트에 복사한다.

```powershell
python -B scripts/capture_unity_dataset.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --out artifacts/equipment-dataset-20261007 --smoke
python -B scripts/capture_unity_dataset.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --out artifacts/equipment-dataset-20261007 --per-equipment 600
```

촬영은 완료된 PNG/JSON 쌍을 건너뛰며 재개할 수 있다. 내보내기는 기존 출력 폴더를 덮어쓰지 않는다. 결과는 출력 폴더의 `summary.json`, 진행 상황은 `capture-progress.txt`, Unity 완료 증거는 `capture-result.txt`에 기록한다.

## 확인한 검증

- 분할 보존·분할 충돌·잘못된 분할 지정 검사를 먼저 추가했고, 구현 전 3개가 실패했다.
- 구현 후 `python -B -m unittest discover -s tests -p test_unity_dataset.py`의 11개 검사가 통과했다. 기존 PNG 손상·라벨 범위·클래스 매핑·중복 ID·그룹 분리 검사도 포함한다.
- 데이터셋 변환 코드의 테스트 커버리지는 90%다.
- Unity 10장 샘플 촬영에서 10대 모두 촬영 대상 라벨을 포함했고, PNG/JSON 검증과 YOLO 변환을 통과했다. HPU·CAU·RT-02·CV-02의 샘플 이미지를 시각 확인했다.
- 2026-10-07 전체 촬영과 내보내기를 완료했다. 장비 10대 각각 학습 480장·검증 60장·평가 60장, 총 6,000장이다. 이미지 SHA-256은 6,000개 모두 고유하며, PNG 구조·CRC·해상도·카메라 메타데이터·라벨 좌표·클래스·분할 충돌 검사를 통과했다.
- 후반 RT-02·RT-03 및 CV-01·CV-02는 별도의 Unity 프로젝트에서 병행 촬영했다. 완료된 장비 폴더를 통합하고 주 작업은 이미 완료된 촬영 번호를 건너뛰었다. 장비별 600장 기준은 그대로 유지했다.
- 학습·평가 미리보기에서 장비 10대의 실제 렌더와 촬영 대상 바운딩 박스를 시각 확인했다. 최종 산출물과 수량 요약은 `artifacts/equipment-dataset-20261007/README.md`, 학습 설정은 `artifacts/equipment-dataset-20261007/dataset/data.yaml`에 있다.

이는 동일한 합성 공장과 장비 모델에서 카메라 방향을 분리한 데이터셋이다. 실카메라 사진 또는 다른 공장에 대한 인식 성능을 평가하는 데이터셋은 아니다. 학습 실행과 실제 인식률 측정은 이번 촬영 작업에 포함하지 않는다.
