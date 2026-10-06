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

## H3 리뷰 반영

- 업로더의 접속·전송·로컬 조회 오류는 JSON 로그에 예외 클래스와 숫자 오류 코드만 남긴다. 메시지와 접속 문자열은 출력하지 않는다. pending 조회 실패 시 건수는 알 수 없으므로 `null`로 표시하고 다음 주기에 다시 조회한다.
- 파일 SQLite는 WAL과 5초 busy timeout을 사용한다. WAL에서도 쓰기는 직렬화되므로 대기 시간을 넘는 락 오류는 재시도 대상이다. DB와 WAL 파일은 같은 장비의 로컬 디스크에 둔다.
- MES는 `Wants=ollama.service`로 Ollama 시작을 요청한다. 이는 모델 등록·로드·응답 준비를 보장하지 않는다. 준비 확인과 판정 실패 시 응답 중단 정책은 별도 결정 사항이며, 현재의 판정 생략 동작은 유지한다.
- 공백이 있는 `EnvironmentFile` 경로는 인용한다. `WorkingDirectory`는 공백을 포함한 값 전체를 경로로 해석하므로 기존 형식을 유지한다. 실제 `systemd-analyze verify`에서 `WorkingDirectory`를 큰따옴표로 감싸면 절대 경로 오류가 나고, 기존 형식은 통과하는 것을 확인했다. `%`, `$`, 따옴표 등 systemd 해석에 영향을 주는 특수 문자가 있는 경로는 이번 검증 범위에 포함하지 않는다.

## 실제 Jetson 등록 후 검증

아래는 현장 검증 절차이며 이 문서를 작성하면서 실제 장비에서 실행한 결과가 아니다. 서비스 중단·재부팅·네트워크 단절은 시험 가능한 시간에 수행한다.

1. `systemctl is-enabled shiftlink-mes shiftlink-uploader`가 둘 다 `enabled`인지 확인한다. `systemctl show -p Wants -p After shiftlink-mes shiftlink-uploader`로 의존성과 순서를 확인한다.
2. `systemctl cat shiftlink-mes shiftlink-uploader`로 `--db`가 같은 파일인지 확인한다. 공백 경로를 쓰면 두 서비스의 실제 시작까지 확인한다.
3. 재부팅 후 1~2분 안에 `systemctl is-active shiftlink-mes shiftlink-uploader`가 둘 다 `active`인지, `journalctl -u shiftlink-uploader -b`에 주기 JSON 로그가 남는지 확인한다.
4. `systemctl stop shiftlink-mes` 후 업로더가 계속 실행되는지 확인한다. MES를 다시 시작하고 `systemctl kill --kill-whom=main -s KILL shiftlink-uploader` 후 재시작 대기 5초와 초기화 시간이 지난 뒤 업로더 복구 및 MES 유지 여부를 확인한다.
5. 네트워크를 끊은 뒤 인계 2건·질의 2건을 생성해 `/api/outbox`의 pending이 각각 2인지 확인한다. 복구 후 다음 전송 주기와 접속 소요 시간이 지난 뒤 각각 0인지 확인한다. `python scripts/check_upload_recon.py`는 인계만 대사하므로 인계 누락 0·충돌 0 및 종료 코드 0을 확인하고, 질의 2건은 클라우드 `query_upload`에서 ID와 payload 해시를 별도로 확인한다. DB 경로를 바꿨다면 대사 명령에도 같은 `--db`를 지정한다.
6. pending 항목이 있는 상태에서 시험용 환경 파일의 CA 경로를 잘못 지정하고 업로더를 재시작한다. JSON의 `error`에 오류 클래스가 보이고 비밀값이 없는지 확인한 뒤 정상 설정으로 복구한다. 오류 클래스·코드만으로 상세 원인이 특정되지 않을 수 있으므로 CA 파일 존재·권한은 별도로 확인한다.
7. `ollama list`에 `exaone-sft-judge`가 등록됐는지 확인하고 질의 하나를 보내 모델 응답까지 확인한다. 첫 로드는 20초 넘게 걸릴 수 있다. 모델 누락 시 판정이 생략된다는 점은 `docs/guides/sft-judge-model.md`를 따른다.
