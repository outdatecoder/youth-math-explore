# -*- coding: utf-8 -*-
"""数学学习门户 · 视觉走查 + 导航按钮行为验收

用法：
  1. 先在门户目录起本地服务： python -m http.server 8765
  2. 运行本脚本：               python _shot.py
  3. 截图输出到 shots/ （已在 .gitignore 中忽略，不参与发布）

三个必要的技巧：

  ① 禁动画 CSS
     学科页有 fadeIn 动画，直接截图会抓到中间态（整页发白），看不出内容。

  ② 导航按钮为什么用「几何/状态探针」而不是滚动截图
     headless 的 --screenshot 对程序化滚动 + position:fixed 元素的绘制位置不可靠
     （实测会拍到空白区），所以显隐行为改为读 computedStyle + getBoundingClientRect，
     并用 scrollTo 打桩验证「点击回顶」。这比截图更权威。
     外观/位置则由「强制显示后的截图」负责，两者互补。

     注意两个 headless 陷阱：
       · --virtual-time-budget 会冻结 CSS transition，直接读 opacity 拿到的是起始值
         （1 而不是 0）。故探针页额外注入 transition:none 让状态瞬时生效。
         这只影响淡入动画本身，不影响「滚动位置 -> class 切换」这条被验证的逻辑。
       · window.innerWidth 含滚动条宽度，右对齐断言必须用
         document.documentElement.clientWidth，否则会误报 16px 的偏差。

  ③ Cytoscape 本地化探针
     验证 window.cytoscape 由本地 vendor 脚本提供，而不是 CDN 兜住的假成功。
"""
import io
import json
import os
import re
import subprocess
import urllib.request

CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
EDGE = next((p for p in CANDIDATES if os.path.exists(p)), None)
if not EDGE:
    raise SystemExit('Edge not found')

PORTAL = os.path.dirname(os.path.abspath(__file__))
BASE = 'http://127.0.0.1:8765'
OUT = os.path.join(PORTAL, 'shots')
PROFILE = os.path.join(PORTAL, '_edge_profile_shot')
os.makedirs(OUT, exist_ok=True)

KILL_ANIM = ('<style>*{animation:none!important;transition:none!important}'
             '.page,.page.active{opacity:1!important;animation:none!important}</style>')
FORCE_TOP = '<style>.portal-top--off{opacity:1!important;visibility:visible!important;pointer-events:auto!important}</style>'

PAGES = ['graph', 'probability', 'statistics', 'functions', 'calculus1']


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.read().decode('utf-8')


def edge(url, extra=(), dump=False):
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--user-data-dir=' + PROFILE, '--virtual-time-budget=8000']
    cmd += ['--dump-dom'] if dump else ['--hide-scrollbars']
    cmd += list(extra) + [url]
    return subprocess.run(cmd, capture_output=True)


def shot(tag, url, w, h, extra=()):
    png = os.path.join(OUT, tag + '.png')
    if os.path.exists(png):
        os.remove(png)
    edge(url, extra=list(extra) + ['--window-size=%d,%d' % (w, h), '--screenshot=' + png])
    kb = os.path.getsize(png) / 1024.0 if os.path.exists(png) else -1
    print('%-26s -> %8.1f KB' % (tag, kb))


def tmp_page(html, name='_tmp_shot.html'):
    p = os.path.join(PORTAL, name)
    io.open(p, 'w', encoding='utf-8', newline='').write(html)
    return 'file:///' + p.replace('\\', '/')


def title_of(dump):
    m = re.search(r'<title>([^<]*)</title>', dump.stdout.decode('utf-8', 'ignore'))
    return m.group(1) if m else 'TITLE-NOT-FOUND'


print('EDGE =', EDGE)

# ---------------------------------------------------------------- 1. 门户页
print('--- 门户页（三档响应式 + 页脚） ---')
shot('01_index_desktop', BASE + '/', 1280, 1320)
shot('02_index_tablet', BASE + '/', 834, 1700)
shot('03_index_mobile', BASE + '/', 400, 2400)
shot('13_index_footer', BASE + '/', 1280, 1320)

# ------------------------------------------------- 2. 学科页 顶部（真实状态）
print('--- 学科页 顶部真实状态（左上应见「返回门户」，右下应不见「返回顶部」） ---')
for i, name in enumerate(PAGES, start=4):
    html = fetch('/%s.html' % name).replace('</head>', KILL_ANIM + '\n</head>', 1)
    shot('%02d_%s_top' % (i, name), tmp_page(html), 1280, 900)
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))

# ------------------------------------- 3. 学科页 强制显示「返回顶部」看外观/位置
print('--- 学科页 强制显示「返回顶部」（验证外观、位置、不遮挡正文） ---')
for i, name in enumerate(PAGES, start=9):
    html = fetch('/%s.html' % name)
    html = html.replace('</head>', KILL_ANIM + FORCE_TOP + '\n</head>', 1)
    shot('%02d_%s_nav' % (i, name), tmp_page(html), 1280, 900)
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))

