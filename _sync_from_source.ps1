<#
  数学学习门户 · 源仓库 -> 门户目录 同步脚本
  ==================================================================
  作用：把 5 个学习页从各自的源仓库同步到门户目录，并重新应用门户专用补丁。
  特性：幂等 —— 可重复运行，结果一致。
  用法：双击 _sync.cmd（推荐），或
        powershell -ExecutionPolicy Bypass -File _sync_from_source.ps1

  铁律：不要在门户目录手工编辑那 5 个 HTML —— 下次同步会被覆盖。
        所有修改请在源仓库里做（2026-08-16-18-32-38 / 2026-07-27-23-03-56）。

  补丁清单：
    P1  Cytoscape 本地化   unpkg CDN -> ./vendor/cytoscape.min.js
    P2  门户导航按钮       左上「← 返回门户」(自适应下移到页面自带返回键下方)
                          + 右下「返回顶部 ↑」(滚动 >240px 淡入)
    行尾规范化             统一为 LF
#>

$ErrorActionPreference = 'Stop'

$PortalRoot = $PSScriptRoot
if (-not $PortalRoot) { $PortalRoot = (Get-Location).Path }

# ---------- 映射表：源文件 -> 门户文件名 ----------
$MAP = @(
    [ordered]@{ Src = 'D:\WorkBuddy\2026-07-27-23-03-56\图论交互学习.html';    Dst = 'graph.html'       },
    [ordered]@{ Src = 'D:\WorkBuddy\2026-08-16-18-32-38\概率交互学习.html';    Dst = 'probability.html' },
    [ordered]@{ Src = 'D:\WorkBuddy\2026-08-16-18-32-38\统计学交互学习.html';  Dst = 'statistics.html'  },
    [ordered]@{ Src = 'D:\WorkBuddy\2026-08-16-18-32-38\函数先导.html';        Dst = 'functions.html'   },
    [ordered]@{ Src = 'D:\WorkBuddy\2026-08-16-18-32-38\微积分上篇_瞬间.html'; Dst = 'calculus1.html'   }
)

# ---------- 补丁 P1：Cytoscape 本地化（正则匹配任意版本号，抗源侧升版） ----------
$CDN_PATTERN = '<script src="https://unpkg\.com/cytoscape@[\d\.]+/dist/cytoscape\.min\.js"></script>'
$CDN_REPLACE = '<script src="./vendor/cytoscape.min.js"></script>'

