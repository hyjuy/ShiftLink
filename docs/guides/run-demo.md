# 시연 실행 가이드 — 켜기·확인·끄기 (10/8 기준)

이 문서 하나로 시연 장비 3대를 처음부터 켜고, 확인하고, 끈다. 비밀값(Aiven 접속, 비밀번호)은 저장소에 없고 각 장비의 파일을 가리키기만 한다.

```
[Unity PC] 작업자 시점 /stream.mjpg ──SSH 역터널 127.0.0.1:8090──▶ [라즈베리파이 PDA] 화면·얼굴 로그인·설비 분류(CNN)
                                                                        │ /api/* (Tailscale)
                                                                        ▼
                                                [Jetson] MES :8000 · 검색 + SFT 판정기 + SFT 답(hybrid) · 업로더 → Aiven
```

## 1. 장비

| 장비 | 주소 | 계정 | 돌아가는 것 | 시작 방식 |
|---|---|---|---|---|
| Jetson Orin Nano | `jetson-06.tail0a6af3.ts.net` (Tailscale) | `jetson` | `shiftlink-mes`(:8000), `shiftlink-uploader`, `ollama` | systemd, 부팅 시 자동 |
| 라즈베리파이 4 | `raspberrypi` (Tailscale) | `pi` | PDA 키오스크(`python -m shiftlink.pda`, 127.0.0.1:8080) | 데스크톱 로그인 시 autostart |
| Unity PC (Windows) | — | 각자 | Unity 공장 씬, 카메라 서버(127.0.0.1:8090) | 사람이 실행 |

Tailscale IP는 저장소에 적지 않는다. 같은 tailnet에서 `tailscale status`로 확인한다.

### 경로·모델

| 장비 | 항목 | 값 |
|---|---|---|
| Jetson | 앱 | `/home/jetson/shiftlink/app` (저장소 사본) |
| Jetson | DB | `/home/jetson/shiftlink/data/mock-mes.sqlite3` (MES·업로더 공용) |
| Jetson | Aiven 접속 | `/home/jetson/shiftlink/aiven.env` (chmod 600, 저장소 밖) |
| Jetson | Ollama | 0.34.1, `LLAMA_ARG_CACHE_RAM=0` drop-in(멈춤 방지, `docs/reports/jetson-ollama-memory-20261001.md`) |
| Jetson | 모델 (digest) | `exaone-sft-judge:latest` f31ce4dde530 · `exaone-sft-answer:latest` bd82c5ceaa36 · `exaone3.5:2.4b-instruct-q4_K_M` 13644fc3d28e |
| Jetson | 질의 구성 | hybrid: `SHIFTLINK_ANSWER_MODE=hybrid`, 판정 `exaone-sft-judge`, 답 `exaone-sft-answer` |
| 파이 | 앱 | `~/shiftlink/app` (`deploy/install_pda.sh`가 복사) |
| 파이 | Python | `~/shiftlink/venv-face` (OpenCV, onnxruntime 1.20.1) |
| 파이 | 설비 분류 모델 | `~/shiftlink/models/cnn/{model.onnx,labels.txt}` FP32 sha256 `e2209953b22d…` (`docs/testing/cnn-unity-result-20261008.md`) |
| 파이 | 로그·촬영 사진 | `~/shiftlink/logs/pda.log`, `~/shiftlink/data/scan-shots/` |

모델 파일(`*.onnx`, GGUF)은 저장소에 넣지 않는다. 팀 드라이브·장비에만 있다.

## 2. 처음 설치 (한 번)

**Jetson** (저장소 사본 `~/shiftlink/app`에서, sudo는 사람이 입력)

```bash
DB=/home/jetson/shiftlink/data/mock-mes.sqlite3 ENV_FILE=/home/jetson/shiftlink/aiven.env deploy/install_uploader.sh
DB=/home/jetson/shiftlink/data/mock-mes.sqlite3 deploy/install_service.sh mes        # 기본 hybrid
sudo systemctl set-default multi-user.target                                          # 데스크톱 끔(메모리)
```

SFT 모델 등록은 `docs/guides/sft-judge-model.md`. 모델 digest가 위 표와 같아야 한다.

**라즈베리파이** (저장소 사본에서, 앱 폴더가 아닌 곳)

```bash
sudo apt install -y fcitx5 fcitx5-hangul                                              # 한글 입력
~/shiftlink/venv-face/bin/pip install onnxruntime==1.20.1                             # 설비 분류
SHIFTLINK_CNN=$HOME/shiftlink/models/cnn deploy/install_pda.sh http://jetson-06.tail0a6af3.ts.net:8000 http://127.0.0.1:8090
```

autostart에 `--unity http://127.0.0.1:8090 --cnn … --save-shots …`가 들어간다. 얼굴: `cd ~/shiftlink/app && ~/shiftlink/venv-face/bin/python -m shiftlink.face fetch`, 작업자마다 `… -m shiftlink.face enroll --id E-001`(이미지는 저장하지 않는다).

