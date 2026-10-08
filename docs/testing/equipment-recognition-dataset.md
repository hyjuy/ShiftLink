# 장비 인식 데이터셋 촬영

## 2026-10-08 최신 모델·사람 시점·추가 근접 촬영

최신 모델로 10대 × 600장 = 6,000장을 촬영한 뒤, 사용자 피드백에 따라 장비마다 **방향 보강 전경 60장 + 특징 근접 300장**을 추가했다. 후보 9,600장 중 최종 **8,951장**을 유지한다(학습 7,178·검증 893·평가 880). 전경 6,092장과 특징 근접 2,859장이다. HPU-01, PDP-01, CAU-01, GR-01·02, RT-01·02·03, CV-01·02 모두 대상이며, 모든 장비에 12방향이 남아 있다. 사용자 지시에 따라 제외 원본과 복사본 649장은 삭제하고 사유 기록만 보관한다.

장비 형태와 크기는 유지하면서 촬영 공장 바닥을 66×51m, 배치 간격을 1.5배로 넓힌다. CAU 플랫폼도 걷는 공간을 확장한다. 바닥 또는 플랫폼 기준 렌즈 높이 1.2~1.8m를 유지하고 발판 존재·사람 공간·장비 및 배관 충돌을 검사한다. 추가 사진은 30° 간격 12방향으로 구성하고 학습·검증·평가 모두에 모든 방향을 포함한다. 추가분은 분할별 각도 범위를 우선 분리한다. 연결부가 사람 공간을 막으면 같은 방향 구간 안에서 가능한 각도로 옮기고 `angle_range_relaxed`에 기록한다. 장면·세션 ID와 이미지 해시는 분할 사이에 공유하지 않는다. 같은 장비·배경에 대한 상관성은 남는다.

근접 사진은 원본을 크롭해서 만들지 않고 카메라를 실제로 가까이 옮겨 촬영한다. CAU 제어판·흡기 루버·배기부, HPU 축압기·밸브·탱크 점검부, PDP 차단기·피더 패널, GR 축·모터·기어 점검부, RT 롤러·베어링·체인 가드, CV 벨트·드럼·배출 슈트 등의 보이는 특징부를 겨냥한다. 전경은 화면 가장자리 잘림을 거부한다. 근접은 장비 전체의 일부 잘림을 허용하되 가시 타깃 면적 12% 이상, 중앙 특징부의 시선 가림 검사를 적용한다.

어두움·보통·밝음·따뜻한 조명·차가운 조명을 각 분할에 포함한다. 실제 태양·실내 LED 밝기와 주변광을 바꾸고 JSON에 기록한다. **어두워도 식별 가능한 사진은 유지한다.** 밝기 프로필만으로 사진을 제외하지 않는다.

최종 CNN 입력은 `artifacts/equipment-dataset-20261008-combined/cnn-curated/{train,val,test}`다. 사진 전체를 쓰고 `target_equipment_id`를 정답으로 삼는다. 다른 종류의 장비가 더 크게 보이더라도 정답을 그 장비로 바꾸지 않는다. 유지 사진의 PNG 바이트와 분할을 보존하고 기존 JSON에는 카메라 좌표로 계산한 방향과 전경 종류만 보강한다.

서브에이전트가 실제 사진 표본을 독립 검토하여 평평한 외판만 강조한 근접, 심한 가림, 원경 타깃 등의 제외 후보를 기록했다. 자동 선별은 전경 타깃 면적 8% 미만, 근접 12% 미만, 다른 클래스 상자 면적이 타깃의 1.2배 초과, 타깃 영역의 대비 부족 등을 확인한다. 긴 컨베이어의 짧은 변 길이만으로 일괄 제외하지 않는다. 마지막 육안 검토에서 식별 가능한 CAU 저조도 6장과 RT 경계 표본 1장을 보존했다. dim 프로필 사진 1,791장이 남는다. 제외 기록은 `cnn-curated/excluded.jsonl`, 실제 분포는 `cnn-curated/summary.json`에 남긴다. 전수 육안검사나 CNN 성능 측정은 아니다.

공유 파일은 전체 데이터의 단일 ZIP `equipment-cnn-20261008.zip`이며 제외 사진과 제외 원본 JSON은 포함하지 않는다. 사진·ZIP은 Git에 넣지 않는다. [Drive 공유 폴더](https://drive.google.com/drive/folders/1CxBqCGu8sweYRiwg3DbIQAxNqONbPhBm?usp=drive_link), [선별 통계와 검토 기록](equipment-dataset-20261008/README.md)을 참고한다.

```powershell
python -B scripts/capture_unity_dataset.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --out artifacts/equipment-dataset-20261008-extra --smoke --equipment-codes CAU-01
python -B scripts/capture_unity_dataset.py --editor D:/obsd/Unity/Editors/6000.3.12f1/Editor/Unity.exe --out artifacts/equipment-dataset-20261008-extra --per-equipment 360
python -B scripts/augment_equipment_dataset.py --existing artifacts/equipment-dataset-20261008 --additional artifacts/equipment-dataset-20261008-extra --out artifacts/equipment-dataset-20261008-combined
python -B scripts/curate_equipment_cnn.py --source artifacts/equipment-dataset-20261008-combined --out artifacts/equipment-dataset-20261008-combined/cnn-curated --review-exclusions artifacts/equipment-dataset-20261008-extra/review-exclusions.json --review-keeps artifacts/equipment-dataset-20261008-extra/review-keeps.json
python -B scripts/retire_excluded_photos.py --excluded artifacts/equipment-dataset-20261008-combined/cnn-curated/excluded.jsonl --workspace D:/obsd/Projects/ShiftLink
python -B scripts/package_equipment_cnn.py --cnn artifacts/equipment-dataset-20261008-combined/cnn-curated --captures artifacts/equipment-dataset-20261008-combined/captures --out artifacts/equipment-dataset-20261008-packages
```

추가 촬영은 완료된 PNG/JSON 쌍을 건너뛰며 재개한다. 내보내기·합산·선별은 기존 출력 폴더를 덮어쓰지 않는다. PNG 구조·CRC·해상도·가시 라벨·분할 그룹·중복 SHA-256, 사람 높이·설 공간·실제 조도, 방향·근접 수량, CNN 사본의 해시를 검사한다. 실행 근거는 [TDD 기록](human-equipment-dataset-20261008.tdd.md)에 남긴다. 같은 합성 장비와 배경이므로 실카메라 성능을 대신하지 않으며, 실제 CNN 학습과 정확도 측정은 수행하지 않는다.

## 이전 촬영 기록 (2026-10-07, 데이터 교체 완료)

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