# --------------------------------------------------- 4. 导航按钮行为 DOM 探针
print('--- 导航按钮行为探针（几何 + 显隐 + 点击回顶） ---')
PROBE = """
<script>
(function(){
  var b = document.querySelector('.portal-back');
  var t = document.getElementById('portal-top-btn');
  if (!b || !t) { document.title = 'NAV|' + JSON.stringify({missing:true, back:!!b, top:!!t}); return; }
  var o = {};
  var de = document.documentElement;
  var rb = b.getBoundingClientRect();
  o.backRect = [Math.round(rb.left), Math.round(rb.top), Math.round(rb.width), Math.round(rb.height)];
  o.backHref = b.getAttribute('href');
  o.client = [de.clientWidth, de.clientHeight];
  o.opTop = parseFloat(getComputedStyle(t).opacity);
  o.visTop = getComputedStyle(t).visibility;
  o.maxY = Math.max(0, de.scrollHeight - de.clientHeight);
  window.scrollTo(0, o.maxY);
  setTimeout(function(){
    o.yScrolled = Math.round(window.pageYOffset || 0);
    o.opScrolled = parseFloat(getComputedStyle(t).opacity);
    o.visScrolled = getComputedStyle(t).visibility;
    o.clsScrolled = t.className;
    var rt = t.getBoundingClientRect();
    o.topRect = [Math.round(rt.left), Math.round(rt.top), Math.round(rt.width), Math.round(rt.height)];
    var calls = [];
    var orig = window.scrollTo;
    window.scrollTo = function (a, c) {
      if (typeof a === 'object' && a) { calls.push({kind: 'obj', top: a.top, behavior: a.behavior}); }
      else { calls.push({kind: 'num', x: a, y: c}); }
      return orig.call(window, 0, 0);
    };
    t.click();
    setTimeout(function(){
      o.clickCalls = calls;
      o.yAfterClick = Math.round(window.pageYOffset || 0);
      document.title = 'NAV|' + JSON.stringify(o);
    }, 200);
  }, 200);
})();
</script>
"""
nav_results = {}
for name in PAGES:
    html = fetch('/%s.html' % name)
    html = html.replace('</head>', KILL_ANIM + '\n</head>', 1)
    html = html.replace('</body>', PROBE + '</body>', 1)
    raw = title_of(edge(tmp_page(html), dump=True))
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))
    print('  %-15s %s' % (name + '.html', raw))
    m = re.match(r'NAV\|(\{.*\})$', raw.strip(), re.S)
    if m:
        nav_results[name] = json.loads(m.group(1))

# ------------------------------------------------------ 5. Cytoscape 本地化验收
print('--- Cytoscape 本地化验收 ---')
probe = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
         '<script src="./vendor/cytoscape.min.js"></script></head><body>'
         '<script>document.title="CYCHECK="+(typeof window.cytoscape)'
         '+"|VER="+((window.cytoscape&&window.cytoscape.version)||"none");</script>'
         '</body></html>')
print('RESULT:', title_of(edge(tmp_page(probe, '_tmp_probe.html'), dump=True)))
os.remove(os.path.join(PORTAL, '_tmp_probe.html'))

# ------------------------------------------------------------------- 6. 判据
print('--- NAV ASSERTIONS ---')
fail = 0


def chk(cond, msg):
    global fail
    print('  %-4s %s' % ('PASS' if cond else 'FAIL', msg))
    if not cond:
        fail += 1


for name in PAGES:
    r = nav_results.get(name)
    if not r or r.get('missing'):
        chk(False, '%s: 探针未取到按钮 (%s)' % (name, r))
        continue
    cw, ch = r['client']
    lx, ly, lw, lh = r['backRect']
    tx, ty, tw, th = r['topRect']

    chk(lx <= 24 and ly <= 24,
        '%s: 返回门户固定在左上 (left=%s top=%s)' % (name, lx, ly))
    chk(lh >= 44, '%s: 返回门户高度 %s >= 44 (触控友好)' % (name, lh))
    chk(r['backHref'] == './index.html', '%s: 返回门户 href = %s' % (name, r['backHref']))

    # 位置：右边缘 / 下边缘贴视口（用 clientWidth 排除滚动条）
    chk(abs(tx + tw - (cw - 16)) <= 2 and abs(ty + th - (ch - 16)) <= 2,
        '%s: 返回顶部固定在右下 (right=%s/%s bottom=%s/%s)' % (name, tx + tw, cw - 16, ty + th, ch - 16))

    # 未滚动：隐藏
    chk(r['opTop'] == 0 and r['visTop'] == 'hidden',
        '%s: 顶部时返回顶部隐藏 (opacity=%s visibility=%s)' % (name, r['opTop'], r['visTop']))

    if r['yScrolled'] > 240:
        chk(r['opScrolled'] == 1 and r['visScrolled'] == 'visible',
            '%s: 滚动到底后返回顶部出现 (%s/%s)' % (name, r['opScrolled'], r['visScrolled']))
        chk(r['yAfterClick'] == 0,
            '%s: 点击返回顶部后回到顶部 (y=%s)' % (name, r['yAfterClick']))
        c = r['clickCalls'][0] if r['clickCalls'] else None
        chk(bool(c) and c.get('kind') == 'obj' and c.get('top') == 0,
            '%s: 点击调用 scrollTo({top:0,behavior:smooth}) -> %s' % (name, c))
        # 位置在滚动后仍固定
        chk(abs(tx + tw - (cw - 16)) <= 2, '%s: 滚动后返回顶部仍贴右边' % name)
    else:
        chk('portal-top--off' in r['clsScrolled'],
            '%s: 页面不可滚动(y=%s<=240)，按钮保持隐藏 (正确行为)' % (name, r['yScrolled']))
        print('       (跳过回顶断言：本页 maxY=%s)' % r['maxY'])

print('')
print('NAV RESULT:', 'ALL PASS' if fail == 0 else '%d FAILED' % fail)

leftover = [f for f in os.listdir(PORTAL) if f.startswith('_tmp_')]
print('leftover:', leftover if leftover else 'none')
