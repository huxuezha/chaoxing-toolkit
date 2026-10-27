# -*- coding: utf-8 -*-
"""第 6 步：刷视频进度。

做什么：不下载视频、不真正播放，而是像播放器一样，按固定节奏向服务器
报告「我播到第几秒了」。每次报告都要带一个签名，签名算错服务器直接不认。

三个必须知道的规律（这套代码已经内置）：
  1. 服务器按「真实时间 × 2」发额度。报得太快（比如 60 秒真实时间报 300 秒）
     会被拒收，所以速度上限就是 2 倍。
  2. 上报间隔必须 ≥ 服务器要求的值（第 5 步已经自动读出来了），
     报得太勤会被当成噪音丢掉——进度条满了也不给通过。
  3. 连续高速跑太久会被临时降额，表现是「突然全都不通过了」。
     本脚本会自动降速重试，不用你手动干预。

用法：
  python step6_video.py 268330787                 # 按 config.json 的参数跑
  python step6_video.py 268330787 --speed 1.5 --workers 2 --gap 60
  python step6_video.py 268330787 --state          # 只看状态，不刷
"""
import hashlib
import json
import os
import re
import sys
import threading
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg

DATA = os.path.join(cfg.HERE, 'data')
SALT = 'd_yHJ!$pdA~5'
LOCK = threading.Lock()


def log(msg):
    line = time.strftime('[%H:%M:%S] ') + msg
    with LOCK:
        print(line, flush=True)


def make_session():
    s = requests.Session()
    s.headers.update({'User-Agent': cfg.UA, 'Referer': 'https://%s/' % cfg.HOST})
    p = os.path.join(DATA, 'cookies.json')
    if not os.path.exists(p):
        raise SystemExit('缺 data/cookies.json，先运行：python step4_cookies.py')
    for c in json.load(open(p, encoding='utf-8')):
        s.cookies.set(c['name'], c['value'], domain=c['domain'], path=c['path'])
    return s


def md5enc(clazz, uid, jobid, oid, pt, dur):
    raw = '[%s][%s][%s][%s][%s][%s][%s][0_%s]' % (
        clazz, uid, jobid, oid, pt * 1000, SALT, dur * 1000, dur)
    return hashlib.md5(raw.encode()).hexdigest()


