# -*- coding: utf-8 -*-
"""第 3 步：自动完成课后习题（章节测验）。

做法：进入每章的任务点 → 把答题脚本注入页面 → 让它调 AI 逐题作答 → 自动提交。
已经做完的章节会自动跳过，可以反复运行。

用法：
  python step3_quiz.py 268330787              # 全部未完成的
  python step3_quiz.py 268330787 --dry        # 只看状态，不答题
  python step3_quiz.py 268330787 --limit 2    # 先试两章
  python step3_quiz.py 268330787 --kid 1268862967
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import cfg, cdp, xiaoai

DATA = os.path.join(cfg.HERE, 'data')

FIND_WORK = r"""
function findWork(w, d) {
  if (d > 5) return null;
  var fs = [];
  try { fs = w.document.querySelectorAll('iframe'); } catch (e) { return null; }
  for (var i = 0; i < fs.length; i++) {
    var iw = null;
    try { iw = fs[i].contentWindow; } catch (e) { continue; }
    if (!iw) continue;
    var href = '';
    try { href = iw.location.href; } catch (e) {}
    if (/doHomeWork|selectWorkQuestion|\/api\/work/.test(href)) return iw;
    var r = findWork(iw, d + 1);
    if (r) return r;
  }
  return null;
}
"""

QUIZ_JS = FIND_WORK + r"""
(function(){
  var T = window.__XIAOAI_TEST__;
  if (!T) {
    return JSON.stringify({err: 'no hook', xaErr: String(window.__XA_ERR__||'').slice(0,300)});
  }
  try { T.Router._toNext = function () {}; } catch (e) {}
  try { T.Router.route = function () {}; } catch (e) {}

  var w = findWork(window, 0);
  if (!w) return JSON.stringify({stage: 'no-work-frame'});
  var d = w.document;
  var $ = window.jQuery;
  var st = window.__QUIZ_STATE__;
  if (st && (st.submitted || st.skip)) return JSON.stringify(st);

  var bodyTxt = (d.body ? d.body.innerText : '').replace(/\s+/g, ' ');
  var done = /本次成绩|成绩[:：]\s*\d|已完成|查看正确答案|已提交/.test(bodyTxt);
  var hasQ = d.querySelectorAll('.Py-mian1').length > 0;
  var hasInput = d.querySelectorAll('ul.answerList, .blankList2 input, textarea, .edui-editor')
                  .length > 0;

  if (!hasQ) {
    if (done) { window.__QUIZ_STATE__ = {skip: true, stage: 'already-done',
      body: bodyTxt.slice(0, 160)}; return JSON.stringify(window.__QUIZ_STATE__); }
    var entry = null;
    var all = d.querySelectorAll('a,button,div,span,li,p');
    for (var i = 0; i < all.length; i++) {
      var t = (all[i].innerText || '').trim();
      if (/由此作答|开始作答|去做作业|去作答|重新作答/.test(t) && t.length < 20) { entry = all[i]; break; }
    }
    if (entry) { entry.click(); return JSON.stringify({stage: 'clicked-entry', label: entry.innerText.trim()}); }
    return JSON.stringify({stage: 'no-entry', body: bodyTxt.slice(0, 200)});
  }

  if (!hasInput) return JSON.stringify({stage: 'questions-but-no-input', body: bodyTxt.slice(0, 160)});

  if (st && st.started) return JSON.stringify(st);
  window.__QUIZ_STATE__ = {stage: 'answering', total: d.querySelectorAll('.Py-mian1').length,
                           started: true, submitted: false, done: false};

  var $timu = $('.Py-mian1', d);
  T.QuizEngine.processAll($timu, T.PhoneAdapter, {
    alterTitle: false,
    delayFn: function () { return 900; },
    onAllDone: function (answered, total) {
      var s = window.__QUIZ_STATE__;
      s.answered = answered; s.total = total; s.done = true;
      if (total > 0 && answered === 0) {
        s.stage = 'no-answer-abort';
        return;
      }
      var sub = d.querySelector('.btn-ok-bottom');
      if (sub) { sub.click(); }
      setTimeout(function () {
        var ok = d.getElementById('okBtn') || d.querySelector('#okBtn') ||
                 d.querySelector('#cxAlertBox1 #okBtn');
        if (ok) { try { ok.click(); } catch (e) {} }
        s.submitted = true; s.stage = 'submitted';
      }, 3000);
    }
  });
  return JSON.stringify(window.__QUIZ_STATE__);
})()
"""


def log(path, line):
    with open(path, 'a', encoding='utf-8') as f:
        f.write(time.strftime('%H:%M:%S ') + line + '\n')
    print(line, flush=True)


def inject(cmd, bundle):
    cdp.evaluate(cmd, 'try{window.__XA_INJECTED__=false;window.__XA_ERR__=null;'
                      'window.__QUIZ_STATE__=null;}catch(e){}')
    cdp.evaluate(cmd, 'try{' + bundle + '}catch(e){window.__XA_ERR__=String(e).slice(0,300)}')
    time.sleep(3)


def run_one(cmd, bundle, c, kid, num, dry=False, budget=240):
    cdp.nav(cmd, cfg.card_url(c, kid, num), 8)
    inject(cmd, bundle)
    t0 = time.time()
    seen = None
    r = {}
    while time.time() - t0 < budget:
        try:
            r = json.loads(cdp.evaluate(cmd, QUIZ_JS) or '{}')
        except Exception as e:
            r = {'err': str(e)[:150]}
        stage = (r.get('stage') or r.get('err') or '') + '|' + str(r.get('answered'))
        if stage != seen:
            print('    ', json.dumps(r, ensure_ascii=False)[:220], flush=True)
            seen = stage
        if r.get('submitted') or r.get('skip'):
            return r
        if r.get('err') == 'no hook':
            return r
        if dry and r.get('stage') in ('already-done', 'no-entry', 'no-work-frame'):
            return r
        time.sleep(3)
    return {'stage': 'timeout', 'last': r}


def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法：python step3_quiz.py <课程号>')
    c = cfg.get_course(sys.argv[1])
    p = os.path.join(DATA, 'works_%s.json' % c['course'])
    if not os.path.exists(p):
        raise SystemExit('缺 %s，先运行：python step2_scan.py %s' % (p, c['course']))
    works = json.load(open(p, encoding='utf-8'))

    if '--kid' in sys.argv:
        only = sys.argv[sys.argv.index('--kid') + 1]
        works = [w for w in works if w['kid'] == only]
    if '--limit' in sys.argv:
        works = works[:int(sys.argv[sys.argv.index('--limit') + 1])]
    dry = '--dry' in sys.argv

    logf = os.path.join(DATA, 'quiz_%s.log' % c['course'])
    log(logf, '=== %s 章节测验 %d 个 (dry=%s) ===' % (c['name'], len(works), dry))

    bundle = xiaoai.build_bundle()
    ok = skip = fail = 0
    for i, w in enumerate(works, 1):
        log(logf, '[%d/%d] %s num=%s' % (i, len(works), w['chapter'][:22], w['num']))
        r = {}
        for attempt in range(3):
            ws = None
            try:
                t = cdp.find_tab()
                ws, cmd = cdp.connect(t['webSocketDebuggerUrl'])
                cmd('Page.enable')
                r = run_one(cmd, bundle, c, w['kid'], w['num'], dry=dry)
                break
            except Exception as e:
                r = {'stage': 'ws-error', 'err': str(e)[:160]}
                log(logf, '    ! 第%d次连接异常: %s' % (attempt + 1, str(e)[:100]))
                time.sleep(3)
            finally:
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
        if r.get('submitted'):
            ok += 1
            log(logf, '    OK 已提交 答%s/%s' % (r.get('answered'), r.get('total')))
        elif r.get('skip'):
            skip += 1
            log(logf, '    -- 已完成，跳过')
        else:
            fail += 1
            log(logf, '    XX %s' % json.dumps(r, ensure_ascii=False)[:200])
    log(logf, '=== 完成 提交%d 跳过%d 失败%d ===' % (ok, skip, fail))


if __name__ == '__main__':
    main()
