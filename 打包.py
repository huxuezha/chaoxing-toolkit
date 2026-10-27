# -*- coding: utf-8 -*-
"""打包分发包：生成一个干净的 zip，可以直接发给同学。

为什么要专门写这个：跑过之后 data/ 目录里会有 cookies.json（你的登录凭证）和
你自己的课程数据。直接把文件夹压缩发出去，等于把登录态一起送人了。
这个脚本会把这些统统排除掉。

用法：python 打包.py
产出：学习通助手_分发包.zip（在当前目录的上一级）
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), '学习通助手_分发包.zip')

# 这些不打包：个人数据、缓存、测试残留
SKIP_DIRS = {'data', '__pycache__', '.git'}
SKIP_FILES = {'courses.json', 'cookies.json', '.gitignore'}
SKIP_EXT = {'.pyc', '.log', '.out', '.zip'}


def keep(rel):
    parts = rel.replace('\\', '/').split('/')
    if any(p in SKIP_DIRS for p in parts[:-1]):
        return False
    name = parts[-1]
    if name in SKIP_FILES:
        return False
    if os.path.splitext(name)[1].lower() in SKIP_EXT:
        return False
    return True


def main():
    # config.json 里的密钥也要清掉，避免把自己的密钥送出
    cfg_path = os.path.join(HERE, 'config.json')
    backup = None
    if os.path.exists(cfg_path):
        backup = open(cfg_path, encoding='utf-8').read()
        import json
        d = json.loads(backup)
        if d.get('api', {}).get('key'):
            d['api']['key'] = '在这里填你自己的密钥'
        open(cfg_path, 'w', encoding='utf-8').write(
            json.dumps(d, ensure_ascii=False, indent=2) + '\n')

    n = 0
    try:
        with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(HERE):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
                for f in files:
                    p = os.path.join(root, f)
                    rel = os.path.relpath(p, HERE)
                    if keep(rel):
                        z.write(p, os.path.join('学习通助手', rel))
                        n += 1
    finally:
        if backup is not None:
            open(cfg_path, 'w', encoding='utf-8').write(backup)

    size = os.path.getsize(OUT) / 1024.0 / 1024.0
    print('已打包 %d 个文件 -> %s' % (n, OUT))
    print('大小 %.2f MB' % size)
    print()
    print('已排除：data/（登录凭证和你的课程数据）、courses.json、日志')
    print('密钥已重置为空，同学需要自己填一个。')


if __name__ == '__main__':
    main()
