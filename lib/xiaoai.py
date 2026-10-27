# -*- coding: utf-8 -*-
"""构建「小哀学习通助手」的注入包。

为什么不用装油猴扩展：直接把 jQuery + 兼容层 + 脚本本体拼成一段 JS，
用调试协议塞进页面执行，效果一样但不需要用户装任何插件。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import cfg

ASSETS = os.path.join(cfg.HERE, 'assets')
JQ = os.path.join(ASSETS, 'jquery.min.js')
FONT = os.path.join(ASSETS, 'font_table.json')
USER_JS = os.path.join(ASSETS, 'xiaoai.user.js')


def settings():
    a = cfg.CONFIG['api']
    if not a.get('key') or '填' in str(a.get('key')):
        raise SystemExit('还没填 API 密钥。打开 config.json，把 api.key 改成你自己的密钥。')
    return {
        'apiKey': a['key'],
        'baseURL': a['base'],
        'model': a['model'],
        'rate': '1',
        'requestInterval': '1',
        'time': '800',
        'aiVote': '1',
        'accuracy': '60',
        'sub': 'true',
        'force': 'true',
        'decrypt': 'true',
        'antiDetect': 'false',
        'jsonMode': 'true',
        'fuzzyMatch': 'true',
        'useCache': 'true',
        'randomDo': 'true',
        'alterTitle': 'false',
        'examTurn': 'false',
        'redo': 'false',
    }


POLYFILL = r"""
(function () {
  if (window.__XA_INJECTED__) { return; }
  window.__XA_INJECTED__ = true;
  if (typeof window.unsafeWindow === 'undefined') { window.unsafeWindow = window; }
  window.GM_setValue = function (k, v) { try { localStorage.setItem(k, String(v)); } catch (e) {} };
  window.GM_getValue = function (k, d) {
    try { var v = localStorage.getItem(k); if (v !== null) return v; } catch (e) {}
    return d;
  };
  window.GM_deleteValue = function (k) { try { localStorage.removeItem(k); } catch (e) {} };
  window.GM_listValues = function () {
    var out = []; for (var i = 0; i < localStorage.length; i++) out.push(localStorage.key(i)); return out;
  };
  window.GM_addStyle = function (css) {
    var s = document.createElement('style'); s.textContent = css;
    (document.head || document.documentElement).appendChild(s); return s;
  };
  window.GM_info = { script: { name: '小哀学习通助手', version: '1.1.0', namespace: 'xiaoai.chaoxing' } };
  window.GM_getResourceText = function (name) {
    if (name === 'fontTable') return window.__XA_FONT_TABLE__ || '';
    return '';
  };
  window.GM_getResourceURL = function () { return ''; };
  window.GM_xmlhttpRequest = function (opt) {
    try {
      var x = new XMLHttpRequest();
      x.open(opt.method || 'GET', opt.url, true);
      if (opt.responseType) { try { x.responseType = opt.responseType; } catch (e) {} }
      var h = opt.headers || {};
      for (var k in h) { if (h.hasOwnProperty(k)) { try { x.setRequestHeader(k, h[k]); } catch (e) {} } }
      if (opt.timeout) { try { x.timeout = opt.timeout; } catch (e) {} }
      x.onreadystatechange = function () {
        if (x.readyState !== 4) return;
        var res = { status: x.status, statusText: x.statusText,
                    responseText: x.responseText, response: x.response,
                    responseHeaders: x.getAllResponseHeaders ? x.getAllResponseHeaders() : '',
                    finalUrl: opt.url };
        if (opt.onload) opt.onload(res);
        if (opt.onreadystatechange) opt.onreadystatechange(res);
      };
      x.onerror = function () { if (opt.onerror) opt.onerror({ error: 'network' }); };
      x.ontimeout = function () { if (opt.ontimeout) opt.ontimeout({ error: 'timeout' }); };
      x.send(opt.data === undefined ? null : opt.data);
      return { abort: function () { try { x.abort(); } catch (e) {} } };
    } catch (e) {
      if (opt.onerror) opt.onerror({ error: String(e) });
      return { abort: function () {} };
    }
  };
  if (typeof window.Swal === 'undefined') {
    window.Swal = {
      fire: function () { return Promise.resolve({ isConfirmed: true, value: true }); },
      close: function () {}, showLoading: function () {}, closeLoading: function () {},
      mixin: function () { return window.Swal; }
    };
  }
})();
"""

_cache = {}


def build_bundle(extra=None):
    key = 'b'
    if key in _cache:
        return _cache[key]
    for p in (JQ, FONT, USER_JS):
        if not os.path.exists(p):
            raise SystemExit('缺少资源文件：%s\n（分发包不完整，请重新解压整个文件夹）' % p)
    jq = open(JQ, encoding='utf-8', errors='replace').read()
    table = open(FONT, encoding='utf-8', errors='replace').read()
    user = open(USER_JS, encoding='utf-8', errors='replace').read()
    st = settings()
    if extra:
        st.update(extra)
    settings_js = '\n'.join(
        "try { localStorage.setItem(%s, %s); } catch (e) {}"
        % (json.dumps('GPTJsSetting.' + k), json.dumps(v)) for k, v in st.items())
    bundle = '\n'.join([
        'try { window.__XA_INJECTED__ = false; } catch (e) {}',
        'window.__XA_FONT_TABLE__ = ' + table + ';',
        settings_js,
        jq,
        'window.jQuery = window.jQuery || window.$; window.$ = window.jQuery;',
        POLYFILL,
        user,
    ])
    _cache[key] = bundle
    return bundle


if __name__ == '__main__':
    print('注入包大小', len(build_bundle()))
