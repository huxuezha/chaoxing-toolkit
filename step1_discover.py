# -*- coding: utf-8 -*-
"""第 1 步：自动登记课程 ID。

原理：学习通每门课的地址里都带着「课程号 clazzid / 课程 courseid / cpi」，
你在浏览器里打开那门课的任意一页，脚本直接从地址栏读出来，不用你手抄。

用法：
  python step1_discover.py                  # 读当前标签页（推荐）
  python step1_discover.py --url "粘贴地址"  # 手动粘地址也行
  python step1_discover.py --list           # 看已经登记了哪些课
"""
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg, cdp

KEYS = ('courseid', 'clazzid', 'cpi', 'stuenc')


def parse(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    out = {}
    for k in KEYS:
        if q.get(k):
            out[k] = q[k][0]
    return out


def from_page():
    t = cdp.find_tab()
    ws, cmd = cdp.connect(t['webSocketDebuggerUrl'])
    try:
        return (cdp.evaluate(cmd, 'location.href') or '',
                cdp.evaluate(cmd, 'document.title') or '')
    finally:
        ws.close()


def hunt(c):
    """地址里缺参数时，跳一次课程页，从新地址和页面源码里补 cpi / stuenc。"""
    t = cdp.find_tab()
    ws, cmd = cdp.connect(t['webSocketDebuggerUrl'])
    try:
        cmd('Page.enable')
        u = ('https://%s/mooc2-ans/mycourse/studentcourse?courseid=%s&clazzid=%s'
             '&ut=s&t=%d' % (cfg.HOST2, c['course'], c['klass'], int(time.time() * 1000)))
        cdp.nav(cmd, u, 8)
        got = parse(cdp.evaluate(cmd, 'location.href') or '')
        html = cdp.evaluate(cmd, 'document.documentElement.innerHTML.slice(0,600000)') or ''

        if not got.get('cpi'):
            m = re.search(r'-cpi_(\d+)', html) or re.search(r'cpi=(\d{6,})', html) \
                or re.search(r'cpi%3D(\d{6,})', html)
            if m:
                got['cpi'] = m.group(1)
        if not got.get('stuenc'):
            m = re.search(r'stuenc=([A-Za-z0-9]{16,})', html)
            if m:
                got['stuenc'] = m.group(1)
        return got
    finally:
        ws.close()


def show():
    d = cfg.courses()
    if not d:
        print('还没登记任何课程。')
        return
    print('已登记的课程：')
    for k, c in d.items():
        print('  %-12s %-26s clazz=%-11s cpi=%s'
              % (k, c.get('name', '?'), c.get('klass'), c.get('cpi')))


def main():
    if '--list' in sys.argv:
        show()
        return

    if '--url' in sys.argv:
        url, title = sys.argv[sys.argv.index('--url') + 1], ''
    else:
        url, title = from_page()

    got = parse(url)
    if not (got.get('courseid') and got.get('clazzid')):
        print('当前页面地址里没找到课程号：')
        print(' ', url[:160])
        print()
        print('请在这个专用窗口里打开你要处理的那门课（点进任意一章），再运行一次。')
        raise SystemExit(1)

    c = {'course': got['courseid'], 'klass': got['clazzid'],
         'cpi': got.get('cpi', ''), 'stuenc': got.get('stuenc', '')}

    if not (c['cpi'] and c['stuenc']):
        print('地址里缺参数，正在自动补（会跳一次课程页）...')
        extra = hunt(c)
        c['cpi'] = c['cpi'] or extra.get('cpi', '')
        c['stuenc'] = c['stuenc'] or extra.get('stuenc', '')

    if not c['cpi']:
        print()
        print('补不到 cpi。请把浏览器打开到该课程的「章节」页面，'
              '让地址栏里出现 cpi= 数字，再运行一次。')
        raise SystemExit(1)

    name = ''
    if '--name' in sys.argv:
        name = sys.argv[sys.argv.index('--name') + 1]
    elif title:
        name = title
        for junk in ('章节测验', '课程门户', '学习通', '章节', '章节列表'):
            name = name.replace(junk, '')
        name = name.strip(' -_|')
    if not name:
        name = '课程' + c['course']

    d = cfg.courses()
    d[c['course']] = {'name': name, 'klass': c['klass'],
                      'cpi': c['cpi'], 'stuenc': c['stuenc']}
    cfg.save_courses(d)

    print()
    print('已登记：')
    print('  课程名  %s' % name)
    print('  courseid=%s  clazzid=%s  cpi=%s' % (c['course'], c['klass'], c['cpi']))
    print('  stuenc=%s' % (c['stuenc'] or '（空，一般不影响）'))
    print()
    print('下一步：python step2_scan.py %s' % c['course'])
    print()
    show()


if __name__ == '__main__':
    main()