## 3. 켜는 순서 (시연 당일)

1. **Jetson 전원** → 부팅 약 2분 뒤 확인(4절). 시작할 때 두 모델을 예열하므로 첫 질의 전 약 1분 기다린다.
2. **파이 전원** → 데스크톱 로그인 → PDA 키오스크가 자동으로 뜬다. Jetson이 늦으면 응답할 때까지 5초마다 기다린다.
3. **Unity PC**
   ```powershell
   # 창 1: 파이로 카메라 역터널 (비밀번호는 프롬프트에만 입력)
   ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 -R 127.0.0.1:8090:127.0.0.1:8090 pi@raspberrypi
   # 창 2: Unity 공장 씬 + 플레이 모드
   python -B scripts/run_unity_demo.py --editor <Unity.exe 경로> --mes-url http://jetson-06:8000
   ```
   조작 키·자세한 설명은 `docs/guides/unity-pda-camera-stream.md`.
4. **PDA**: 로그인(얼굴 확인) → **설비 스캔** → Unity 영상이 보이면 작업자를 설비 앞으로 옮겨 화면 가운데 담고 **◉ 촬영** → 설비 자동 선택 → 증상 질의. 시연 질문은 `docs/planning/시연_질문_9개_20261006.md`.

## 4. 확인

| 확인 | 명령 | 정상 |
|---|---|---|
| Jetson 서비스 | `systemctl is-active shiftlink-mes shiftlink-uploader ollama` | `active` 3줄 |
| Jetson 데스크톱 꺼짐 | `systemctl get-default`, `pgrep -c -x gnome-shell` | `multi-user.target`, `0` |
| Jetson 모델 | `ollama list` | 1절 digest 3개 |
| 예열 | `journalctl -u shiftlink-mes -b \| grep 예열` | `[예열] 모델 적재: …` 한 줄 |
| MES HTTP | PC에서 `python scripts/check_mes_http.py --server http://jetson-06.tail0a6af3.ts.net:8000` | 통과(통신 확인용 scan 1건이 남는다) |
| 업로드 대사 | Jetson에서 `set -a; . ~/shiftlink/aiven.env; set +a; python3 scripts/check_upload_recon.py --db ~/shiftlink/data/mock-mes.sqlite3` | 누락 0·충돌 0 (exit 0) |
| 파이 PDA | 파이에서 `curl -s 127.0.0.1:8080/api/unity/config` | `"enabled": true, "shoot": true` |
| Unity 카메라 | 파이에서 `curl -s -o /dev/null -w '%{http_code}' 127.0.0.1:8090/frame.jpg` | `200` (Unity가 멈춰 있으면 503) |
| 파이 로그 | `tail ~/shiftlink/logs/pda.log` | `스캔 촬영 분류: … min_conf=0.8`, 촬영 시 `촬영 확정 HPU conf=0.98 … sent=True` |

10/14 채점 직전 점검은 `ShiftLink-records/experiments/test30_1014/preflight.sh`(저장소 밖, 13항목)를 쓴다.

## 5. 끄는 순서

1. PDA: 화면의 **종료** 버튼 → 파이 `sudo poweroff`.
2. Unity PC: Unity ▶ 버튼으로 플레이 종료, 터널 창 Ctrl+C.
3. Jetson: 업로드 대기 0건 확인(PDA 화면 또는 4절 대사) → `sudo poweroff`. 서비스는 다음 부팅에 자동으로 뜬다.

## 6. 문제가 생기면

| 증상 | 할 일 |
|---|---|
| PDA 스캔 화면 「Unity 카메라 연결 대기」 | 터널 창이 살아 있는지, Unity가 플레이 중인지 확인. PDA는 자동 재연결한다 |
| 「확신도 낮음(…) — 다시 촬영」 | 설비 하나만 가까이·가운데 담아 다시 촬영. 넓은 장면(입구 등)은 오인식한다. 기준 0.8은 바꾸지 않는다 |
| 촬영 버튼이 없다 | 파이 autostart에 `--cnn`이 빠졌거나 모델 폴더가 없다 → 2절 설치 다시 |
| 질의가 25~54초 걸린다 | Jetson 데스크톱·VNC가 켜져 두 번째 모델이 밀려났다 → `~/.local/bin/vnc off`, `multi-user.target` 확인 |
| 질의 503 | 판정 불가 또는 모델 미예열. 30초 뒤 다시. 계속되면 `journalctl -u shiftlink-mes -n 50` |
| 대시보드에 다녀온 뒤 카메라가 안 열림 | PDA 재시작(대시보드의 재시작 버튼 또는 `/pda/restart`) |
| 업로드 대기 건수가 줄지 않는다 | 클라우드 끊김. 업로더는 30초마다 다시 시도하고 대기 건은 재시작해도 남는다(`docs/testing/cloud-cut-test-plan-20261008.md`) |
| 한글이 안 쳐진다 | Ctrl+Space 또는 한/영 키. fcitx5 미설치면 2절 apt |
