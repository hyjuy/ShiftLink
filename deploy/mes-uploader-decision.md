# MES·업로더 상시 실행 결정 (2026-10-06)

**결정: 업로더를 별도 `shiftlink-uploader.service`로 유지하고, MES가 이를 Wants로 함께 시작하며 동일 SQLite DB를 사용한다.**

네트워크 업로드의 실패·재시작은 MES 가동과 분리한다. 업로더는 `After=shiftlink-mes.service`로 시작 순서만 지정하고, MES가 멈춰도 이미 저장된 pending 항목을 계속 전송한다. 두 서비스 모두 재시작 및 부팅 자동 시작을 사용한다.

설치 시 MES 실행 계정으로, 저장소 루트에서 두 명령을 실행한다. 기본 DB는 둘 다 `mes_data/mock-mes.sqlite3`다. 경로를 바꾸면 **두 설치 명령에 같은 DB 값을 지정한다.**

```bash
DB=/home/jetson/shiftlink/app/mes_data/mock-mes.sqlite3 ENV_FILE=/etc/shiftlink/aiven.env deploy/install_uploader.sh
DB=/home/jetson/shiftlink/app/mes_data/mock-mes.sqlite3 deploy/install_service.sh mes
```

환경 파일에는 기존 MYSQL_DATABASE_URL·MYSQL_SSL_CA를 두고, 서비스 파일이나 저장소에 비밀값을 적지 않는다. 업로더가 이미 등록돼 있어야 MES의 Wants로 시작할 수 있다.

```bash
systemctl status shiftlink-mes shiftlink-uploader
journalctl -u shiftlink-uploader -f
python scripts/check_upload_recon.py
```

Claude 협업 검토 항목: 별도 서비스 결정, 동일 DB 경로, 부팅 순서 및 오프라인 재시도. 실제 서비스 설치·활성화는 이번 변경의 검증 범위에 포함하지 않는다.
