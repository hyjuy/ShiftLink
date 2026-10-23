# 전체 테스트 환경·검증 복구 (2026-10-23)

기준은 main `e1c88f5978d259ab85af324a8ce3d6b4fcb2e717`에 PR #343의 `b7bbeb2885d50358490158a3054d0a0e6b79371c`를 반영한 코드다. 변경은 테스트 4개, 연구 테스트 의존성 파일, CI, 체크포인트 저장 함수의 OS 분기, 이 문서의 8파일이다. UI·모델·임계값·MES·운영 DB는 변경하지 않는다.

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

운영 실행 파일 변경은 `scripts/mes_causal_pda_service.py` 하나다. Pi의 기존 r2를 보존한 별도 analytics 릴리스에 반영하고 #343의 기존 PDA 4파일·기기용 HTML·설정·core를 보존한다. CI·테스트 파일은 검증용이며 기기에 연구용 CPU torch를 설치하지 않는다. Jetson 실행 코드의 변경은 없다.

## #343 통합에서 추가 확인한 경계

- 원 PR의 Linux CI #519는 2 실패·2953 통과·5 skip이었다. Chromium은 JS 검사 전에 Zygote 초기화에서 종료됐고, 다른 연구 테스트가 import한 torch 때문에 전역 `sys.modules` 부재 검사도 실패했다. 모듈 부재 검사는 새 Python 프로세스에서 정상/비정상 설정 모두에 적용한다. 부모가 torch를 이미 import해도 독립적인 검사가 된다.
- Chromium의 `--no-sandbox`는 GitHub Actions의 합성 file fixture에만 명시적으로 설정한다. 기본 Pi 브라우저와 운영 브라우저 인수는 그대로 유지한다. 실행 실패의 전체 stderr를 보존하도록 해 실제 UI assertion 실패와 구분한다. 최종 CI 결과로 실행 조건 수정의 효과를 확인한다.
- Windows 전체 통합 검사에서는 22 실패·2929 통과·3 skip·WSL 오류 1개였다. 이 중 21개는 체크포인트 파일 교체 뒤 디렉터리를 `os.open`하는 부분의 `PermissionError`, 1개는 위 전역 모듈 검사였다. `atomic_json`은 파일 flush/fsync·chmod·원자적 교체를 유지하고 디렉터리 fsync만 POSIX에서 수행한다. Pi의 POSIX 저장 경로는 동일하며 Linux 오류를 숨기는 예외 처리는 추가하지 않는다.
- 수정 후 Torch 미세조정·통계 core·실서비스/정지 이력·reader·배포 복구·표시·계정의 관련 8개 파일은 **84개 모두 통과**했다. 선택 skip은 없었다. 전체 검사·Linux CI·Pi 격리 검사·실제 배포 결과는 PR의 검증 결과와 로컬 원자료에 따로 남긴다. 개별 검사 통과를 전체 검사의 성공으로 바꾸지 않는다.
