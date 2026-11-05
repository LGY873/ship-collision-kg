<#
.SYNOPSIS
  在新机器上一键恢复 ship-collision-kg 的运行环境。

.DESCRIPTION
  做四件事：检查 Python、建 .venv 装依赖、跑环境自检与冒烟测试、打印下一步命令。
  可选 -WithTraining 额外装训练栈（torch cu124 + transformers/peft/bitsandbytes），
  可选 -SkipOllama 跳过 Ollama 检测提示。

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup_new_machine.ps1
.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\setup_new_machine.ps1 -WithTraining
#>
param(
    [switch]$WithTraining,
    [switch]$SkipOllama,
    [string]$PipIndex = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try { chcp 65001 | Out-Null } catch { }

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Write-Step([string]$text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkGray
    Write-Host $text -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkGray
}

function Write-Ok([string]$text) { Write-Host ("[OK]   " + $text) -ForegroundColor Green }
function Write-Warn2([string]$text) { Write-Host ("[WARN] " + $text) -ForegroundColor Yellow }
function Write-Err2([string]$text) { Write-Host ("[FAIL] " + $text) -ForegroundColor Red }

# ---------- 1/4 Python ----------
Write-Step "1/4 检查 Python（需要 3.10 - 3.12）"

$pyExe = $null
$pyVerArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    foreach ($v in @("-3.12", "-3.11", "-3.10")) {
        & py $v -V 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $pyExe = "py"; $pyVerArgs = @($v); break }
    }
}
if (-not $pyExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    & python -V 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { $pyExe = "python"; $pyVerArgs = @() }
}
if (-not $pyExe) {
    Write-Err2 "没找到 Python。装一个 3.10-3.12（勾选 Add to PATH），然后重跑本脚本。"
    exit 1
}
$verText = (& $pyExe @pyVerArgs -V 2>&1) -join " "
Write-Ok ("Python: " + $verText.Trim())

# ---------- 2/4 venv + 依赖 ----------
Write-Step "2/4 建虚拟环境并安装依赖"

$venvPy = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Ok "已存在 .venv，跳过创建"
} else {
    Write-Host "创建 .venv ..."
    & $pyExe @pyVerArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Write-Err2 "venv 创建失败"; exit 1 }
    Write-Ok "已创建 .venv"
}

& $venvPy -m pip install --upgrade pip -q --disable-pip-version-check --no-input
$pipArgs = @("-m", "pip", "install", "-r", "requirements.txt", "--disable-pip-version-check", "--no-input", "--progress-bar", "off")
if ($PipIndex -ne "") { $pipArgs += @("-i", $PipIndex) }
Write-Host "安装 requirements.txt（首次约 1-3 分钟）..."
& $venvPy @pipArgs
if ($LASTEXITCODE -ne 0) {
    Write-Err2 "依赖安装失败。若卡在下载，加 -PipIndex https://pypi.tuna.tsinghua.edu.cn/simple 重试。"
    exit 1
}
Write-Ok "依赖安装完成"

# ---------- 3/4 自检 ----------
Write-Step "3/4 环境自检 + 离线冒烟测试"

& $venvPy "tools\check_env.py"
if ($LASTEXITCODE -ne 0) { Write-Warn2 "check_env 返回非 0，看上面的 WARN/FAIL 项（Neo4j 未部署属正常）" }

& $venvPy "tools\smoke_test.py"
if ($LASTEXITCODE -ne 0) { Write-Err2 "冒烟测试失败，环境不完整，先别往下走"; exit 1 }
Write-Ok "冒烟测试全过（18 项断言）"

# ---------- 4/4 训练栈（可选） ----------
if ($WithTraining) {
    Write-Step "4a/4 安装训练栈（torch cu124 + transformers/peft/bitsandbytes）"
    & $venvPy -m pip install torch --index-url https://download.pytorch.org/whl/cu124 --disable-pip-version-check --no-input --progress-bar off
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "torch cu124 安装失败，退回 CPU 版（只能做数据侧调试，不能训练）"
        & $venvPy -m pip install torch
    }
    & $venvPy -m pip install transformers peft bitsandbytes datasets accelerate trl sentencepiece --disable-pip-version-check --no-input --progress-bar off
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "训练栈部分安装失败，检查 bitsandbytes 是否支持当前平台" }
    Write-Host ""
    Write-Host "训练前必须设置镜像（HuggingFace 直连在国内会超时）：" -ForegroundColor Yellow
    Write-Host '  $env:HF_ENDPOINT = "https://hf-mirror.com"'
}

# ---------- 下一步 ----------
Write-Step "4/4 接下来怎么跑"

if (-not $SkipOllama) {
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if ($ollama) {
        Write-Ok ("Ollama 已安装: " + $ollama.Source)
        Write-Host '  拉模型: ollama pull qwen2.5:7b-instruct'
    } else {
        Write-Warn2 "没检测到 ollama（抽取要用它）。装好后执行: ollama pull qwen2.5:7b-instruct"
    }
}

Write-Host ""
Write-Host "常用命令：" -ForegroundColor Cyan
Write-Host '  .venv\Scripts\python.exe tools\check_env.py'
Write-Host '  .venv\Scripts\python.exe src\llm\runner.py --strategy p1 --model qwen2.5:7b-instruct --split dev --run-id p1_qwen7b_dev'
Write-Host '  .venv\Scripts\python.exe src\llm\postprocess.py --run-id p1_qwen7b_dev'
Write-Host '  .venv\Scripts\python.exe src\eval\evaluate.py --run-id p1_qwen7b_dev'
Write-Host '  .venv\Scripts\python.exe src\kg\build_nodes.py --runs p1_qwen7b_dev'
Write-Host '  .venv\Scripts\python.exe tools\smoke_test.py'
Write-Host ""
Write-Host "微调对照实验的完整步骤见 docs\微调方案.md（第 10 节是换机清单）。" -ForegroundColor Cyan
Write-Ok "环境就绪"