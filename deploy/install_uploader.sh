#!/usr/bin/env bash
# Jetson: 인계 outbox → Aiven 업로더를 부팅 시 자동 시작 systemd 서비스로 등록한다. 저장소 안에서, MES를 돌리는 계정으로 실행한다.
#
#   deploy/install_uploader.sh                      # 기본: DB mes_data/mock-mes.sqlite3(MES와 같은 파일), 주기 30초, 접속 정보는 저장소 .env
#   DB=/경로/mock-mes.sqlite3 INTERVAL=30 ENV_FILE=/etc/shiftlink/aiven.env deploy/install_uploader.sh
#
# ENV_FILE은 MYSQL_DATABASE_URL·MYSQL_SSL_CA 줄이 든 파일(저장소 밖 권장, chmod 600). 없으면 저장소 .env를 쓴다. 비밀값은 이 스크립트·unit에 적지 않는다.
# 클라우드가 끊겨도 서비스는 죽지 않고 다음 주기에 다시 올린다(끊김 시험 W3-3). DRY_RUN=1 이면 등록하지 않고 unit만 출력한다.
# 확인: systemctl status shiftlink-uploader · 로그: journalctl -u shiftlink-uploader -f · 대사: python scripts/check_upload_recon.py
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PY:-$REPO/.venv/bin/python}"
[ -x "$PY" ] || PY="$(command -v python3)"
RUN_AS="${SUDO_USER:-$(id -un)}"
DB="${DB:-$REPO/mes_data/mock-mes.sqlite3}"
INTERVAL="${INTERVAL:-30}"
NAME=shiftlink-uploader

if [ -n "${ENV_FILE:-}" ]; then
  [ -r "$ENV_FILE" ] || [ -n "${DRY_RUN:-}" ] || { echo "ENV_FILE을 읽을 수 없음: $ENV_FILE" >&2; exit 1; }
  # 따옴표로 감싸지 않는다: systemd 249(Jetson)는 따옴표 경로를 "절대 경로 아님"으로 무시한다. 값 전체가 경로라 공백도 그대로 된다.
  ENVLINE="EnvironmentFile=$ENV_FILE"
else
  [ -f "$REPO/.env" ] || [ -n "${DRY_RUN:-}" ] || { echo "접속 정보 없음: $REPO/.env (또는 ENV_FILE=...)" >&2; exit 1; }
  ENVLINE=""
fi

UNIT="[Unit]
Description=ShiftLink 인계 및 질의 outbox → Aiven 업로더 (Jetson)
After=network-online.target shiftlink-mes.service
Wants=network-online.target

[Service]
User=$RUN_AS
WorkingDirectory=$REPO
Environment=PYTHONUNBUFFERED=1
$ENVLINE
ExecStart=\"$PY\" -m shiftlink.mes.uploader --db \"$DB\" --interval $INTERVAL
Restart=always
RestartSec=5

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
