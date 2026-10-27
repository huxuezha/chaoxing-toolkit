# -*- coding: utf-8 -*-
"""第 0 步：打开一个专用的 Chrome 窗口，用来登录（不影响你平时用的浏览器）。

为什么要专用窗口：它把登录状态存在单独的目录里，脚本才有稳定的入口去读；
跟你日常浏览器的账号、缓存、插件都不打架。

运行：python step0_open.py
然后在这个新窗口里登录学习通（学校统一认证），登录完关掉命令行也不用管。
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg


def find_browser():
    la = os.path.expandvars(r'%LOCALAPPDATA%')
    pf = os.path.expandvars(r'%PROGRAMFILES%')
    pf86 = os.path.expandvars(r'%PROGRAMFILES(X86)%')
    cands = [
        os.path.join(la, r'Google\Chrome\Application\chrome.exe'),
        os.path.join(pf, r'Google\Chrome\Application\chrome.exe'),
        os.path.join(pf86, r'Google\Chrome\Application\chrome.exe'),
        os.path.join(pf86, r'Microsoft\Edge\Application\msedge.exe'),
        os.path.join(pf, r'Microsoft\Edge\Application\msedge.exe'),
    ]
    for p in cands:
        if os.path.exists(p):
            return p
    return None


def main():
    exe = find_browser()
    if not exe:
        raise SystemExit('没找到 Chrome 或 Edge，请先装一个 Chrome 再试。')

    profile = os.path.join(os.path.expandvars(r'%LOCALAPPDATA%'), 'Chaoxing_' + cfg.CONFIG['chrome']['profile'])
    args = [
        exe,
        '--user-data-dir=' + profile,
        '--remote-debugging-port=%d' % cfg.PORT,
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=DnsOverHttps',
        '--autoplay-policy=no-user-gesture-required',
        'https://%s/' % cfg.SPACE,
    ]
    print('启动：', exe)
    print('登录状态目录：', profile)
    print('调试端口：', cfg.PORT)
    subprocess.Popen(args, close_fds=True)
    print()
    print('>>> 请在弹出的窗口里登录学习通（学校统一认证）。')
    print('>>> 登录成功后，继续运行：python step1_discover.py')


if __name__ == '__main__':
    main()
