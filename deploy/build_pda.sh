#!/usr/bin/env bash
# 라즈베리파이 PDA 실행파일 빌드·설치. 저장소 안에서, 파이(aarch64)에서 실행한다 (실행파일은 빌드한 CPU에서만 돈다).
#
#   deploy/build_pda.sh [Jetson 주소, 기본 http://jetson-06.tail0a6af3.ts.net:8000]
#
# 결과: ~/shiftlink/app/shiftlink-pda (화면 파일 내장, /api/* 는 Jetson으로)
#       ~/.config/autostart/shiftlink-pda.desktop (데스크톱 로그인 시 자동 실행)
# 해제: ~/.config/autostart/shiftlink-pda.desktop 을 지운다. 앱 닫기: Alt+F4 · 로그: ~/shiftlink/logs/pda.log
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
JETSON="${1:-http://jetson-06.tail0a6af3.ts.net:8000}"
APP="$HOME/shiftlink/app"
BUILD="$HOME/.cache/shiftlink-pda-build"

python3 -m venv "$BUILD/venv"
"$BUILD/venv/bin/pip" install -q pyinstaller
"$BUILD/venv/bin/pyinstaller" --onefile --noconfirm --name shiftlink-pda \
  --distpath "$APP" --workpath "$BUILD/work" --specpath "$BUILD" \
  --paths "$REPO" --add-data "$REPO/shiftlink/mes/web:shiftlink/mes/web" \
  "$REPO/shiftlink/pda/__main__.py"

mkdir -p "$HOME/shiftlink/logs" "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/shiftlink-pda.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ShiftLink PDA
Exec=sh -c '$APP/shiftlink-pda --jetson $JETSON >> $HOME/shiftlink/logs/pda.log 2>&1'
EOF
rm -f "$HOME/.config/autostart/pda-kiosk.desktop"  # 이전 키오스크 스크립트(pda_kiosk.sh) 대체
echo "설치: $APP/shiftlink-pda → API $JETSON"
