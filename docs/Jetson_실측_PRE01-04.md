# Jetson 실측 — PRE-01~04 (1주차 최우선 전제 확인)

측정 2026-09-18 13:3X KST · 대상 `jetson-06` (100.115.59.4) · 측정자: Claude(SSH 원격, 최재영 PC 계정 키 등록 후)

> 개발계획 v2 §2.2 Day2, 01_고도화_초안 §15.1의 PRE-01~04를 실행한 결과다. **PRE-04는 계획이 요구하는 "깨끗한 유휴 상태" 조건을 만족하지 못했다** — 아래 참고, 재측정 필요.

## PRE-01 — RAM 실측

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           7.4Gi       3.3Gi       902Mi        39Mi       3.2Gi       3.8Gi
$ tegrastats (1회) → RAM 3598/7620MB
```

**결론: 물리 RAM은 약 7.6GB(≈8GB, Orin Nano 8GB 스펙과 일치).** 사양서 원문의 "Ram: 89GB"는 **오기로 확정**한다 (고도화 초안 §15.2 분기표의 "8GB로 확인" 분기 적용 — 4.3 플랜 순위(B 기본) 변경 없음).

## PRE-02 — JetPack/L4T 버전

```
$ cat /etc/nv_tegra_release
# R36 (release), REVISION: 4.7, GCID: 42132812, BOARD: generic, EABI: aarch64
```

L4T R36.4.7 (JetPack 6.x 계열).

## PRE-03 — 전력 모드

`/etc/nvpmodel.conf`에 정의된 모드 4종:

| ID | 이름 |
|---|---|
| 0 | 15W |
| 1 | 25W |
| 2 | MAXN_SUPER |
| 3 | 7W |

측정 시점 활성 모드: **25W** (`nvpmodel -q` 결과 "NV Power Mode: 25W", id 1).

주의: 계획서 4.3의 `MAXN(25W)` 표기와 NVIDIA 공식 `25W`/`MAXN_SUPER` 분리가 실제로 다른 두 모드임이 확인됐다 → N-6 결정에 반영 필요.

## PRE-04 — 유휴 메모리 · ⚠️ 재측정 필요

**측정 조건이 계획(§2.2 Day2: "VSCode Remote-SSH는 끊고 잰다", "GUI 켠 상태/끈 상태 각각")과 다르다.**

측정 시점 확인된 상태:
- `systemctl get-default` → `graphical.target` (GUI 켜짐)
- VNC 데스크톱 세션 활성 (`Xtigervnc :1`, `gnome-shell`, `xfwm4`, `xfdesktop` 동시 실행 — 데스크톱 환경이 섞여 있어 보임, 확인 필요)
- **VSCode Remote-SSH 서버와 Cursor Remote 서버가 동시에 실행 중** (프로세스 시작 시각이 09:15와 13:19로 다름 → 서로 다른 시점에 접속한 별도 세션일 가능성 높음, 팀원 동시 접속 추정)
- 위 상태에서 `free -h` available 3.8Gi로 나오지만 **free는 902Mi, largest free block은 4MB 단위로 파편화**(`lfb 2x4MB`)

### 실제 영향 — 플랜 B 모델 로드 실패 (재현됨)

```
POST /api/generate (qwen2.5:3b-instruct-q4_K_M, 구조화 출력 요청)
→ {"error": "llama-server process has terminated: exit status 1: cudaMalloc failed: out of memory
   alloc_tensor_range: failed to allocate CUDA0 buffer of size 1923955712
   error loading model: unable to allocate CUDA0 buffer"}
```

**1.9GB 모델(qwen2.5:3b, q4_K_M)조차 이 조건에서는 로드되지 않았다.** Jetson은 통합 메모리 구조라 시스템 RAM 압박이 곧바로 "CUDA 메모리 부족"으로 나타난다.

### 원인 진단

메모리 상위 소비 프로세스(`ps aux --sort=-%mem`)에 데스크톱·원격개발 툴이 대부분을 차지: `.cursor-server`(약 480MB), `.vscode-server` 관련 프로세스 다수(합 ~1GB), `gnome-shell`(~215MB), VNC·xfwm4·xfdesktop(~수백MB) 등. **개발계획 v2 §5 리스크표의 "Jetson 1대를 4명이 공유" 위험이 실측으로 확인됐다.**

### 필요 조치 (팀 결정 필요)

1. **점유 규칙을 지금 정한다** — 계획서에 있던 "측정 시간대 예약"이 아직 실행되지 않고 있다. 최소한 모델 로드·추론 측정 중에는 다른 원격 세션(VSCode/Cursor Remote 등)을 끄기로 합의 필요.
2. GUI(`graphical.target`) 상태에서 상시 운영할지, `multi-user.target`(헤드리스)로 바꿔 운영할지 결정 — 계획서는 후자를 유휴 메모리 기준으로 요구했으나 아직 미검증.
3. 위 조치 후 PRE-04를 GUI 켬/끔 두 조건으로 재측정하고 이 문서에 추가한다.

## 부가 확인

- Ollama 버전 `0.34.1`, `qwen2.5:3b-instruct-q4_K_M` digest `357c53fb659c` — **PC(`models.lock`) 기록과 일치** (개발계획 Day1 완료기준 4번 충족)
- `jtop` 설치 확인됨(`/usr/local/bin/jtop`), 정식 발열·GPU% 모니터링은 미실행 — 3일차 실측(플랜 B 연속 20건, 15W/25W 대조)에서 사용 예정
