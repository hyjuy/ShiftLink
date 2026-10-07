#!/usr/bin/env bash
# 라즈베리파이 PDA 화면 설치 (MES 대시보드는 Jetson이 서빙, 파이의 / 는 Jetson으로 이동). 저장소 안에서, 파이에서 실행한다.
# 화면은 파이가 서빙하고 Jetson은 API만 맡는다.
# 얼굴 점수는 OpenCV가 있는 ~/shiftlink/venv-face 로 띄운다. 설비 분류(install_service.sh)의 .venv와 합치지 않는다.
# 이유는 얼굴(OpenCV·YuNet/SFace)과 설비 분류 의존성을 따로 관리하기 위해서다. 웹캠은 로그인만 쓴다.
#
#   deploy/install_pda.sh [Jetson 주소, 기본 http://jetson-06.tail0a6af3.ts.net:8000]
#   PY=/다른/python deploy/install_pda.sh
#   모델이 없어 시연만 통과시키려면: SHIFTLINK_FACE_BYPASS=1 deploy/install_pda.sh
#   (서버는 127.0.0.1만 연다. 기본은 우회 끔)
#
# 결과: ~/shiftlink/app/shiftlink/{pda,face,mes/web/pda.*}
#       ~/.config/autostart/shiftlink-pda.desktop
# 해제: 그 desktop 파일을 지운다. 로그: ~/shiftlink/logs/pda.log
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
JETSON="${1:-http://jetson-06.tail0a6af3.ts.net:8000}"
APP="$HOME/shiftlink/app"
PY="${PY:-$HOME/shiftlink/venv-face/bin/python}"

if [ ! -x "$PY" ] || ! "$PY" -c "import cv2" >/dev/null 2>&1; then
  echo "얼굴용 Python이 없습니다: $PY (cv2 필요). 설비 분류 .venv와 의존성을 따로 둡니다." >&2
  exit 1
fi

mkdir -p "$APP/shiftlink/mes" "$HOME/shiftlink/logs" "$HOME/.config/autostart"
rm -rf "$APP/shiftlink/pda" "$APP/shiftlink/face" "$APP/shiftlink/mes/web"
cp -r "$REPO/shiftlink/pda" "$APP/shiftlink/pda"
cp -r "$REPO/shiftlink/face" "$APP/shiftlink/face"
mkdir -p "$APP/shiftlink/mes/web"
cp "$REPO/shiftlink/mes/web/pda.html" "$REPO/shiftlink/mes/web/pda.js" "$APP/shiftlink/mes/web/"
touch "$APP/shiftlink/__init__.py"

BYPASS=""
if [ "${SHIFTLINK_FACE_BYPASS:-}" = "1" ]; then
  BYPASS="SHIFTLINK_FACE_BYPASS=1 "
fi

cat > "$HOME/.config/autostart/shiftlink-pda.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ShiftLink PDA
# 모델이 없을 때만 시연 우회: 위의 Exec 앞에 SHIFTLINK_FACE_BYPASS=1 을 넣고 다시 로그인한다. 기본은 끄다.
Exec=sh -c 'cd $APP && exec ${BYPASS}$PY -m shiftlink.pda --jetson $JETSON >> $HOME/shiftlink/logs/pda.log 2>&1'
EOF
echo "설치: $APP ($PY -m shiftlink.pda) → API $JETSON"
