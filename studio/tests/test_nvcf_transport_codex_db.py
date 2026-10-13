"""Independent local transport regressions for the NVCF operation deadline.

No external service, GPU, credentials, or paid operation is used.
"""
import hashlib
import json
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import server  # isolated DB configured by studio/tests/conftest.py

REPO = Path(server.__file__).resolve().parent.parent


@pytest.mark.parametrize('scenario', ['immediate_success', 'slow_post_headers', 'trickle_post_body', 'trickle_get_body', 'poll_sleep'])
def test_deadline_controls(scenario):
    class Handler(BaseHTTPRequestHandler):
        def answer(self, trickle=False):
            body=b'{"ok":true}'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            try:
                for b in body:
                    self.wfile.write(bytes([b]))
                    self.wfile.flush()
                    if trickle: time.sleep(.2)
            except OSError: pass
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if scenario in ('trickle_get_body', 'poll_sleep'):
                self.send_response(202)
                self.send_header('NVCF-REQID','local-owned-probe')
                self.send_header('Content-Length','0')
                self.end_headers()
            else:
                if scenario == 'slow_post_headers': time.sleep(2)
                self.answer(scenario == 'trickle_post_body')
        def do_GET(self): self.answer(scenario == 'trickle_get_body')
        def log_message(self, *args): pass
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    t=threading.Thread(target=httpd.serve_forever,daemon=True)
    t.start()
    response=None
    exception=None
    start=time.monotonic()
    try:
        base=f'http://127.0.0.1:{httpd.server_port}'
        try:
            response=server._nim_invoke(base+'/invoke',{}, {}, timeout=1, poll_base=base+'/status',poll_interval=3 if scenario=='poll_sleep' else .01)
        except Exception as exc: exception=type(exc).__name__
        elapsed=time.monotonic()-start
    finally:
        httpd.shutdown()
        httpd.server_close()
        t.join(timeout=3)
    observed=dict(scenario=scenario,elapsed=elapsed,timeout=1,response=response,exception=exception,module=server.__file__)
    if scenario=='immediate_success': assert response=={'ok':True} and exception is None, observed
    else: assert exception=='TimeoutError', observed
    assert elapsed<1.5, observed


def test_trickling_headers_respect_total_deadline():
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            try:
                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Slow: ')
                self.wfile.flush()
                for _ in range(20):
                    self.wfile.write(b'x')
                    self.wfile.flush()
                    time.sleep(.1)
                self.wfile.write(b'\r\nContent-Length: 2\r\n\r\n{}')
                self.wfile.flush()
            except OSError: pass
        def log_message(self,*args): pass
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    t=threading.Thread(target=httpd.serve_forever,daemon=True)
    t.start()
    caught=None
    start=time.monotonic()
    try:
        try: server._nim_invoke(f'http://127.0.0.1:{httpd.server_port}/',{}, {},timeout=1)
        except Exception as exc: caught=type(exc).__name__
        elapsed=time.monotonic()-start
    finally:
        httpd.shutdown();httpd.server_close();t.join(3)
    data={'exception':caught,'elapsed':elapsed,'timeout':1,'module':server.__file__}
    assert caught=='TimeoutError' and elapsed<1.5,data


def test_timeout_releases_concurrent_http_work():
    source_hash=hashlib.sha256((REPO/'studio/server.py').read_bytes()).hexdigest()
    stop=threading.Event()
    lock=threading.Lock()
    state={'active':0,'peak':0}
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            with lock:
                state['active']+=1
                state['peak']=max(state['peak'],state['active'])
            try:
                self.send_response(200)
                self.send_header('Content-Length','100000')
                self.end_headers()
                end=time.monotonic()+3
                while not stop.is_set() and time.monotonic()<end:
                    self.wfile.write(b' ')
                    self.wfile.flush()
                    stop.wait(.03)
            except OSError: pass
            finally:
                with lock: state['active']-=1
        def log_message(self,*args): pass
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    accept=threading.Thread(target=httpd.serve_forever,daemon=True)
    accept.start()
    def invoke(_):
        start=time.monotonic()
        try:
            server._nim_invoke(f'http://127.0.0.1:{httpd.server_port}/invoke',{}, {},timeout=.2)
            error=None
        except Exception as exc: error=type(exc).__name__
        return {'elapsed':time.monotonic()-start,'exception':error}
    try:
        with ThreadPoolExecutor(max_workers=8) as pool: results=list(pool.map(invoke,range(8)))
        time.sleep(.3)
        with lock: active=state['active']; peak=state['peak']
    finally:
        stop.set()
        httpd.shutdown()
        httpd.server_close()
        accept.join(2)
    observed={'repo':str(REPO),'server_sha256':source_hash,'results':results,'active_after_callers_settled_plus_300ms':active,'peak':peak}
    assert all(r['exception']=='TimeoutError' and r['elapsed']<.7 for r in results),observed
    assert active==0,observed


def test_resolver_stall_respects_operation_deadline(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            self.send_response(200);self.send_header('Content-Length','2');self.end_headers()
            try:self.wfile.write(b'{}')
            except OSError:pass
        def log_message(self,*args):pass
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    t=threading.Thread(target=httpd.serve_forever,daemon=True);t.start()
    original=socket.getaddrinfo;original_popen=subprocess.Popen
    resolver_calls=[];children=[]
    def delayed(*args,**kwargs):
        resolver_calls.append(str(args[0]));time.sleep(1)
        return original(*args,**kwargs)
    def delayed_helper(args,*positional,**kwargs):
        # Inject a stalled owned helper at the OS process boundary, using a real
        # process. No application test flag or production code patch is needed.
        child=original_popen([sys.executable,'-c','import time; time.sleep(1)'],*positional,**kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(socket,'getaddrinfo',delayed)
    monkeypatch.setattr(subprocess,'Popen',delayed_helper)
    start=time.monotonic();caught=None
    try:
        try:server._nim_invoke(f'http://localhost:{httpd.server_port}/',{}, {},timeout=.2)
        except Exception as exc:caught=type(exc).__name__
        elapsed=time.monotonic()-start
        live_children=[p.pid for p in children if p.poll() is None]
    finally:
        for child in children:
            if child.poll() is None:child.kill()
            child.wait(timeout=3)
        httpd.shutdown();httpd.server_close();t.join(3)
    observed={'timeout':.2,'injected_delay':1,'elapsed':elapsed,'exception':caught,'module':server.__file__,'resolver_calls':resolver_calls,'helper_pids':[p.pid for p in children],'live_children_after_return':live_children}
    assert resolver_calls or children,'Fault injection did not reach resolver/helper boundary'
    assert caught=='TimeoutError' and elapsed<.7 and not live_children,observed


def test_hostname_success_reaps_resolver(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length',0)))
            body=b'{"hostname":"worked"}'
            self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    t=threading.Thread(target=httpd.serve_forever,daemon=True);t.start()
    original=subprocess.Popen;children=[]
    def track(*args,**kwargs):
        p=original(*args,**kwargs);children.append(p);return p
    monkeypatch.setattr(subprocess,'Popen',track)
    start=time.monotonic()
    try:
        result=server._nim_invoke(f'http://localhost:{httpd.server_port}/',{}, {},timeout=5)
        elapsed=time.monotonic()-start
    finally:httpd.shutdown();httpd.server_close();t.join(3)
    live=[p.pid for p in children if p.poll() is None]
    observed={'result':result,'elapsed':elapsed,'helper_pids':[p.pid for p in children],'live_children':live,'module':server.__file__}
    assert result=={'hostname':'worked'} and elapsed<5 and not live,observed

