# -*- coding: utf-8 -*-
"""第 2 步：扫描这门课的所有章节，找出「课后习题」和「视频」任务点。

用法：
  python step2_scan.py 268330787

产出（data/ 目录下）：
  tasks_<课程号>.json   全部章节和任务点
  works_<课程号>.json   只含课后习题（章节测验），第 3 步用
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg, cdp

DATA = os.path.join(cfg.HERE, 'data')

FETCH = """
(async (u) => {
  const r = await fetch(u, {credentials: 'include'});
  const t = await r.text();
  return JSON.stringify({s: r.status, t: t});
})
"""


def extract_marg(html):
    i = html.find('mArg = {')
    if i < 0:
        return None
    s = html.find('{', i + 7)
    d, e, instr, esc = 0, -1, False, False
    for k in range(s, len(html)):
        c = html[k]
        if instr:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == '{':
            d += 1
        elif c == '}':
            d -= 1
            if d == 0:
                e = k + 1
                break
    if e < 0:
        return None
    try:
        return json.loads(html[s:e])
    except Exception:
        return None


def fetch_card(cmd, c, kid, num):
    r = json.loads(cdp.evaluate(cmd, FETCH + '(%s)' % json.dumps(cfg.card_url(c, kid, num)),
                                await_promise=True))
    html = r.get('t') or ''
    title = html.split('<title>')[1].split('</title>')[0].strip() if '<title>' in html else ''
    return r.get('s'), title, extract_marg(html)


def slim_atts(m):
    out = []
    for a in (m or {}).get('attachments') or []:
        p = a.get('property') or {}
        out.append({
            'type': a.get('type') or p.get('module') or '',
            'job': a.get('job') or '',
            'jobid': a.get('jobid') or '',
            'objectid': a.get('objectid') or a.get('objectId') or '',
            'name': (p.get('name') or p.get('title') or '')[:60],
            'isPassed': a.get('isPassed') is True,
            'attDuration': a.get('attDuration') or 0,
            'playTime': a.get('playTime') or 0,
            '_prop_module': p.get('module') or '',
        })
    return out


def chapters(cmd, c):
    cmd('Page.enable')
    cdp.nav(cmd, cfg.studentcourse_url(c), 9)
    raw = cdp.evaluate(cmd, r"""JSON.stringify([...document.querySelectorAll('.chapter_item[id^=cur]')].map(function(e){
        return {kid: e.id.replace('cur',''),
                title: (e.innerText||'').replace(/\s+/g,' ').trim().slice(0,60)};
    }))""")
    return json.loads(raw or '[]')


def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法：python step2_scan.py <课程号>   （不知道课程号就先跑 step1_discover.py）')
    c = cfg.get_course(sys.argv[1])
    os.makedirs(DATA, exist_ok=True)
    maxnum = 8
    delay = 1.1

    t = cdp.find_tab()
    ws, cmd = cdp.connect(t['webSocketDebuggerUrl'])
    try:
        items = chapters(cmd, c)
        print('%s  共 %d 个章节' % (c['name'], len(items)), flush=True)
        if not items:
            print('没读到章节。可能是登录过期了，或这门课的章节结构不同。')
            print('页面地址：', cdp.evaluate(cmd, 'location.href')[:160])
            return
        # 切到 mooc1 域，后面同源 fetch
        cdp.nav(cmd, cfg.card_url(c, items[0]['kid'], 0), 5)

        for it in items:
            it['tasks'] = []
            for n in range(maxnum):
                try:
                    s, title, m = fetch_card(cmd, c, it['kid'], n)
                except Exception as e:
                    print('  !! %s num=%d 出错 %s' % (it['title'][:18], n, str(e)[:80]), flush=True)
                    s, title, m = 0, '', None
                if s != 200 or title in ('', '提示页面'):
                    break
                it['tasks'].append({'num': n, 'title': title, 'atts': slim_atts(m)})
                time.sleep(delay)
            line = ' | '.join('%d:%s[%d]' % (x['num'], x['title'], len(x['atts']))
                              for x in it['tasks'])
            print('%-24s %s' % (it['title'][:22], line), flush=True)
    finally:
        ws.close()

    out = dict(name=c['name'], course=c['course'], klass=c['klass'], cpi=c['cpi'],
               chapters=items)
    json.dump(out, open(os.path.join(DATA, 'tasks_%s.json' % c['course']), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    works = []
    for it in items:
        for t2 in it['tasks']:
            for a in t2['atts']:
                if 'work' in str(a['type']).lower() or a['_prop_module'] == 'work':
                    w = dict(kid=it['kid'], chapter=it['title'], num=t2['num'],
                             card_title=t2['title'])
                    w.update(a)
                    works.append(w)
    json.dump(works, open(os.path.join(DATA, 'works_%s.json' % c['course']), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    videos = [a for it in items for t2 in it['tasks'] for a in t2['atts']
              if a['type'] in ('video', 'audio')]
    print()
    print('=== 汇总 ===')
    print('课后习题（章节测验）：%d 个' % len(works))
    print('视频任务点：%d 个' % len(videos))
    if works:
        print()
        print('下一步：python step3_quiz.py %s' % c['course'])
    if videos:
        print('视频：先把第 3 步跑完，再 python step4_jobs.py %s' % c['course'])


if __name__ == '__main__':
    main()
