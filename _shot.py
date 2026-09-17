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
     （实测会拍到空白区，且按钮出现在画面底部而非 top:16px），所以显隐行为改为
     读 computedStyle + getBoundingClientRect，并用 scrollTo 打桩验证「点击回顶」。
     外观/位置则由「强制显示后的截图」负责，两者互补。

     headless 的四个陷阱（都实际踩过）：
       · --virtual-time-budget 会冻结 CSS transition，直接读 opacity 拿到的是起始值
         （1 而不是 0）。故探针页额外注入 transition:none 让状态瞬时生效。
         这只影响淡入动画本身，不影响「滚动位置 -> class 切换」这条被验证的逻辑。
       · window.innerWidth 含滚动条宽度，右/下对齐断言必须用
         document.documentElement.clientWidth/clientHeight，否则会误报约 16px 偏差。
       · **共享 --user-data-dir 会残留上一次的窗口尺寸**：截图用了 400x780 之后，
         不带 --window-size 的 --dump-dom 探针会继续跑在窄屏下（实测 clientWidth 481），
         于是桌面断言在手机布局下判定 -> 大面积假红。
         → **每次 Edge 调用都显式传 --window-size**，不依赖默认值。
       · 滚动事件在虚拟时钟下可能晚于断言（同一份夹具里 4/5 页正常、1 页读到旧 class）。
         → 滚动后显式 dispatchEvent(new Event('scroll'))，让探针确定性收敛；
         这仍然走页面自己的监听器，不是绕过被测逻辑。

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

# 与补丁 P2 的媒体查询保持一致：<=520px 用 12px 偏移 + 44px 高，否则 16px + 48px
NARROW_MAX = 520
OFF_NARROW, OFF_WIDE = 12, 16
H_NARROW, H_WIDE = 44, 48


def expected_offset(cw):
    return OFF_NARROW if cw <= NARROW_MAX else OFF_WIDE


def expected_height(cw):
    return H_NARROW if cw <= NARROW_MAX else H_WIDE


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.read().decode('utf-8')


def edge(url, w, h, extra=(), dump=False):
    """每次调用都显式带 --window-size：共享 profile 会残留上次尺寸，不能靠默认值。"""
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--user-data-dir=' + PROFILE, '--virtual-time-budget=8000',
           '--window-size=%d,%d' % (w, h)]
    cmd += ['--dump-dom'] if dump else ['--hide-scrollbars']
    cmd += list(extra) + [url]
    return subprocess.run(cmd, capture_output=True)


def shot(tag, url, w, h, extra=()):
    png = os.path.join(OUT, tag + '.png')
    if os.path.exists(png):
        os.remove(png)
    edge(url, w, h, extra=list(extra) + ['--screenshot=' + png])
    kb = os.path.getsize(png) / 1024.0 if os.path.exists(png) else -1
    print('%-28s -> %8.1f KB' % (tag, kb))


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

# ------------------------------------------- 3.1 窄屏（平板/手机，目标用户主用）
print('--- 窄屏 500px（验证 44px 高 + 12px 偏移） ---')
for name, tag in (('graph', '14_graph_mobile'), ('calculus1', '15_calculus1_mobile')):
    for suffix, css in (('_top', KILL_ANIM), ('_nav', KILL_ANIM + FORCE_TOP)):
        html = fetch('/%s.html' % name).replace('</head>', css + '\n</head>', 1)
        shot(tag + suffix, tmp_page(html), 500, 780)
        os.remove(os.path.join(PORTAL, '_tmp_shot.html'))

# --------------------------------------------------- 4. 导航按钮行为 DOM 探针
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
  // 虚拟时钟下滚动事件可能晚于断言 -> 显式触发（走的仍是页面自己的监听器）
  window.dispatchEvent(new Event('scroll'));
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


def run_probe(name, w, h):
    html = fetch('/%s.html' % name)
    html = html.replace('</head>', KILL_ANIM + '\n</head>', 1)
    html = html.replace('</body>', PROBE + '</body>', 1)
    raw = title_of(edge(tmp_page(html), w, h, dump=True))
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))
    m = re.match(r'NAV\|(\{.*\})$', raw.strip(), re.S)
    return raw, (json.loads(m.group(1)) if m else None)