class Runner:
    def __init__(self, meta, speed=1.5, gap=60):
        self.klass = meta['klass']
        self.course = meta['course']
        self.cpi = meta['cpi']
        self.speed = speed
        self.gap = gap
        self.s = make_session()
        self.uid = next((c.value for c in self.s.cookies if c.name == '_uid'), None)
        self.fid = next((c.value for c in self.s.cookies if c.name == 'fid'), None)
        if not self.uid or not self.fid:
            raise SystemExit('登录凭证不全（缺 _uid / fid），重新登录后跑一遍 step4_cookies.py')
        self.blocked = False

    def status(self, oid):
        try:
            r = self.s.get('https://%s/ananas/status/%s?k=%s&flag=normal'
                           % (cfg.HOST, oid, self.fid), timeout=20)
            j = r.json()
            return j if j.get('status') == 'success' else None
        except Exception:
            return None

    def report(self, job, dtoken, pt, isdrag=3, rt='0.9'):
        dur = job['attDuration']
        params = {
            'clazzId': self.klass, 'playingTime': pt, 'duration': dur,
            'clipTime': '0_%d' % dur, 'objectId': job['objectid'],
            'otherInfo': job['otherinfo'], 'courseId': self.course,
            'jobid': job['jobid'], 'userid': self.uid, 'isdrag': isdrag,
            'view': 'pc', 'enc': md5enc(self.klass, self.uid, job['jobid'],
                                        job['objectid'], pt, dur),
            'dtype': 'Video', 'rt': rt, '_t': str(int(time.time() * 1000)),
        }
        if job.get('attDurationEnc'):
            params['attDurationEnc'] = job['attDurationEnc']
        if job.get('videoFaceCaptureEnc'):
            params['videoFaceCaptureEnc'] = job['videoFaceCaptureEnc']
        url = 'https://%s/mooc-ans/multimedia/log/a/%s/%s' % (cfg.HOST, self.cpi, dtoken)
        for attempt in range(3):
            try:
                r = self.s.get(url, params=params, timeout=30,
                               headers={'Referer': 'https://%s/ananas/modules/video/index.html' % cfg.HOST})
                if r.status_code == 202 or '验证码' in (r.text or '')[:3000]:
                    self.blocked = True
                    log('!! 触发验证码拦截（9010），需要人工在浏览器里输一次')
                return r
            except Exception as e:
                if attempt < 2:
                    time.sleep(5)
                    continue
                return type('R', (), {'status_code': 0,
                                      'text': '%s: %s' % (type(e).__name__, str(e)[:80])})()

    def read_state(self, job):
        p = {'clazzid': self.klass, 'courseid': self.course, 'knowledgeid': job['chapter_kid'],
             'num': str(job.get('num', 0)), 'ut': 's', 'cpi': self.cpi, 'v': '2024', 'embeded': '1'}
        try:
            t = self.s.get('https://%s/mooc-ans/knowledge/cards' % cfg.HOST,
                           params=p, timeout=20).text
        except Exception:
            return None
        m = None
        i = t.find('mArg = {')
        if i >= 0:
            i += len('mArg = ')
            depth, in_str, esc = 0, False, False
            for k in range(i, len(t)):
                ch = t[k]
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
                            m = json.loads(t[i:k + 1])
                        except Exception:
                            pass
                        break
        for a in (m or {}).get('attachments', []):
            if a.get('type') == 'video' and \
                    (a.get('objectId') or a.get('objectid')) == job['objectid']:
                return {'head': (a.get('headOffset') or 0) // 1000,
                        'play': (a.get('playTime') or 0) // 1000,
                        'passed': bool(a.get('isPassed')),
                        'dur': int(a.get('attDuration') or job['attDuration'])}
        return None

    def run_one(self, job):
        name = '%s %s' % (job['chapter_title'][:14], job['name'][:14])
        vi = self.status(job['objectid'])
        if not vi:
            log('%s X 取不到视频信息' % name)
            return False
        dtoken = vi['dtoken']
        dur = int(vi.get('duration') or job['attDuration'])
        job['attDuration'] = dur

        st = self.read_state(job)
        if st and st['passed']:
            log('%s 已完成，跳过' % name)
            return True

        pt = 0
        if st and st['head'] > 3:
            log('%s 未通过，回卷到 0 重新累计（原位置 %ds）' % (name, st['head']))
            self.report(job, dtoken, 0, isdrag=3)

        step = int(self.gap * self.speed)
        last = time.time()
        fails = 0
        while pt < dur:
            time.sleep(self.gap)
            pt = min(dur, pt + step)
            r = self.report(job, dtoken, pt, isdrag=3)

            if self.blocked:
                log('%s !! 等 5 分钟后重试' % name)
                time.sleep(300)
                self.blocked = False
                pt -= step
                continue

            if r.status_code != 200:
                fails += 1
                log('%s 上报 %ds -> HTTP %s %s' % (name, pt, r.status_code, str(r.text)[:80]))
                if fails >= 2:
                    vi2 = self.status(job['objectid'])
                    if vi2:
                        dtoken = vi2['dtoken']
                if fails >= 8:
                    log('%s 连续失败 8 次，放弃本章' % name)
                    return False
                pt -= step
                continue
            fails = 0
            passed = False
            try:
                passed = bool(r.json().get('isPassed'))
            except Exception:
                pass
            _ = last
            last = time.time()
            log('%s %ds/%ds %s' % (name, pt, dur, '通过' if passed else 'ok'))
            if passed:
                log('%s 完成' % name)
                return True

        for _ in range(2):
            r = self.report(job, dtoken, dur, isdrag=4)
            try:
                if r.json().get('isPassed'):
                    log('%s 完成（收尾）' % name)
                    return True
            except Exception:
                pass
            time.sleep(4)
        st2 = self.read_state(job)
        if st2 and st2['passed']:
            log('%s 完成（复核确认）' % name)
            return True
        log('%s 未通过，稍后换更慢的参数重试' % name)
        return False


