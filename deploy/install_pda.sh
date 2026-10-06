#!/usr/bin/env bash
# 라즈베리파이 PDA 화면 설치 (MES 대시보드는 Jetson이 서빙, 파이의 / 는 Jetson으로 이동). 저장소(또는 shiftlink/pda·shiftlink/mes/web 사본) 안에서, 파이에서 실행한다.
# 화면은 파이가 서빙하고 Jetson은 API만 맡는다. 파이 기본 python3만 쓴다(추가 패키지 없음).
#
#   deploy/install_pda.sh [Jetson 주소, 기본 http://jetson-06.tail0a6af3.ts.net:8000]
#
# 결과: ~/shiftlink/app/shiftlink/{pda,mes/web/pda.*} (화면 수정 반영 = 이 스크립트 다시 실행 후 앱 재시작)
#       ~/.config/autostart/shiftlink-pda.desktop (데스크톱 로그인 시 Chromium 키오스크로 PDA)
# 해제: ~/.config/autostart/shiftlink-pda.desktop 을 지운다. 앱 닫기: Alt+F4 · 로그: ~/shiftlink/logs/pda.log
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
JETSON="${1:-http://jetson-06.tail0a6af3.ts.net:8000}"
APP="$HOME/shiftlink/app"

mkdir -p "$APP/shiftlink/mes" "$HOME/shiftlink/logs" "$HOME/.config/autostart"
rm -rf "$APP/shiftlink/pda" "$APP/shiftlink/mes/web"
cp -r "$REPO/shiftlink/pda" "$APP/shiftlink/pda"
mkdir -p "$APP/shiftlink/mes/web"
cp "$REPO/shiftlink/mes/web/pda.html" "$REPO/shiftlink/mes/web/pda.js" "$APP/shiftlink/mes/web/"
touch "$APP/shiftlink/__init__.py"

cat > "$HOME/.config/autostart/shiftlink-pda.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ShiftLink PDA
Exec=sh -c 'cd $APP && exec python3 -m shiftlink.pda --jetson $JETSON >> $HOME/shiftlink/logs/pda.log 2>&1'
EOF
echo "설치: $APP (python3 -m shiftlink.pda) → API $JETSON"
