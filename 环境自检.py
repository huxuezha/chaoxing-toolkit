# -*- coding: utf-8 -*-
"""一键自检：跑之前先运行这个，把环境问题一次挑出来。

用法：python 环境自检.py
"""
import json
import os
import socket
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

OK = '  [OK]   '
BAD = '  [!!]   '


def line(tag, msg):
    print(tag + msg)


def main():
    print('=== 学习通助手 环境自检 ===')
    print()
    print('1) 依赖库')
    miss = []
    for name, mod in (('requests', 'requests'), ('websocket-client', 'websocket')):
        try:
            __import__(mod)
            line(OK, name)
        except Exception:
            line(BAD, name + ' 没装  ->  pip install ' + name)
            miss.append(name)

    print()
    print('2) 资源文件')
    for f in ('jquery.min.js', 'font_table.json', 'xiaoai.user.js'):
        p = os.path.join(HERE, 'assets', f)
        if os.path.exists(p):
            line(OK, '%s  %.0f KB' % (f, os.path.getsize(p) / 1024.0))
        else:
            line(BAD, f + ' 缺失，分发包不完整')

    print()
    print('3) 配置文件')
    try:
        from lib import cfg
        line(OK, '学校域名 %s' % cfg.SCHOOL)
        line(OK, '接口地址 %s' % cfg.HOST)
        k = cfg.CONFIG['api']['key']
        if k and '填' not in k:
            line(OK, 'API 密钥已填（%s...）' % k[:8])
        else:
            line(BAD, 'API 密钥还没填 -> 打开 config.json 填 api.key')
        dv = cfg.CONFIG['video']
        line(OK, '视频默认参数 %sx / 间隔 %ss / %s 路'
             % (dv['speed'], dv['gap'], dv['workers']))
        cs = cfg.courses()
        if cs:
            line(OK, '已登记 %d 门课' % len(cs))
        else:
            line(BAD, '还没登记课程 -> 登录后跑 step1_discover.py')
    except SystemExit as e:
        line(BAD, str(e))
        return
    except Exception as e:
        line(BAD, 'config.json 有问题：%s' % e)
        return

    print()
    print('4) 浏览器调试端口')
    port = cfg.PORT
    s = socket.socket()
    s.settimeout(0.5)
    alive = s.connect_ex(('127.0.0.1', port)) == 0
    s.close()
    if alive:
        line(OK, '端口 %d 已连通（专用浏览器开着）' % port)
    else:
        line(BAD, '端口 %d 连不上 -> 先运行 python step0_open.py' % port)

    print()
    print('5) 登录状态')
    p = os.path.join(HERE, 'data', 'cookies.json')
    if os.path.exists(p):
        names = {c['name'] for c in json.load(open(p, encoding='utf-8'))}
        if '_uid' in names and 'fid' in names:
            line(OK, 'cookies.json 有效（%d 条）' % len(names))
        else:
            line(BAD, 'cookies.json 不完整 -> 重跑 step4_cookies.py')
    else:
        line(BAD, '还没导出登录状态 -> 登录后跑 step4_cookies.py')

    print()
    if miss:
        print('先装依赖：pip install ' + ' '.join(miss))
    else:
        print('自检结束。按 README.md 的步骤走即可。')


if __name__ == '__main__':
    main()
