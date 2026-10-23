# 전체 테스트 환경·검증 복구 (2026-10-23)

기준 main은 `e1c88f5978d259ab85af324a8ce3d6b4fcb2e717`이다. 이 변경은 테스트 2개, 연구 테스트 의존성 파일, CI의 같은 의존성 파일 참조, 이 문서에 한정한다. 실행 코드, UI, 서비스 설정, 운영 DB는 변경하지 않는다.

## 확인한 원인

- 기존 로컬 UI의 유효한 제목 `센서 기반 증상 후보`를 테스트가 `원인 후보`라는 특정 문자열로만 검사했다. 보존한 로컬 복사본에서 관련 3개 파일은 1 실패·84 통과였고 main에서는 85 통과였다. 원래 보고서의 실패 전체 로그는 없으므로, 당시 실패와 동일하다고 단정하지는 않는다.
- 표시 테스트는 원인/증상 후보 제목을 허용하되 후보 section, 슬립, `확정 진단 아님`, 추가 확인을 검사한다. 두 제목의 양성 대조군과 확정 진단/다른 section의 음성 대조군을 함께 검사한다. UI를 바꾸지 않는다. RED 체크포인트는 `088f628`이다.
- 전체 main 검사에서 Windows의 POSIX 권한 비트 검사가 추가 실패했다(`438 != 384`). Windows에서는 해당 권한 비트만 검사하지 않는다. Linux에서는 `0600` 검사를 그대로 유지하고, 모든 OS에서 인증·역할·비밀번호 비평문 저장·중복·로그아웃·시도 제한을 계속 검사한다. NTFS ACL을 검증했다는 뜻은 아니다.
- 기존 `test_mes_timestral_finetune.py`는 torch/Timestral을 직접 import하므로 전체 테스트 수집에 해당 개발 의존성이 필요하다. 새 `requirements-test-research.txt`는 기존 CI 버전과 Git 커밋을 그대로 고정하고 CI/로컬에서 같은 설치 명령을 사용하도록 한다. 런타임 requirements는 바꾸지 않는다.

## #339와의 구분

#339의 최종 v14c는 Timestral/Torch를 로딩하지 않는다. EWMA·동시 온도 상승·정상 기준 문턱 보정을 사용한다. 저장된 `docs/research/evidence/mes-causal-v14c-20261023/evaluation/result.json`의 `timing.timestral_loaded`와 `timing.torch_loaded`도 false다. 이번 torch/Timestral 설치는 별도 기존 연구 테스트용이며 v14c 또는 운영 추론의 새 의존성이 아니다.

## 재현 명령과 환경

Windows 로컬 검증은 Python 3.13.15, torch `2.14.1+cpu`, Timestral `1.0.0`(소스 커밋 `a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`), scikit-learn `1.7.2`를 사용한다. x86 CPU wheel용 파일이므로 Pi/Jetson ARM·CUDA 환경에 설치하면 안 된다.

```powershell
python -m pip install -r requirements.txt -r requirements-test-research.txt
$env:HF_HUB_OFFLINE='1'
python -m pytest -q -ra tests
python scripts/check_knowledge_publication.py
```

실제 브라우저 테스트에는 Playwright와 Chrome이 필요하다. 비전/얼굴의 선택 의존성과 모델 설치 여부에 따른 skip은 통과와 구분한다. WSL 생성 unit 검사는 `DRY_RUN=1`이며 실제 서비스를 등록하거나 시작하지 않는다.

## 증거 보존과 배포 범위

로컬 원자료는 `artifacts/full-suite-repair-20261023/`에 보존한다. 최초 수집 오류, WSL 시간 초과, Windows 권한 실패, 중단한 실행은 성공으로 집계하지 않는다. 장시간 실행 중 테스트 자료/임시 경로 문제를 발견하면 준비를 수정한 뒤 별도 실행으로 확인한다.

기기에 반영하는 경우 위 5개 개발/테스트 파일의 저장소 상대 경로만 기존 `/home/pi/shiftlink/app` 및 `/home/jetson/shiftlink/app` 아래에 복사한다. 기존 파일 유무와 해시를 백업하고 적용 후 파일 해시·실행 Python/UI 소스·HTTP 상태·서비스 PID 불변을 확인한다. CPU torch 설치, 모델 다운로드, 서비스 재시작, 운영 데이터 변경은 이 배포에 포함하지 않는다.
