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

  ④ 「返回门户」为什么不是固定 top（补丁 P2 v3）
     这 5 个页面的左上角布局差异极大：页面自带的「返回首页 / 返回知识地图」按钮
     底部在 37~70px 之间，而它下方的可用空隙位置各不相同（graph 的 s2 窄屏下，
     返回键底部 70px 到「操作模式」标签 120px 之间只有 50px，而按钮高 44px）。
     实测不存在任何固定下移量能让 5 个页面 × 全部 41 个子节都不遮挡。
     故改为运行时测量：吸附到内置返回键下方 6px，再向下避让「纯文字块 + 可交互
     控件」（canvas/svg 视为图形不避让，与右下角「返回顶部」同属浮动按钮的取舍）。
     因此本脚本的断言不写死 top，而是断言「贴左边 + 不与内置返回键重叠 + 完整可见」。

     另注：学科页的 fadeIn 关键帧含 transform:translateY(12px)，子节切换后立刻
     测量会读到偏下 12px 的中间态。补丁因此在 180ms 与 700ms 各定位一次；
     本脚本的子节几何探针也等到 900ms 后再读，避开这个陷阱。
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

# ------------------------------------------------- 1.1 门户 hero 结构探针
# 门户顶部是满幅渐变色块 + 骑在色块下沿的白色导言卡（对齐各学科页 .home-header / .intro-card）。
# 这几条只能靠几何/计算样式判定，截图看不出「卡片有没有骑上去」「h1 是不是白字」。
HERO_PROBE = """
<script>
(function(){
  var o = {};
  var hero = document.querySelector('.hero');
  var intro = document.querySelector('.intro');
  var h1 = hero && hero.querySelector('h1');
  if (!hero || !intro || !h1) {
    document.title = 'HERO|' + JSON.stringify({missing: true, hero: !!hero, intro: !!intro, h1: !!h1});
    return;
  }
  var de = document.documentElement;
  var cs = getComputedStyle(hero);
  o.heroBg = cs.backgroundImage;
  o.h1Color = getComputedStyle(h1).color;
  o.h1Text = (h1.textContent || '').trim();
  o.viewW = de.clientWidth;
  o.heroW = Math.round(hero.getBoundingClientRect().width);
  o.heroBottom = Math.round(hero.getBoundingClientRect().bottom);
  o.introTop = Math.round(intro.getBoundingClientRect().top);
  o.introLeft = Math.round(intro.getBoundingClientRect().left);
  o.scrollW = de.scrollWidth;
  var c = document.querySelector('.card');
  o.cardLeft = c ? Math.round(c.getBoundingClientRect().left) : -1;
  document.title = 'HERO|' + JSON.stringify(o);
})();
</script>
"""


def run_hero_probe(w, h):
    html = fetch('/index.html').replace('</body>', HERO_PROBE + '</body>', 1)
    raw = title_of(edge(tmp_page(html), w, h, dump=True))
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))
    m = re.match(r'HERO\|(\{.*\})$', raw.strip(), re.S)
    return raw, (json.loads(m.group(1)) if m else None)


print('--- 门户 hero 结构探针 · 桌面 1280x900 ---')
HERO_RAW, HERO = run_hero_probe(1280, 900)
print('  %s' % HERO_RAW)

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

# ------------------------------- 4.1 子节内「返回门户」几何探针（贴左 + 不遮挡内置返回键）
SUBPROBE = """
<script>
(function(){
  try { %(nav)s } catch (e) {}
  setTimeout(function(){
    var b = document.querySelector('.portal-back');
    var de = document.documentElement;
    var rb = b.getBoundingClientRect();
    var own = null;
    var cands = document.querySelectorAll('a,button,span,label');
    for (var i = 0; i < cands.length; i++) {
      var el = cands[i];
      if (el === b || (el.closest && el.closest('.portal-back,.portal-top'))) continue;
      if (el.children.length) continue;
      var txt = (el.textContent || '').replace(/\\s+/g, '');
      if (txt.indexOf('返回') < 0 || txt.length > 16) continue;
      var rr = el.getBoundingClientRect();
      if (rr.width < 1 || rr.height < 1) continue;
      if (own === null || rr.bottom > own[3]) {
        own = [Math.round(rr.left), Math.round(rr.top), Math.round(rr.width), Math.round(rr.height)];
      }
    }
    var o = {
      backRect: [Math.round(rb.left), Math.round(rb.top), Math.round(rb.width), Math.round(rb.height)],
      ownBackRect: own,
      client: [de.clientWidth, de.clientHeight]
    };
    document.title = 'SUB|' + JSON.stringify(o);
  }, 900);
})();
</script>
"""

SUB_NAV = {
    'graph': 'goToSection(1)',
    'probability': 'goTo(1)',
    'statistics': "goTo('t1')",
    'functions': 'goTo(1)',
    'calculus1': 'goC1(1)',
}


