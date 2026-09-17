# -*- coding: utf-8 -*-
"""数学学习门户 · 「返回门户」浮动按钮遮挡验证（独立判据，不复用补丁里的规则）

用法：
  1. 先在门户目录起本地服务： python -m http.server 8765
  2. 运行本脚本：               python _verify_overlay.py

做的事：在**真实动画条件**下（不注入禁动画 CSS），遍历 5 个页面的全部 41 个子节
+ 5 个首页 × 3 档视口，逐一对「← 返回门户」做四项断言：

  T1  与「有文字的叶子元素」或「可交互控件」重叠（排除 svg/canvas 子树与门户自身）
  T2  与「可交互控件」重叠  ← 用户实际抱怨的问题类别
  OWN 遮住页面内置的「返回…」控件
  VW  按钮超出视口

四项计数都必须是 0。

为什么单独存在：`_shot.py` 里的探针只抽验「每页第一个子节 + 首页」。但同一页不同
子节的左上角布局差异极大（graph 的 s2 内置返回键底部是 70px，s5 只有 37px），
只抽验会漏。本脚本做全遍历。

注意：本脚本的判据**故意比补丁实现更严格**（补丁为避免被整列正文挤下去，
对超长文字块有豁免；本脚本对"所有文字元素"一视同仁）—— 验证探针若复用被测
代码的判定规则就是自证，会漏掉真问题。
"""
import os, re, subprocess, urllib.request, json

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
BASE = 'http://127.0.0.1:8765'
PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(PORTAL_DIR, '_tmp_overlay_probe')   # 已在 .gitignore 中忽略
os.makedirs(OUT, exist_ok=True)

SEQ = {
    'graph': ['goToSection(%d)' % n for n in [1, 2, 3, 4, 5, 6]],
    'probability': ['goTo(%d)' % n for n in [1, 2, 4, 5]],
    'statistics': ["goTo('t%d')" % n for n in [1, 2, 3, 4, 5, 6]],
    'functions': ['goTo(%d)' % n for n in [1, 2, 3, 4, 5]],
    'calculus1': ['goC1(%d)' % n for n in [1, 2, 3, 4, 5]]
                 + ['goC2(%d)' % n for n in [1, 2, 3, 4, 5]]
                 + ['goC3(%d)' % n for n in [1, 2, 3, 4]],
}

PROBE = """<script>
window.addEventListener('load', function(){
  var seq = %(seq)s;
  var out = [];
  var idx = 0;
  var back = null, topBtn = null;

  function mine(el){
    return el === back || el === topBtn ||
           (el.closest && el.closest('.portal-back,.portal-top'));
  }
  function inGraphics(el){
    return el.closest && el.closest('svg,canvas');
  }
  var CTRL = {A:1,BUTTON:1,INPUT:1,SELECT:1,TEXTAREA:1,LABEL:1,OPTION:1};

  function check(){
    back = document.querySelector('.portal-back');
    topBtn = document.getElementById('portal-top-btn');
    var pr = back.getBoundingClientRect();
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var t1 = [], t2 = [], ownHit = false;
    var els = document.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], tag = el.tagName;
      if (tag === 'HTML' || tag === 'BODY' || tag === 'SCRIPT' || tag === 'STYLE'
          || tag === 'META' || tag === 'TITLE' || tag === 'LINK' || tag === 'HEAD') continue;
      if (mine(el)) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      if (r.right <= pr.left || pr.right <= r.left) continue;
      if (r.bottom <= pr.top || pr.bottom <= r.top) continue;
      var tc = (el.textContent || '').trim();
      var label = tag + ':' + (tc || String(el.className) || '').replace(/\\s+/g, '').slice(0, 16);
      var ctrl = CTRL[tag] || el.hasAttribute('onclick');
      if (ctrl && tc.indexOf('返回') === 0) ownHit = true;
      if (ctrl) t2.push(label);
      if (!inGraphics(el)) {
        if (ctrl || (el.children.length === 0 && tc.length > 0)) t1.push(label);
      }
    }
    var okViewport = (pr.top >= 0 && pr.bottom <= vh && pr.left >= 0 && pr.right <= vw);
    return {
      top: Math.round(pr.top), left: Math.round(pr.left),
      size: Math.round(pr.width) + 'x' + Math.round(pr.height),
      t1: t1, t2: t2, own: ownHit, okViewport: okViewport, vw: vw, vh: vh
    };
  }

  function step(){
    if (idx >= seq.length) {
      document.documentElement.setAttribute('data-verify', JSON.stringify(out));
      return;
    }
    var label = (idx === 0 ? '<HOME>' : seq[idx - 1]);
    if (idx > 0) { try { eval(seq[idx - 1]); } catch (e) { label += ' NAVERR'; } }
    // 等 1000ms（> 700ms 二次校正 + 400ms fadeIn 动画）后再断言
    setTimeout(function(){
      var r = check();
      out.push([label, r.top, r.left, r.size, r.t1, r.t2, r.own, r.okViewport, r.vw, r.vh]);
      idx++;
      step();
    }, 1000);
  }
  step();
});
</script>"""


