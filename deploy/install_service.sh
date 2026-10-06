#!/usr/bin/env bash
# 부팅 시 자동 시작 systemd 서비스 등록 (작업계획 E1·D2). 저장소 안에서, 서비스를 돌릴 계정으로 실행한다.
#
#   Jetson (E1):       deploy/install_service.sh mes
#                      DB=/경로/mock-mes.sqlite3 deploy/install_service.sh mes
# 업로더는 별도 서비스: deploy/install_uploader.sh로 먼저 등록한다. MES와 같은 DB= 경로를 지정한다.
#   라즈베리파이 (D2): deploy/install_service.sh vision http://<jetson>:8000 [모델 폴더, 기본 data/vision/model]
#
# 계정·저장소 경로·python(.venv/bin/python, 없으면 python3)은 실행한 장비에서 찾는다. PY=... 로 바꿀 수 있다.
# DRY_RUN=1 이면 등록하지 않고 생성될 unit만 출력한다.
# 확인: systemctl status <이름> · 로그: journalctl -u <이름> -f · 해제: sudo systemctl disable --now <이름>
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
RUN_AS="${SUDO_USER:-$(id -un)}"
EXTRA=""
WANTS="network-online.target"

case "${1:-}" in
  mes)
    NAME=shiftlink-mes
    DESC="ShiftLink 모의 MES 서버 (Jetson, 파이·PDA 화면이 접속)"
    AFTER="network-online.target ollama.service"
    DB="${DB:-$REPO/mes_data/mock-mes.sqlite3}"
    WANTS="$WANTS shiftlink-uploader.service"
    EXEC="\"$PY\" -m shiftlink.mes --host 0.0.0.0 --port 8000 --db \"$DB\""
    ;;
  vision)
    SERVER="${2:?Jetson 주소가 필요합니다: $0 vision http://<jetson>:8000}"
    MODEL="${3:-$REPO/data/vision/model}"
    if [ ! -f "$MODEL/model.onnx" ] && [ -z "${DRY_RUN:-}" ]; then
      echo "모델 없음: $MODEL/model.onnx (PC에서 학습한 model.onnx·labels.txt를 먼저 복사)" >&2; exit 1
    fi
    NAME=shiftlink-vision
    DESC="ShiftLink 웹캠 설비 분류 → Jetson 전송 (라즈베리파이)"
    AFTER="network-online.target"
    EXEC="$PY -m shiftlink.vision.classify --headless --model $MODEL --server $SERVER --device-id $(hostname)"
    EXTRA="SupplementaryGroups=video"  # /dev/video* 접근
    ;;
  *)
    sed -n '2,9p' "$0" >&2; exit 2
    ;;
esac

# 카메라·네트워크가 부팅 직후 준비 안 됐거나 Jetson이 늦게 떠도 5초마다 다시 시작한다.
UNIT="[Unit]
Description=$DESC
After=$AFTER
Wants=$WANTS

[Service]
User=$RUN_AS
WorkingDirectory=$REPO
Environment=PYTHONUNBUFFERED=1
ExecStart=$EXEC
Restart=always
RestartSec=5
$EXTRA

[Install]
WantedBy=multi-user.target"

if [ -n "${DRY_RUN:-}" ]; then
  printf '# /etc/systemd/system/%s.service\n%s\n' "$NAME" "$UNIT"
  exit 0
fi

printf '%s\n' "$UNIT" | sudo tee "/etc/systemd/system/$NAME.service" >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now "$NAME"
systemctl --no-pager --lines=5 status "$NAME" || true
echo "로그: journalctl -u $NAME -f"