# ---------- 补丁 P2：门户导航按钮 ----------
#   v3 布局：
#     · 左上「← 返回门户」—— 位置由脚本在运行时测量决定：吸附到页面自带「返回…」
#       控件下方 6px，并向下避让正文文字与可交互控件（画布/图形视为软遮挡，不避让，
#       与右下角「返回顶部」同属浮动按钮的既定取舍）。
#       原因：这 5 个页面的左上角布局差异极大（graph 的 s2 窄屏下，返回键底部 70px
#       到「操作模式」标签 120px 之间只有 50px，而按钮高 44px），不存在任何固定的
#       下移量能让 5 个页面 × 全部子节都躲开。
#     · 右下「返回顶部 ↑」—— 下滚超过 240px 才淡入。
#   用 <!-- portal-nav:start/end --> 包裹，方便整块替换，不留残骸。
#   注：5 个页面原本 position:fixed 计数为 0，两枚按钮不会与页面自有元素争夺层。
$BACK_PATCH = @'
<!-- portal-nav:start -->
<style id="portal-nav-style">
.portal-back,.portal-top{position:fixed;z-index:99999;display:inline-flex;align-items:center;justify-content:center;border-radius:24px;background:rgba(28,32,44,.86);color:#fff;font-size:15px;font-weight:600;text-decoration:none;box-shadow:0 6px 20px rgba(0,0,0,.25);font-family:system-ui,-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;transition:opacity .2s,visibility .2s,transform .15s,background .15s}
.portal-back{left:16px;top:16px;height:48px;padding:0 18px}
.portal-top{right:16px;bottom:16px;height:48px;padding:0 18px;border:0;cursor:pointer;-webkit-appearance:none;appearance:none}
.portal-back:hover,.portal-top:hover{background:rgba(28,32,44,.96);transform:translateY(-2px)}
.portal-back:visited{color:#fff}
.portal-top--off{opacity:0;visibility:hidden;pointer-events:none}
@media (max-width:520px){.portal-back,.portal-top{height:44px;padding:0 14px;font-size:14px}.portal-back{left:12px;top:12px}.portal-top{right:12px;bottom:12px}}
@media print{.portal-back,.portal-top{display:none}}
</style>
<a href="./index.html" class="portal-back" aria-label="返回门户">← 返回门户</a>
<button type="button" class="portal-top" id="portal-top-btn" aria-label="返回顶部">返回顶部 ↑</button>
<script id="portal-nav-script">
(function(){
  var back = document.querySelector('.portal-back');
  var topBtn = document.getElementById('portal-top-btn');

  /* ---------- 返回顶部：滚动超过 240px 才显示 ---------- */
  if (topBtn) {
    var sync = function(){
      var y = window.pageYOffset || document.documentElement.scrollTop || 0;
      if (y > 240) { topBtn.classList.remove('portal-top--off'); }
      else { topBtn.classList.add('portal-top--off'); }
    };
    topBtn.addEventListener('click', function(){
      try { window.scrollTo({ top: 0, behavior: 'smooth' }); }
      catch (e) { window.scrollTo(0, 0); }
    });
    window.addEventListener('scroll', sync, { passive: true });
    sync();
  }

  /* ---------- 返回门户：吸附到页面自带「返回…」控件下方，并避让文字/控件 ---------- */
  if (!back) return;

  var SKIP_TAGS = { HTML:1, BODY:1, HEAD:1, SCRIPT:1, STYLE:1, META:1, TITLE:1, LINK:1,
                    CANVAS:1, SVG:1, IMG:1, VIDEO:1, AUDIO:1, IFRAME:1 };
  var CTRL_TAGS = { A:1, BUTTON:1, INPUT:1, SELECT:1, TEXTAREA:1, LABEL:1, OPTION:1 };
  var GAP = 6;          /* 与页面自带返回控件的最小间距 */
  var MAX_EXTRA = 260;  /* 向下寻找空位的最大探索距离 */

  function scrollY(){ return window.pageYOffset || document.documentElement.scrollTop || 0; }
  function mine(el){
    return el === back || el === topBtn || (el.closest && el.closest('.portal-back,.portal-top'));
  }

  /* 页面自带「返回…」控件的底部（文档坐标，与滚动位置无关）。
     只认页面顶部 240px 内的控件，避免滚动后被正文里的“返回”字样带偏。 */
  function ownNavBottom(sy){
    var best = null;
    var els = document.querySelectorAll('a,button,span,div[onclick],label');
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      if (mine(el) || el.children.length) continue;
      var t = (el.textContent || '').replace(/\s+/g, '');
      if (t.indexOf('返回') < 0 || t.length > 16) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      var dt = r.top + sy;
      if (dt > 240) continue;
      var b = r.bottom + sy;
      if (best === null || b > best) best = b;
    }
    return best;
  }

  /* 左上窄带内的「硬遮挡」：正文文字 + 可交互控件。
     canvas / svg / img 及其内部文字视为图形，不参与避让。 */
  function blockers(l, w, top, bottom){
    var out = [], x0 = l - 6, x1 = l + w + 6, sy = scrollY();
    var els = document.querySelectorAll('*');
    for (var i = 0; i < els.length; i++) {
      var el = els[i], tag = el.tagName;
      if (SKIP_TAGS[tag] || mine(el)) continue;
      if (el.closest && el.closest('svg,canvas')) continue;
      var r = el.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      if (r.right <= x0 || r.left >= x1) continue;
      var t = r.top + sy, b = r.bottom + sy;
      if (b <= top || t >= bottom) continue;
      var hard = CTRL_TAGS[tag] || el.hasAttribute('onclick');
      if (!hard) {
        /* 纯文字块（无子元素且有文字）整体算遮挡。不加长度上限：这类元素的盒子
           就是它文字本身的范围，不会像带子元素的容器那样把整列正文算成一块。 */
        hard = (el.children.length === 0) && (el.textContent || '').trim().length > 0;
      }
      if (hard) out.push([r.left, t, r.right, b]);
    }
    return out;
  }

  function place(){
    if (!back.offsetHeight) return;
    var sy = scrollY();
    var r = back.getBoundingClientRect();
    var l = r.left, w = r.width, h = r.height;
    var base = (document.documentElement.clientWidth <= 520) ? 12 : 16;
    var ob = ownNavBottom(sy);
    var start = (ob === null) ? base : Math.max(base, Math.ceil(ob) + GAP);
    var maxTop = Math.max(base, Math.round(window.innerHeight * 0.55) - h);
    var limit = Math.min(start + MAX_EXTRA, maxTop);
    var boxes = blockers(l, w, start - h, start + MAX_EXTRA + h);
    var y = start;
    for (; y <= limit; y++) {
      var hit = false;
      for (var i = 0; i < boxes.length; i++) {
        var e = boxes[i];
        if (e[2] <= l || l + w <= e[0]) continue;
        if (e[3] <= y || y + h <= e[1]) continue;
        hit = true; break;
      }
      if (!hit) break;
    }
    if (y > limit) y = start;      /* 实在找不到空位就退回起点，不做无意义的下漂 */
    var next = Math.round(y) + 'px';
    if (back.style.top !== next) back.style.top = next;
  }

  /* 两次校正：子节切换带 .page.active { animation: fadeIn .4s }，其中含
     transform: translateY(12px)。动画进行中测量会偏下 12px，所以 180ms 先粗定位，
     700ms（动画结束后）再按稳定布局精校一次。place() 结果相同则不写 DOM。 */
  var timer = 0, settle = 0;
  function schedule(){
    clearTimeout(timer);  timer  = setTimeout(place, 180);
    clearTimeout(settle); settle = setTimeout(place, 700);
  }

  window.addEventListener('resize', schedule);
  window.addEventListener('orientationchange', schedule);
  window.addEventListener('load', schedule);
  document.addEventListener('click', schedule, true);
  if (window.MutationObserver) {
    try {
      new MutationObserver(schedule).observe(document.documentElement,
        { attributes: true, attributeFilter: ['class'], subtree: true });
    } catch (e) {}
  }
  place();      /* 解析阶段先定位，避免首屏闪动 */
  schedule();   /* 字体/图片就位后再校正一次 */
})();
</script>
<!-- portal-nav:end -->
'@

# ---------- 旧补丁剥离规则 ----------
#   P2 从 v1 升级到 v2 时必须先剥掉旧版，否则会残留两枚右下角按钮。
#   这是历史包袱，但对“拿旧副本再跑一次脚本”的场景是必需的。
$STRIP_NAV_MARKED = '(?s)<!--\s*portal-nav:start\s*-->.*?<!--\s*portal-nav:end\s*-->\s*'
$STRIP_NAV_LEGACY = '(?s)<style id="portal-back-style">.*?</a>\s*'

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$rows = @()

foreach ($item in $MAP) {
    $row = [ordered]@{ File = $item.Dst; Copy = 'FAIL'; CdnPatch = 'n/a'; NavStrip = 'none'; BtnPatch = 'FAIL'; Bytes = 0 }

    if (-not (Test-Path -LiteralPath $item.Src)) {
        $row.Copy = 'SOURCE-MISSING'
        $rows += [pscustomobject]$row
        continue
    }

    # 1) 读入源文件（ReadAllText 自动识别并剥离 BOM）
    $html = [System.IO.File]::ReadAllText($item.Src)

    # 2) 补丁 P1
    if ($html -match $CDN_PATTERN) {
        $html = $html -replace $CDN_PATTERN, $CDN_REPLACE
        $row.CdnPatch = 'REPLACED'
    } elseif ($html -match 'vendor/cytoscape\.min\.js') {
        $row.CdnPatch = 'ALREADY'
    }

    # 3) 剥离旧版导航补丁（源文件干净时此处必然无命中）
    $stripped = 0
    $before = $html
    $html = [regex]::Replace($html, $STRIP_NAV_MARKED, '')
    $html = [regex]::Replace($html, $STRIP_NAV_LEGACY, '')
    if ($html.Length -ne $before.Length) { $stripped = 1 }
    $row.NavStrip = if ($stripped) { 'STRIPPED' } else { 'none' }

    # 4) 补丁 P2（</body> 在每个页面恰好出现 1 次，锚点安全）
    $idx = $html.LastIndexOf('</body>')
    if ($idx -ge 0) {
        $html = $html.Insert($idx, $BACK_PATCH)
        $row.BtnPatch = 'INJECTED'
    } else {
        $row.BtnPatch = 'NO-ANCHOR'
    }

    # 5) 行尾规范化：统一为 LF
    #    实测源文件存在 mixed 行尾（graph.html / statistics.html 混用 CRLF 与 LF）。
    #    若不做规范化，每次同步后 git 都会依据 .gitattributes 重新 normalize，
    #    导致 git status 反复出现无意义的“已修改”。HTML 中 CRLF 与 LF 等价，规范化无副作用。
    $html = $html.Replace("`r`n", "`n").Replace("`r", "`n")

    # 6) 写出（UTF-8 无 BOM）
    $dstPath = Join-Path $PortalRoot $item.Dst
    [System.IO.File]::WriteAllText($dstPath, $html, $Utf8NoBom)

    $row.Copy = 'OK'
    $row.Bytes = (Get-Item -LiteralPath $dstPath).Length
    $rows += [pscustomobject]$row
}

# ---------- 自校验 ----------
Write-Host ''
Write-Host '===== SYNC REPORT =====' -ForegroundColor Cyan
$rows | Format-Table -AutoSize

$fail = 0
foreach ($item in $MAP) {
    $dstPath = Join-Path $PortalRoot $item.Dst
    if (-not (Test-Path -LiteralPath $dstPath)) {
        Write-Host "FAIL  $($item.Dst)  not generated" -ForegroundColor Red; $fail++; continue
    }
    $t = [System.IO.File]::ReadAllText($dstPath)
    if ($t -match 'unpkg\.com')     { Write-Host "FAIL  $($item.Dst)  still references unpkg CDN"    -ForegroundColor Red; $fail++ }
    if (-not ($t -match 'portal-back'))    { Write-Host "FAIL  $($item.Dst)  missing back-to-portal btn" -ForegroundColor Red; $fail++ }
    if (-not ($t -match 'portal-top-btn')) { Write-Host "FAIL  $($item.Dst)  missing back-to-top btn"    -ForegroundColor Red; $fail++ }
    if (-not ($t -match 'ownNavBottom'))   { Write-Host "FAIL  $($item.Dst)  missing adaptive nav placement" -ForegroundColor Red; $fail++ }
    if (([regex]::Matches($t, '<!--\s*portal-nav:start\s*-->')).Count -ne 1) {
        Write-Host "FAIL  $($item.Dst)  nav patch not injected exactly once" -ForegroundColor Red; $fail++
    }
    if ($t -match '<style id="portal-back-style">') { Write-Host "FAIL  $($item.Dst)  legacy v1 nav patch still present" -ForegroundColor Red; $fail++ }
    if (-not ($t -match '</html>')) { Write-Host "FAIL  $($item.Dst)  html structure incomplete"     -ForegroundColor Red; $fail++ }
}

Write-Host ''
if ($fail -eq 0) {
    Write-Host 'ALL PASS -- portal copies synced to latest source' -ForegroundColor Green
} else {
    Write-Host "$fail check(s) failed, see FAIL lines above" -ForegroundColor Red
    exit 1
}
