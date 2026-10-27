# -*- coding: utf-8 -*-
"""第 5 步：提取每个视频的上报参数，并自动测出这门课要求的上报间隔。

关键点：不同课程对「多久报一次进度」的要求不一样（这次实测：世界文明史 60 秒，
儒学也是 60 秒，但有的课更松）。报得太勤服务器会把增量丢掉，表现就是
「进度显示满了，但一直不通过」。所以这一步会顺带把官方要求的间隔读出来，
第 6 步会按它自动调整，不用你猜。

用法：python step5_jobs.py <课程号>

产出：data/jobs_<课程号>.json
"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg

DATA = os.path.join(cfg.HERE, 'data')


def load_session():
    p = os.path.join(DATA, 'cookies.json')
    if not os.path.exists(p):
        raise SystemExit('缺 data/cookies.json，先运行：python step4_cookies.py')
    s = requests.Session()
    s.headers.update({'User-Agent': cfg.UA, 'Referer': 'https://%s/' % cfg.HOST})
    for c in json.load(open(p, encoding='utf-8')):
        s.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
    return s


def parse_marg(html):
    i = html.find('mArg = {')
    if i < 0:
        return None
    i += len('mArg = ')
    depth, in_str, esc = 0, False, False
    for j in range(i, len(html)):
        ch = html[j]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[i:j + 1])
                except Exception:
                    return None
    return None


def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法：python step5_jobs.py <课程号>')
    c = cfg.get_course(sys.argv[1])
    p = os.path.join(DATA, 'tasks_%s.json' % c['course'])
    if not os.path.exists(p):
        raise SystemExit('缺 %s，先运行：python step2_scan.py %s' % (p, c['course']))
    d = json.load(open(p, encoding='utf-8'))
    klass, cpi = d['klass'], d['cpi']
    chapters = [x for x in d['chapters'] if x.get('kid')]
    print('%s  章节 %d 个' % (c['name'], len(chapters)), flush=True)

    s = load_session()
    jobs, intervals = [], []
    for n, ch in enumerate(chapters, 1):
        nums = [t['num'] for t in ch.get('tasks', [])] or [0]
        got = 0
        for num in nums:
            params = {'clazzid': klass, 'courseid': c['course'], 'knowledgeid': ch['kid'],
                      'num': str(num), 'ut': 's', 'cpi': cpi, 'v': '2024', 'embeded': '1'}
            try:
                r = s.get('https://%s/mooc-ans/knowledge/cards' % cfg.HOST,
                          params=params, timeout=20)
            except Exception as e:
                print('  [%d] %s num=%s 失败 %s' % (n, ch['title'][:14], num, str(e)[:60]), flush=True)
                continue
            if r.status_code != 200 or '验证码' in r.text[:3000]:
                print('  !! HTTP %s（可能触发验证码，先停一停）' % r.status_code, flush=True)
                break
            m = parse_marg(r.text)
            iv = ((m or {}).get('defaults') or {}).get('reportTimeInterval')
            if iv:
                try:
                    intervals.append(int(iv))
                except Exception:
                    pass
            for a in (m or {}).get('attachments', []):
                if a.get('type') not in ('video', 'audio'):
                    continue
                prop = a.get('property') or {}
                oi = a.get('otherInfo') or ''
                if '&' in oi:
                    oi = oi.split('&')[0]
                jobs.append({
                    'chapter_kid': ch['kid'], 'chapter_title': ch['title'], 'num': num,
                    'name': prop.get('name') or a.get('name') or '?',
                    'objectid': prop.get('objectid') or a.get('objectid') or a.get('objectId'),
                    'jobid': a.get('jobid') or prop.get('jobid'),
                    'otherinfo': oi,
                    'attDuration': int(a.get('attDuration') or 0),
                    'playTime': int(a.get('playTime') or 0),
                    'isPassed': bool(a.get('isPassed')),
                    'attDurationEnc': a.get('attDurationEnc') or '',
                    'videoFaceCaptureEnc': a.get('videoFaceCaptureEnc') or '',
                })
                got += 1
            time.sleep(1.1)
        print('  [%2d/%d] %-22s 视频 %d' % (n, len(chapters), ch['title'][:20], got), flush=True)

    interval = max(intervals) if intervals else int(cfg.CONFIG['video']['gap'])
    out = {'course': c['course'], 'name': c['name'], 'klass': klass, 'cpi': cpi,
           'interval': interval, 'jobs': jobs}
    dest = os.path.join(DATA, 'jobs_%s.json' % c['course'])
    json.dump(out, open(dest, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    ok = sum(1 for x in jobs if x['isPassed'])
    left = sum(x['attDuration'] for x in jobs if not x['isPassed'])
    print()
    print('视频 %d 个 | 已完成 %d | 待跑 %d' % (len(jobs), ok, len(jobs) - ok))
    print('剩余内容 %.0f 分钟' % (left / 60.0))
    print('服务器要求的上报间隔：%d 秒（第 6 步会自动用它）' % interval)
    print('->', dest)
    print()
    print('下一步：python step6_video.py %s' % c['course'])


if __name__ == '__main__':
    main()
