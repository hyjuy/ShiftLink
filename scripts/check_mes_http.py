"""Check the MES HTTP contract without camera, PDA, LLM, or cloud calls.

Writes one synthetic scan tagged communication-check; does not control MES.
"""
import argparse
from shiftlink.communication import HTTPClientError, MesHTTPClient


def check(server):
    client = MesHTTPClient(server)
    state = client.get_state()
    assert state.get('is_synthetic') is True
    assert isinstance(state['measurements'], list)
    events = client.get_events()
    assert isinstance(events['events'], list)
    assert isinstance(events['run_id'], str)
    result = client.send_scan('GR', 0.95, 'communication-check')
    scan = result['scan']
    assert scan['class'] == 'GR' and scan['device_id'] == 'communication-check'
    assert scan['equipment_id'] and scan['scan_id']
    recent = client.get_recent_scans(limit=50)
    assert any(s['scan_id'] == scan['scan_id'] for s in recent['scans'])
    try:
        client.send_scan('INVALID', 0.95, 'communication-check')
    except HTTPClientError as error:
        assert error.status_code == 400
    else:
        raise AssertionError('Invalid class must return HTTP 400')
    print('PASS: state/events received, scan recorded and retrieved, invalid scan HTTP 400')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', default='http://127.0.0.1:8000')
    check(parser.parse_args().server)