def run(page, w, h, tag):
    html = urllib.request.urlopen('%s/%s.html' % (BASE, page), timeout=30).read().decode('utf-8')
    inj = PROBE % {'seq': str(SEQ[page])}
    html = html.replace('</head>', inj + '</head>', 1)
    name = '_tmp_vfy_%s_%s.html' % (page, tag)
    tmp = os.path.join(PORTAL_DIR, name)
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(html)
    prof = os.path.join(OUT, 'vf_%s_%s' % (page, tag))
    r = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                        '--user-data-dir=' + prof, '--virtual-time-budget=200000',
                        '--window-size=%d,%d' % (w, h), '--dump-dom',
                        BASE + '/' + name], capture_output=True)
    dom = r.stdout.decode('utf-8', 'ignore')
    try:
        os.remove(tmp)
    except OSError:
        pass
    m = re.search(r'data-verify="([^"]*)"', dom)
    if not m:
        return None
    import html as _h
    return json.loads(_h.unescape(m.group(1)))


fails_t1, fails_t2, fails_own, fails_vp = [], [], [], []
tops = {}
for vw, vh, tag in [(1280, 900, 'd'), (900, 900, 'm'), (500, 780, 'n')]:
    print('\n' + '=' * 78)
    print('### 视口 %dx%d  —— 真实条件（动画照常）逐子节验证' % (vw, vh))
    print('=' * 78)
    for page in SEQ:
        data = run(page, vw, vh, tag)
        print('\n--- %s.html ---' % page)
        if not data:
            print('    !! 未取得数据')
            continue
        for label, top, left, size, t1, t2, own, okvp, rvw, rvh in data:
            mark = 'OK  '
            if t1: mark = 'T1  '
            if t2: mark = 'T2!!'
            if own: mark = 'OWN!'
            if not okvp: mark = 'VW!!'
            tops.setdefault((page, tag), []).append(top)
            print('  %-14s %s top=%-4d left=%-3d %-8s 视口%dx%d'
                  % (label, mark, top, left, size, rvw, rvh))
            if t1: print('        T1命中(文字/控件): %s' % ' ; '.join(t1[:4]))
            if t2: print('        T2命中(可交互控件): %s' % ' ; '.join(t2[:4]))
            if own: print('        !! 遮住页面自带返回控件')
            if not okvp: print('        !! 超出视口')
            if t1: fails_t1.append((tag, page, label, t1[:3]))
            if t2: fails_t2.append((tag, page, label, t2[:3]))
            if own: fails_own.append((tag, page, label))
            if not okvp: fails_vp.append((tag, page, label))

print('\n' + '=' * 78)
print('### 落位 top 值分布（每页每档的最小~最大）')
print('=' * 78)
for (page, tag), arr in sorted(tops.items()):
    print('  %-12s [%s]  %s  (min=%d max=%d 跨度=%d)'
          % (page, tag, sorted(set(arr)), min(arr), max(arr), max(arr) - min(arr)))

print('\n' + '=' * 78)
print('### 结论')
print('=' * 78)
print('  T1（文字/控件重叠）: %d 处' % len(fails_t1))
for f in fails_t1: print('     [%s] %s %s -> %s' % f)
print('  T2（可交互控件重叠）: %d 处' % len(fails_t2))
for f in fails_t2: print('     [%s] %s %s -> %s' % f)
print('  遮住内置返回控件: %d 处' % len(fails_own))
for f in fails_own: print('     [%s] %s %s' % f)
print('  超出视口: %d 处' % len(fails_vp))
for f in fails_vp: print('     [%s] %s %s' % f)
