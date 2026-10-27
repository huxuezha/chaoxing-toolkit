# -*- coding: utf-8 -*-
"""统一配置与常量。所有脚本只从这里取学校域名 / 端口 / 密钥 / 课程表。

同学要改的只有两样：
  1. config.json       —— 学校域名、API 密钥、刷视频参数
  2. courses.json      —— 由 step1_discover.py 自动生成，不用手写
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # cxkit/
CONFIG_PATH = os.path.join(HERE, 'config.json')
COURSES_PATH = os.path.join(HERE, 'courses.json')

_DEFAULTS = {
    'school': {'domain': 'ppsuc.edu.cn', 'name': '本校'},
    'chrome': {'port': 9223, 'profile': 'ChaoxingChrome2'},
    'api': {'key': '', 'base': 'https://api.educg.net/v1', 'model': 'deepseek-v4-flash'},
    'video': {'speed': 1.5, 'gap': 60, 'workers': 2},
}


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config():
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            data = json.load(open(CONFIG_PATH, encoding='utf-8'))
        except Exception as e:
            raise SystemExit('config.json 格式错误：%s' % e)
    return _merge(_DEFAULTS, data)


CONFIG = load_config()
SCHOOL = CONFIG['school']['domain'].strip()
HOST = 'mooc1.' + SCHOOL
HOST2 = 'mooc2-ans.' + SCHOOL
SPACE = 'imooc.' + SCHOOL
PORT = int(CONFIG['chrome']['port'])

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')


def courses():
    """返回 {courseid: {name, klass, cpi, stuenc}}"""
    if not os.path.exists(COURSES_PATH):
        return {}
    try:
        return json.load(open(COURSES_PATH, encoding='utf-8'))
    except Exception:
        return {}


def save_courses(d):
    json.dump(d, open(COURSES_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def get_course(key):
    d = courses()
    if not d:
        raise SystemExit('还没有课程信息。先运行：python step1_discover.py')
    key = str(key)
    hit_key = None
    if key in d:
        hit_key = key
    else:
        # 也允许用课程名的一部分匹配，方便同学不记 ID
        hits = [k for k, c in d.items() if key in c.get('name', '')]
        if len(hits) == 1:
            hit_key = hits[0]
    if not hit_key:
        raise SystemExit('找不到课程 %r。现有的有：\n  %s'
                         % (key, '\n  '.join('%s  %s' % (k, c.get('name', ''))
                                             for k, c in d.items())))
    c = dict(d[hit_key])
    c['course'] = hit_key          # 课程号统一挂在 course 字段上，下游脚本都读它
    return c


def card_url(c, kid, num):
    return ('https://%s/mooc-ans/knowledge/cards?clazzid=%s&courseid=%s'
            '&knowledgeid=%s&num=%s&ut=s&cpi=%s&mooc2=1'
            % (HOST, c['klass'], c['course'], kid, num, c['cpi']))


def studentcourse_url(c):
    import time
    return ('https://%s/mooc2-ans/mycourse/studentcourse?courseid=%s&clazzid=%s'
            '&cpi=%s&ut=s&t=%d&stuenc=%s'
            % (HOST2, c['course'], c['klass'], c['cpi'], int(time.time() * 1000),
               c.get('stuenc', '')))
