# -*- coding: utf-8 -*-
"""第 4 步：把浏览器的登录状态导出成 cookies.json。

后面刷视频走的是「直接跟服务器对话」，不经过浏览器页面，
所以要先把登录凭证复制一份出来交给程序用。

用法：python step4_cookies.py
说明：这一步不会改变任何东西，只是读取。登录过期时重跑一次即可。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg, cdp

OUT = os.path.join(cfg.HERE, 'data', 'cookies.json')


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    t = cdp.find_tab()
    ws, cmd = cdp.connect(t['webSocketDebuggerUrl'])
    try:
        cmd('Network.enable')
        res = cmd('Network.getAllCookies')
        all_c = res.get('cookies', [])
    finally:
        ws.close()

    keep = []
    for c in all_c:
        d = c.get('domain', '')
        if cfg.SCHOOL in d or 'chaoxing' in d or 'ananas' in d:
            keep.append({'name': c['name'], 'value': c['value'],
                         'domain': d, 'path': c.get('path', '/')})

    if not keep:
        raise SystemExit('一个 cookie 都没拿到，说明这个窗口还没登录。\n'
                         '请先在专用窗口里登录，再运行本步骤。')

    json.dump(keep, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    names = {c['name'] for c in keep}
    print('已导出 %d 个 cookie -> %s' % (len(keep), OUT))
    for need in ('_uid', 'fid'):
        print('  %-6s %s' % (need, '有' if need in names else '缺（可能没登录完整）'))
    print()
    print('下一步：python step5_jobs.py <课程号>')


if __name__ == '__main__':
    main()