def run_sub_probe(name, w, h):
    html = fetch('/%s.html' % name)
    html = html.replace('</head>', KILL_ANIM + '\n</head>', 1)
    html = html.replace('</body>', SUBPROBE % {'nav': SUB_NAV[name]} + '</body>', 1)
    raw = title_of(edge(tmp_page(html), w, h, dump=True))
    os.remove(os.path.join(PORTAL, '_tmp_shot.html'))
    m = re.match(r'SUB\|(\{.*\})$', raw.strip(), re.S)
    return raw, (json.loads(m.group(1)) if m else None)


print('--- 子节内返回门户几何探针 · 桌面 1280x900 ---')
subdesk = {}
for name in PAGES:
    raw, res = run_sub_probe(name, 1280, 900)
    print('  %-15s %s' % (name + '.html', raw))
    subdesk[name] = res

print('--- 子节内返回门户几何探针 · 窄屏 500x780 ---')
subnarrow = {}
for name in PAGES:
    raw, res = run_sub_probe(name, 500, 780)
    print('  %-15s %s' % (name + '.html', raw))
    subnarrow[name] = res

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

    chk(lx <= off + 8, '%s: 返回门户贴左边 (left=%s, 期望 %s)' % (label, lx, off))
    chk(off - 1 <= ly and ly + lh <= ch,
        '%s: 返回门户完整落在视口内 (top=%s h=%s 视口高 %s)' % (label, ly, lh, ch))
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


def assert_sub(label, r):
    """子节内：返回门户必须贴左、完整可见，且落在页面内置「返回…」控件下方且不重叠。"""
    if not r:
        chk(False, '%s: 子节探针未取到数据' % label)
        return
    cw, ch = r['client']
    off = expected_offset(cw)
    lx, ly, lw, lh = r['backRect']
    chk(abs(lx - off) <= 1, '%s: 仍贴左边 (left=%s 期望 %s)' % (label, lx, off))
    chk(ly >= off - 1 and ly + lh <= ch,
        '%s: 完整落在视口内 (top=%s h=%s 视口高 %s)' % (label, ly, lh, ch))
    own = r.get('ownBackRect')
    if not own:
        chk(False, '%s: 未找到页面内置「返回…」控件，无法断言遮挡' % label)
        return
    olx, oly, olw, olh = own
    chk(ly >= oly + olh + 5,
        '%s: 位于内置返回键下方 (top=%s vs 内置底部=%s)' % (label, ly, oly + olh))
    no_overlap = (ly >= oly + olh) or (lx >= olx + olw) or (olx >= lx + lw)
    chk(no_overlap, '%s: 与内置返回键不重叠 (门户 x%s-%s y%s-%s / 内置 x%s-%s y%s-%s)'
        % (label, lx, lx + lw, ly, ly + lh, olx, olx + olw, oly, oly + olh))


for name in PAGES:
    assert_sub('%s@1280 子节' % name, subdesk.get(name))
for name in PAGES:
    assert_sub('%s@500 子节' % name, subnarrow.get(name))

# --- 门户 hero（顶部色块 + 骑边的导言卡） ---
if not HERO or HERO.get('missing'):
    chk(False, '门户 hero: 探针未取到（.hero/.intro/h1 缺失）%s' % HERO_RAW)
else:
    chk('linear-gradient' in HERO['heroBg'] and 'rgb(102, 126, 234)' in HERO['heroBg']
        and 'rgb(118, 75, 162)' in HERO['heroBg'],
        '门户 hero: 顶部为紫蓝渐变色块 (#667eea -> #764ba2)')
    chk(HERO['h1Color'] == 'rgb(255, 255, 255)',
        '门户 hero: 标题为白字，在色块上可读 (color=%s)' % HERO['h1Color'])
    chk(HERO['h1Text'] == '数学探索台', '门户 hero: 标题文案 = %s' % HERO['h1Text'])
    chk(HERO['introTop'] < HERO['heroBottom'],
        '门户导言卡: 骑在色块下沿 (卡顶=%d < 色块底=%d)' % (HERO['introTop'], HERO['heroBottom']))
    chk(abs(HERO['heroW'] - HERO['viewW']) <= 1,
        '门户 hero: 横向满幅 (hero宽=%d 视口=%d)' % (HERO['heroW'], HERO['viewW']))
    chk(HERO['cardLeft'] == HERO['introLeft'],
        '门户导言卡: 与卡片区左边缘对齐 (导言=%d 卡片=%d)' % (HERO['introLeft'], HERO['cardLeft']))
    chk(HERO['scrollW'] <= HERO['viewW'] + 1,
        '门户: 无横向溢出 (scrollW=%d 视口=%d)' % (HERO['scrollW'], HERO['viewW']))

print('')
print('NAV RESULT:', 'ALL PASS' if fail == 0 else '%d FAILED' % fail)

leftover = [f for f in os.listdir(PORTAL) if f.startswith('_tmp_')]
print('leftover:', leftover if leftover else 'none')
