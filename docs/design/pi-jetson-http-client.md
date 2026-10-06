# 라즈베리파이–Jetson HTTP 통신

## 역할과 범위

Jetson의 기존 `shiftlink.mes` 서버가 MES 상태·이벤트를 제공하고 인식 결과·질의·인계를 받는다. 라즈베리파이의 Python 프로그램은 `shiftlink.communication.http_client.MesHTTPClient`를 사용한다. HTTP 클라이언트는 Python 표준 라이브러리만 사용한다.

브라우저 PDA는 기존 `shiftlink.pda`의 `/api/*` 프록시를 그대로 사용한다. JavaScript 화면에서 Python 클라이언트를 직접 호출하지 않으며, 새 프록시나 CORS 설정은 추가하지 않는다. 모델 실행·화면 구현·클라우드 업로드는 이 통신 모듈의 범위에 포함하지 않는다.

## 요청 계약

| 메서드 | 경로 | 클라이언트 함수 |
|---|---|---|
| POST | `/api/equipment/scan` | `send_scan(label, confidence, device_id, ts=None)` |
| GET | `/api/equipment/scan/recent?limit=5` | `get_recent_scans(limit=5)` |
| GET | `/api/state` | `get_state()` |
| GET | `/api/events?after_sequence=-1` | `get_events(after_sequence=-1)` |
| POST | `/api/query` | `query(question, equipment_id=None, scan_id=None, k=5)` |
| POST | `/api/handover` | `save_handover(handover_id, memo_text)` |

호출 결과는 JSON 객체다. HTTP 오류는 `HTTPClientError.status_code`로 구분하고, 연결 실패·유효하지 않은 JSON 응답은 `status_code=None`이다. 일반 요청의 기본 타임아웃은 5초, 질의는 125초다.

## 사용 예

프로젝트 루트에서 Python 프로그램이 다음과 같이 호출한다. 장치별 주소는 호출자가 설정으로 전달한다.

```python
from shiftlink.communication import MesHTTPClient

client = MesHTTPClient("http://jetson-06:8000")
scan = client.send_scan("GR", 0.95, "pi-01")["scan"]
state = client.get_state()
answer = client.query("갈리는 소리가 나요", scan_id=scan["scan_id"])
saved = client.save_handover("HO-demo-001", "GR-01 점검 내용을 다음 조에 전달")
```

## 실패와 재전송

- 클라이언트는 POST를 자동 재전송하지 않는다. 응답을 못 받았어도 서버가 처리했을 수 있다.
- 인계 재전송은 같은 `handover_id`와 같은 메모를 유지한다. 같은 ID에 다른 내용을 보내면 서버가 409를 반환한다.
- 서버 재시작 후 인식 기록은 사라진다. 인계는 SQLite에 남는다.
- 이벤트 `run_id`가 바뀌면 호출자는 이전 커서를 초기화한다. 같은 `sequence`에 여러 이벤트가 있을 수 있으므로 sequence만으로 중복 제거하지 않는다.
- 폴링·마지막 수신 시각·화면의 연결 끊김 표시는 PDA 또는 호출 프로그램이 담당한다.
- 센서값은 현재 모의 MES가 생성하는 합성 데이터다.

## 확인

```bash
python -m scripts.check_mes_http --server http://jetson-06:8000
python -m unittest discover -s tests -p 'test_communication*.py' -v
```

첫 명령은 테스트 인식 결과 한 건을 실제 서버에 기록한다. 질의·인계 통합 테스트는 임시 로컬 서버·임시 SQLite·가짜 모델을 사용해 기존 Jetson과 클라우드에 영향을 주지 않는다.
