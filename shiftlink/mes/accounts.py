"""MES account verification and administrator-only operator registration."""
from __future__ import annotations
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
import time
from pathlib import Path

class Accounts:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.failures = []
        self.sessions = {}
        self.session_actors = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                pass
            else:
                with os.fdopen(fd, 'w') as out:
                    json.dump([{'id':'admin','name':'MES 관리자','role':'admin',
                                'salt':'53686966744c696e6b4d455341646d696e','hash':'d59d0ea33866c6674cc05ca9b406c5ed3ed9404491112a43e90498f1722bae6711635de72ad763ba0e01007523ac6a287b274e9d49d224b4f12c2c8c9ca94a91'}], out)

    def _read(self):
        rows = json.loads(self.path.read_text())
        if not isinstance(rows, list):
            raise ValueError('계정 저장소를 확인해 주세요.')
        return rows

    @staticmethod
    def _public(row):
        return {key:row[key] for key in ('id','name','role')}

    def administrator(self, token):
        with self.lock:
            if self.sessions.get(token,0)<=time.monotonic():
                self.sessions.pop(token,None);self.session_actors.pop(token,None)
                return None
            actor=self.session_actors.get(token)
            return dict(actor) if actor and actor['role']=='admin' else None

    def request(self, method, path, payload=None, token=''):
        payload = payload or {}
        try:
            with self.lock:
                return self._request(method, path, payload, token)
        except (ValueError, KeyError, TypeError):
            return 400, {'error':'계정 정보 또는 입력 내용을 확인해 주세요.'}
        except OSError:
            return 503, {'error':'계정 저장소에 접근할 수 없습니다.'}

    def _request(self, method, path, payload, token):
        now = time.monotonic()
        self.sessions = {key:expires for key,expires in self.sessions.items() if expires > now}
        self.session_actors = {key:actor for key,actor in self.session_actors.items() if key in self.sessions}
        rows = self._read()
        if method == 'POST' and path in ('/api/admin/login','/api/account/login'):
            employee, password = payload.get('id'), payload.get('password')
            if not isinstance(employee,str) or not isinstance(password,str) or not 1 <= len(password) <= 256:
                return 400, {'error':'사번과 비밀번호를 입력해 주세요.'}
            self.failures = [stamp for stamp in self.failures if now - stamp < 60]
            if len(self.failures) >= 5:
                return 429, {'error':'로그인 시도가 많습니다. 1분 후 다시 시도해 주세요.'}
            role = 'admin' if path == '/api/admin/login' else 'operator'
            row = next((row for row in rows if row['id'] == employee.strip() and row['role'] == role), None)
            salt = bytes.fromhex(row['salt']) if row else b'\0' * 16
            digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
            if not row or not hmac.compare_digest(digest,row['hash']):
                self.failures.append(now)
                return 401, {'error':'사번 또는 비밀번호가 올바르지 않습니다.'}
            self.failures.clear()
            if role == 'admin':
                session = secrets.token_urlsafe(32)
                self.sessions[session] = now + 3600
                self.session_actors[session] = self._public(row)
                return 200, {'token':session,'name':row['name'],'role':'admin'}
            return 200, {'operator':{'id':row['id'],'name':row['name']}}
        if path.startswith('/api/admin/'):
            if token not in self.sessions:
                return 401, {'error':'MES 관리자 로그인이 필요합니다.'}
            if method == 'POST' and path == '/api/admin/logout':
                self.sessions.pop(token,None)
                self.session_actors.pop(token,None)
                return 200, {'ok':True}
            if method == 'GET' and path == '/api/admin/accounts':
                return 200, {'accounts':[self._public(row) for row in rows]}
            if method == 'POST' and path == '/api/admin/accounts':
                employee, name, password = payload.get('id'), payload.get('name'), payload.get('password')
                if not isinstance(employee,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,16}',employee.strip()):
                    return 400, {'error':'사번은 영문·숫자·밑줄·하이픈으로 16자 이내로 입력해 주세요.'}
                if not isinstance(name,str) or not name.strip() or len(name)>80 or not isinstance(password,str) or not 8<=len(password)<=256:
                    return 400, {'error':'성명과 8자 이상의 비밀번호를 입력해 주세요.'}
                employee = employee.strip()
                if any(row['id']==employee for row in rows):
                    return 409, {'error':'이미 등록된 사번입니다.'}
                salt=secrets.token_bytes(16)
                row={'id':employee,'name':name.strip(),'role':'operator','salt':salt.hex(),
                     'hash':hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1).hex()}
                rows.append(row)
                with tempfile.NamedTemporaryFile(mode='w',dir=self.path.parent,delete=False) as out:
                    temporary=Path(out.name)
                    try:
                        json.dump(rows,out);out.flush();os.fsync(out.fileno())
                    except BaseException:
                        temporary.unlink(missing_ok=True)
                        raise
                try:
                    os.replace(temporary,self.path)
                finally:
                    temporary.unlink(missing_ok=True)
                return 201, {'operator':{'id':row['id'],'name':row['name']}}
        return 404, {'error':'지원하지 않는 요청입니다.'}
