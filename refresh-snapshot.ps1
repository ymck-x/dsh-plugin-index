<#
从服务器拉取权威清单，并重建插件产物（发版前必跑）。

为什么要有这一步：
  插件包里的内置快照是构建期产物，它必须来自服务器上的权威清单，
  而不是任何一台机器的本地数据 —— 所有用户装到的必须是同一份东西，
  所以这一步要可重复、可核对，而不是「手工 scp 一次算一次」。

用法：
  pwsh -File refresh-snapshot.ps1 -Server ubuntu@<服务器> -Key <私钥路径>
  pwsh -File refresh-snapshot.ps1 -Server ubuntu@<服务器> -Key <私钥> -DryRun

  也可以用环境变量代替参数：DSH_INDEX_SERVER / DSH_INDEX_KEY
  默认远端路径取自 dsh-index 的 publish 产物（public/plugins.json）。
#>
param(
    [string]$Server = $env:DSH_INDEX_SERVER,
    [string]$Key = $env:DSH_INDEX_KEY,
    [string]$RemoteManifest = "/home/ubuntu/dsh-index/public/plugins.json",
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$data = Join-Path $root 'data\plugins.json'

if (-not $Server) { throw "缺少服务器地址：用 -Server 指定，或设环境变量 DSH_INDEX_SERVER（例 ubuntu@1.2.3.4）" }
if (-not $Key) { throw "缺少 SSH 私钥：用 -Key 指定，或设环境变量 DSH_INDEX_KEY" }

Write-Host "拉取清单 $Server`:$RemoteManifest"
scp -i $Key -o BatchMode=yes "$Server`:$RemoteManifest" $data
if ($LASTEXITCODE -ne 0) { throw "scp 失败（退出码 $LASTEXITCODE）" }

$payload = Get-Content $data -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $payload.plugins) { throw "清单里没有 plugins 数组，拒绝用它构建" }
Write-Host ("  条目 {0} · 生成于 {1} · {2:N1} MiB" -f `
    $payload.plugins.Count, $payload.generated_at, ((Get-Item $data).Length / 1MB))

if ($DryRun) {
    Write-Host "DryRun：已更新 data/plugins.json，未重建产物。"
    exit 0
}

Write-Host "重建 lib/client.js（内置首片快照）"
python (Join-Path $root 'build-client.py')
if ($LASTEXITCODE -ne 0) { throw "build-client.py 失败" }

Write-Host "重建 site/index.json + 分片（本地预览用）"
python (Join-Path $root 'build-site.py')
if ($LASTEXITCODE -ne 0) { throw "build-site.py 失败" }

Write-Host ""
Write-Host "完成。发版前请确认："
Write-Host "  1. package.json 版本号已递增"
Write-Host "  2. 打 tag 并推送后，用户才拿得到这份快照"
Write-Host "  3. 服务器侧的 index.json / 分片由 dsh-index 的 publish 定时产出，无需手工同步"
