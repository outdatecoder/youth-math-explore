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
    P2  门户导航按钮       左上「← 返回门户」 + 右下「返回顶部 ↑」（滚动 >240px 淡入）
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
#   v2 布局：左上角固定「← 返回门户」；右下角固定「返回顶部 ↑」（下滚超过 240px 才淡入）
#   用 <!-- portal-nav:start/end --> 包裹，方便以后整块替换，不留残骸。
#   注：5 个页面均以 window 为滚动容器（各页自身用了 window.scrollTo(0,0)），
#       且原本 position:fixed 计数为 0，所以两枚按钮不会撞到页面自有元素。
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
  var btn = document.getElementById('portal-top-btn');
  if (!btn) return;
  function sync(){
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    if (y > 240) { btn.classList.remove('portal-top--off'); }
    else { btn.classList.add('portal-top--off'); }
  }
  btn.addEventListener('click', function(){
    try { window.scrollTo({ top: 0, behavior: 'smooth' }); }
    catch (e) { window.scrollTo(0, 0); }
  });
  window.addEventListener('scroll', sync, { passive: true });
  sync();
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