print('--- 导航按钮行为探针 · 桌面 1280x900 ---')
desktop = {}
for name in PAGES:
    raw, res = run_probe(name, 1280, 900)
    print('  %-15s %s' % (name + '.html', raw))
    desktop[name] = res

print('--- 导航按钮行为探针 · 窄屏 500x780（抽验 graph） ---')
raw, narrow = run_probe('graph', 500, 780)
print('  graph.html      %s' % raw)

# ------------------------------------------------------ 5. Cytoscape 本地化验收
print('--- Cytoscape 本地化验收 ---')
probe = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
         '<script src="./vendor/cytoscape.min.js"></script></head><body>'
         '<script>document.title="CYCHECK="+(typeof window.cytoscape)'
         '+"|VER="+((window.cytoscape&&window.cytoscape.version)||"none");</script>'
         '</body></html>')
print('RESULT:', title_of(edge(tmp_page(probe, '_tmp_probe.html'), 1280, 900, dump=True)))
os.remove(os.path.join(PORTAL, '_tmp_probe.html'))

# ------------------------------------------------------------------- 6. 判据
print('--- NAV ASSERTIONS ---')
fail = 0


def chk(cond, msg):
    global fail
    print('  %-4s %s' % ('PASS' if cond else 'FAIL', msg))
    if not cond:
        fail += 1


def assert_page(label, r):
    """按钮几何/显隐断言。偏移量与高度按当前视口宽度推导，不写死。"""
    cw, ch = r['client']
    off, eh = expected_offset(cw), expected_height(cw)
    lx, ly, lw, lh = r['backRect']
    tx, ty, tw, th = r['topRect']

    chk(lx <= off + 8 and ly <= off + 8,
        '%s: 返回门户固定在左上 (left=%s top=%s, 期望 %s)' % (label, lx, ly, off))
    chk(lh >= 44, '%s: 返回门户高度 %s >= 44 (触控友好)' % (label, lh))
    chk(r['backHref'] == './index.html', '%s: 返回门户 href = %s' % (label, r['backHref']))

    chk(abs(tx + tw - (cw - off)) <= 2 and abs(ty + th - (ch - off)) <= 2,
        '%s: 返回顶部固定在右下 (right=%s/%s bottom=%s/%s, 期望偏移 %s)'
        % (label, tx + tw, cw - off, ty + th, ch - off, off))
    chk(abs(th - eh) <= 1, '%s: 返回顶部高度 %s（视口宽 %s 期望 %s）' % (label, th, cw, eh))

    chk(r['opTop'] == 0 and r['visTop'] == 'hidden',
        '%s: 顶部时返回顶部隐藏 (opacity=%s visibility=%s)' % (label, r['opTop'], r['visTop']))

    if r['yScrolled'] > 240:
        chk(r['opScrolled'] == 1 and r['visScrolled'] == 'visible',
            '%s: 滚动后返回顶部出现 (%s/%s)' % (label, r['opScrolled'], r['visScrolled']))
        chk(r['yAfterClick'] == 0,
            '%s: 点击返回顶部后回到顶部 (y=%s)' % (label, r['yAfterClick']))
        c = r['clickCalls'][0] if r['clickCalls'] else None
        chk(bool(c) and c.get('kind') == 'obj' and c.get('top') == 0,
            '%s: 点击调用 scrollTo({top:0,behavior:smooth}) -> %s' % (label, c))
        chk(abs(tx + tw - (cw - off)) <= 2, '%s: 滚动后返回顶部仍贴右边' % label)
    else:
        chk('portal-top--off' in r['clsScrolled'],
            '%s: 页面不可滚动(y=%s<=240)，按钮保持隐藏 (正确行为)' % (label, r['yScrolled']))


for name in PAGES:
    r = desktop.get(name)
    if not r or r.get('missing'):
        chk(False, '%s: 探针未取到按钮 (%s)' % (name, r))
        continue
    assert_page('%s@1280' % name, r)

if narrow and not narrow.get('missing'):
    assert_page('graph@500', narrow)
else:
    chk(False, 'graph@500: 探针未取到按钮 (%s)' % narrow)

print('')
print('NAV RESULT:', 'ALL PASS' if fail == 0 else '%d FAILED' % fail)

leftover = [f for f in os.listdir(PORTAL) if f.startswith('_tmp_')]
print('leftover:', leftover if leftover else 'none')