def pending(meta):
    return [j for j in meta['jobs'] if not j['isPassed']]


def refresh(meta, jobs):
    """按服务端真实状态回写，避免本地记录过期。"""
    r = Runner(meta)
    changed = 0
    for j in jobs:
        st = r.read_state(j)
        if st and st['passed'] and not j['isPassed']:
            j['isPassed'] = True
            changed += 1
    if changed:
        json.dump(meta, open(os.path.join(DATA, 'jobs_%s.json' % meta['course']), 'w',
                             encoding='utf-8'), ensure_ascii=False, indent=1)
    return changed


def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法：python step6_video.py <课程号>')
    c = cfg.get_course(sys.argv[1])
    p = os.path.join(DATA, 'jobs_%s.json' % c['course'])
    if not os.path.exists(p):
        raise SystemExit('缺 %s，先运行：python step5_jobs.py %s' % (p, c['course']))
    meta = json.load(open(p, encoding='utf-8'))
    jobs = meta['jobs']
    gap = meta.get('interval') or int(cfg.CONFIG['video']['gap'])

    if '--state' in sys.argv:
        ok = 0
        for n, j in enumerate(jobs, 1):
            st = Runner(meta).read_state(j)
            mark = '通过' if (st and st['passed']) else '    '
            if st and st['passed']:
                ok += 1
            print('[%2d] %s %-26s %5ds 位置%5ds'
                  % (n, mark, j['chapter_title'][:24], j['attDuration'],
                     st['head'] if st else -1))
            time.sleep(0.8)
        print('\n已完成 %d / %d' % (ok, len(jobs)))
        return

    speed = float(sys.argv[sys.argv.index('--speed') + 1]) if '--speed' in sys.argv \
        else float(cfg.CONFIG['video']['speed'])
    workers = int(sys.argv[sys.argv.index('--workers') + 1]) if '--workers' in sys.argv \
        else int(cfg.CONFIG['video']['workers'])
    if '--gap' in sys.argv:
        gap = int(sys.argv[sys.argv.index('--gap') + 1])
    gap = max(gap, 30)

    targets = pending(meta)
    print('待跑 %d / %d 个视频，间隔 %ds' % (len(targets), len(jobs), gap))
    if not targets:
        print('全部已完成。')
        return

    for rnd in range(1, 4):
        if not targets:
            break
        log('=== 第 %d 轮 | %d 个 | %.2fx | 间隔 %ds | %d 路 ==='
            % (rnd, len(targets), speed, gap, workers))
        ok = [0]
        lock = threading.Lock()

        def work(chunk):
            r = Runner(meta, speed, gap)
            for job in chunk:
                if r.run_one(job):
                    with lock:
                        ok[0] += 1
                    job['isPassed'] = True
                    json.dump(meta, open(p, 'w', encoding='utf-8'),
                              ensure_ascii=False, indent=1)

        chunks = [targets[i::workers] for i in range(workers)]
        ths = [threading.Thread(target=work, args=(c2,), daemon=True)
               for c2 in chunks if c2]
        for t in ths:
            t.start()
            time.sleep(3)
        for t in ths:
            t.join()
        log('第 %d 轮结束：成功 %d / %d' % (rnd, ok[0], len(targets)))

        log('核对服务端真实状态...')
        refresh(meta, jobs)
        targets = pending(meta)
        if not targets:
            break
        if ok[0] == 0:
            speed = max(1.0, round(speed * 0.7, 2))
            workers = max(1, workers - 1)
            log('本轮一个都没过，多半是被限速了。降到 %.2fx、%d 路重试' % (speed, workers))

    left = pending(meta)
    print()
    print('=== 全部结束 ===')
    print('已完成 %d / %d' % (len(jobs) - len(left), len(jobs)))
    if left:
        print('还有 %d 个没过，建议过几小时再跑一次（服务器限制会自己恢复）：' % len(left))
        for j in left:
            print('  -', j['chapter_title'][:40])


if __name__ == '__main__':
    main()
