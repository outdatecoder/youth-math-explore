# -*- coding: utf-8 -*-
"""数学学习门户 · 视觉走查截图

用法：
  1. 先在门户目录起本地服务： python -m http.server 8765
  2. 运行本脚本：               python _shot.py
  3. 截图输出到 shots/ （已在 .gitignore 中忽略，不参与发布）

为什么要注入禁动画 CSS：
  学科页有 fadeIn 动画，直接截图会抓到中间态（整页发白），看不出内容。
"""
import io
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


def fetch(path):
    with urllib.request.urlopen(BASE + path, timeout=20) as r:
        return r.read().decode('utf-8')


def shot(tag, url, w, h):
    png = os.path.join(OUT, tag + '.png')
    if os.path.exists(png):
        os.remove(png)
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                    '--hide-scrollbars', '--user-data-dir=' + PROFILE,
                    '--virtual-time-budget=4000',
                    '--window-size=%d,%d' % (w, h),
                    '--screenshot=' + png, url], capture_output=True)
    kb = os.path.getsize(png) / 1024.0 if os.path.exists(png) else -1
    print('%-22s -> %8.1f KB' % (tag, kb))


print('EDGE =', EDGE)

print('--- 门户页（三档响应式） ---')
shot('01_index_desktop', BASE + '/', 1280, 1320)
shot('02_index_tablet', BASE + '/', 834, 1700)
shot('03_index_mobile', BASE + '/', 400, 2400)

print('--- 学科页（已注入禁动画） ---')
SUBJECTS = [
    ('04_graph', '/graph.html', 1280, 900),
    ('05_probability', '/probability.html', 1280, 900),
    ('06_statistics', '/statistics.html', 1280, 900),
    ('07_functions', '/functions.html', 1280, 900),
    ('08_calculus1', '/calculus1.html', 1280, 900),
]
for tag, path, w, h in SUBJECTS:
    html = fetch(path)
    injected = html.replace('</head>', KILL_ANIM + '\n</head>', 1)
    tmp = os.path.join(PORTAL, '_tmp_shot.html')
    io.open(tmp, 'w', encoding='utf-8', newline='').write(injected)
    shot(tag, 'file:///' + tmp.replace('\\', '/'), w, h)
    os.remove(tmp)

print('--- Cytoscape 本地化验收 ---')
probe = ('<!DOCTYPE html><html><head><meta charset="utf-8">'
         '<script src="./vendor/cytoscape.min.js"></script></head><body>'
         '<script>document.title="CYCHECK="+(typeof window.cytoscape)'
         '+"|VER="+((window.cytoscape&&window.cytoscape.version)||"none");</script>'
         '</body></html>')
tmp2 = os.path.join(PORTAL, '_tmp_probe.html')
io.open(tmp2, 'w', encoding='utf-8', newline='').write(probe)
dump = subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox',
                       '--user-data-dir=' + PROFILE, '--virtual-time-budget=4000',
                       '--dump-dom', 'file:///' + tmp2.replace('\\', '/')],
                      capture_output=True)
os.remove(tmp2)
m = re.search(r'<title>([^<]*)</title>', dump.stdout.decode('utf-8', 'ignore'))
print('RESULT:', m.group(1) if m else 'TITLE-NOT-FOUND')

leftover = [f for f in os.listdir(PORTAL) if f.startswith('_tmp_')]
print('leftover:', leftover if leftover else 'none')
