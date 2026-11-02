<#
.SYNOPSIS
    离线自检：不联网、不调模型，验证环境与整条链路的代码是否正确。

.DESCRIPTION
    分三步：
      1) 环境自检（依赖、数据文件、Ollama/Neo4j 是否在）
      2) 离线回归测试（分节/截断、JSON 修复、事故节点合成、图谱导出、评测 FN 口径）
      3) 可选：从桌面 Excel 重建种子表与语料（-Rebuild）

.EXAMPLE
    .\run_offline.ps1
    .\run_offline.ps1 -Rebuild
    .\run_offline.ps1 -Us "C:\Users\18191\Desktop\美国海事汇总(1).xlsx" -Uk "C:\Users\18191\Desktop\英国海事(1).xlsx"
#>
param(
    [string]$Us = "",
    [string]$Uk = "",
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

# 优先用项目虚拟环境，没有才用系统 python
$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

function Invoke-Py {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $Py @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "命令失败（exit $LASTEXITCODE）：$Py $($Arguments -join ' ')"
    }
}

Write-Host "解释器：$Py" -ForegroundColor DarkGray

Write-Host "`n[1/3] 环境自检" -ForegroundColor Cyan
Invoke-Py tools/check_env.py

if ($Rebuild) {
    if (-not $Us) { $Us = "C:\Users\18191\Desktop\美国海事汇总(1).xlsx" }
    if (-not $Uk) { $Uk = "C:\Users\18191\Desktop\英国海事(1).xlsx" }
    if (-not (Test-Path $Us) -or -not (Test-Path $Uk)) {
        throw "找不到种子 Excel：$Us / $Uk（用 -Us / -Uk 指定路径）"
    }
    Write-Host "`n[2/3] 重建种子表与字段级语料" -ForegroundColor Cyan
    Invoke-Py src/crawl/build_seed.py --us $Us --uk $Uk
    Invoke-Py src/prep/build_corpus_from_fields.py
    Invoke-Py src/prep/split_dataset.py --corpus data/corpus/corpus_fields.jsonl
} else {
    Write-Host "`n[2/3] 跳过重建（要重建请加 -Rebuild）" -ForegroundColor DarkGray
}

Write-Host "`n[3/3] 离线回归测试" -ForegroundColor Cyan
Invoke-Py tools/smoke_test.py

Write-Host "`n离线自检全部通过。" -ForegroundColor Green
Write-Host "注意：这里不验证模型效果。真实抽取请用："
Write-Host "  $Py src/llm/runner.py --split dev --run-id p1_qwen7b_dev" -ForegroundColor DarkGray
