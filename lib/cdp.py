# -*- coding: utf-8 -*-
"""CDP 小工具：连本机 Chrome 的调试端口，读页面、执行 JS、跳转。

不依赖任何浏览器扩展，走 Chrome 自带的远程调试协议。
"""
import json
import os
import sys
import time
import urllib.request

import websocket

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import cfg

PORT = cfg.PORT
SCHOOL = cfg.SCHOOL


def http(path):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.loads(opener.open('http://127.0.0.1:%d%s' % (PORT, path), timeout=5).read())


def pages():
    try:
        return [t for t in http('/json/list') if t.get('type') == 'page']
    except Exception:
        raise SystemExit(
            '连不上浏览器调试端口 %d。\n'
            '请先运行：python step0_open.py（会打开专用窗口，然后你在里面登录）' % PORT)


def find_tab(sub=None, fallback=True):
    ps = pages()
    if sub:
        for t in ps:
            if sub in t.get('url', ''):
                return t
    for t in ps:
        u = t.get('url', '')
        if SCHOOL in u or 'chaoxing' in u:
            return t
    if fallback and ps:
        return ps[0]
    raise RuntimeError('没找到可用的标签页')


def connect(ws_url):
    ws = websocket.create_connection(ws_url, timeout=60, suppress_origin=True)
    _id = [0]

    def cmd(method, **params):
        _id[0] += 1
        i = _id[0]
        ws.send(json.dumps({'id': i, 'method': method, 'params': params}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == i:
                if 'error' in msg:
                    raise RuntimeError(json.dumps(msg['error']))
                return msg.get('result', msg)

    return ws, cmd


def evaluate(cmd, expr, await_promise=False):
    r = cmd('Runtime.evaluate', expression=expr, returnByValue=True, awaitPromise=await_promise)
    res = r.get('result', {})
    if res.get('subtype') == 'error':
        raise RuntimeError(res.get('description', '')[:400])
    if 'exceptionDetails' in r:
        raise RuntimeError(json.dumps(r['exceptionDetails'], ensure_ascii=False)[:400])
    return res.get('value')


def nav(cmd, url, wait=5):
    cmd('Page.navigate', url=url)
    time.sleep(wait)


def main():
    act = sys.argv[1] if len(sys.argv) > 1 else 'list'
    if act == 'list':
        for t in pages():
            print(t.get('title', '')[:50], '|', t.get('url', '')[:130])
    elif act == 'eval':
        t = find_tab(sys.argv[2] if len(sys.argv) > 3 else None)
        ws, cmd = connect(t['webSocketDebuggerUrl'])
        try:
            print(evaluate(cmd, sys.argv[-1]))
        finally:
            ws.close()


if __name__ == '__main__':
    main()
