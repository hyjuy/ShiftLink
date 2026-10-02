#!/bin/sh
# 라즈베리파이 모니터에 PDA 화면을 전체 화면으로 띄운다 (작업계획 D3).
# Jetson MES 서버가 응답할 때까지 5초마다 기다렸다가 Chromium 키오스크를 연다.
#
#   설치: cp deploy/pda_kiosk.sh ~/.local/bin/ 후 ~/.config/autostart/pda-kiosk.desktop 에
#         Exec=/home/pi/.local/bin/pda_kiosk.sh [PDA 주소] 를 적는다.
#   해제: ~/.config/autostart/pda-kiosk.desktop 을 지운다. 키오스크 닫기: Alt+F4
#   SCALE: 화면 배율. PDA는 세로 휴대폰 폭 기준이라 2560x1600 모니터에서 2가 높이에 맞다.
#   한글이 네모로 나오면: sudo apt install fonts-noto-cjk
URL="${1:-http://jetson-06.tail0a6af3.ts.net:8000/pda.html}"
SCALE="${SCALE:-2}"
until curl -sf -m 5 -o /dev/null "$URL"; do sleep 5; done
# labwc에서는 --kiosk만으로는 일반 창으로 떠서 --app·--start-fullscreen을 같이 준다.
exec chromium --ozone-platform=wayland --force-device-scale-factor="$SCALE" \
  --lang=ko --disable-features=Translate \
  --kiosk --start-fullscreen --noerrdialogs --no-first-run --password-store=basic --app="$URL"
