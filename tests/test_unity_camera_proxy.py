import json
import unittest
from http.server import BaseHTTPRequestHandler
from tests.test_pda_app import serve, fetch
from shiftlink.pda.__main__ import make_handler


class Camera(BaseHTTPRequestHandler):
    body = b'\xff\xd8frame\xff\xd9'
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.path == '/stream.mjpg':
            part = b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(self.body)).encode()+b'\r\n\r\n'+self.body+b'\r\n'
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Content-Length', str(len(part)))
            self.end_headers(); self.wfile.write(part)
            return
        assert self.path == '/frame.jpg'
        self.send_response(200)
        self.send_header('Content-Type', 'image/jpeg')
        self.send_header('Content-Length', str(len(self.body)))
        self.end_headers()
        self.wfile.write(self.body)


class UnityCameraProxyTests(unittest.TestCase):
    def test_mjpeg_is_forwarded_continuously(self):
        camera, origin = serve(Camera)
        pda, base = serve(make_handler('http://127.0.0.1:9', unity=origin))
        try:
            status, body = fetch(base + '/api/unity/stream')
            self.assertEqual(status, 200)
            self.assertIn(Camera.body, body)
            self.assertTrue(json.loads(fetch(base + '/api/unity/config')[1])['stream_live'])
        finally:
            pda.shutdown(); camera.shutdown()
            pda.server_close(); camera.server_close()
    def test_frame_is_from_unity_not_mes_or_physical_camera(self):
        camera, origin = serve(Camera)
        pda, base = serve(make_handler('http://127.0.0.1:9', unity=origin))
        try:
            self.assertTrue(json.loads(fetch(base + '/api/unity/config')[1])['enabled'])
            self.assertEqual(fetch(base + '/api/unity/frame'), (200, Camera.body))
            self.assertEqual(fetch(base + '/api/state')[0], 502)
        finally:
            pda.shutdown(); camera.shutdown()
            pda.server_close(); camera.server_close()

    def test_missing_and_disconnected_unity_return_errors(self):
        for origin, expected in [(None, 503), ('http://127.0.0.1:9', 502)]:
            pda, base = serve(make_handler('http://127.0.0.1:9', unity=origin))
            try:
                self.assertEqual(fetch(base + '/api/unity/frame')[0], expected)
            finally:
                pda.shutdown(); pda.server_close()

    def test_non_image_response_is_rejected(self):
        handler = type('BadCamera', (Camera,), {'body': b'not an image'})
        camera, origin = serve(handler)
        pda, base = serve(make_handler('http://127.0.0.1:9', unity=origin))
        try:
            self.assertEqual(fetch(base + '/api/unity/frame')[0], 502)
        finally:
            pda.shutdown(); camera.shutdown()
            pda.server_close(); camera.server_close()
