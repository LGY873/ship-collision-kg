<#
.SYNOPSIS
    离线全链路：不联网、不调模型，把「种子表 -> 兜底语料 -> 划分 -> 后处理 -> 评测 -> 图谱 CSV」跑通。

.DESCRIPTION
    用于 Day 0 验证环境，以及后续每次改代码后的回归测试。

.EXAMPLE
    .\run_offline.ps1
    .\run_offline.ps1 -Us "D:\data\美国海事汇总(1).xlsx" -Uk "D:\data\英国海事(1).xlsx"
#>
param(
    [string]$Us = "C:\Users\18191\Desktop\美国海事汇总(1).xlsx",
    [string]$Uk = "C:\Users\18191\Desktop\英国海事(1).xlsx",
    [switch]$KeepSmoke
)

$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
Set-Location $PSScriptRoot

function Invoke-Py {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "python 命令失败（exit $LASTEXITCODE）：$($Arguments -join ' ')"
    }
}

# 0. 依赖自检
& python -c "import openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "当前 python 缺少 openpyxl。请先激活虚拟环境并 pip install -r requirements.txt" -ForegroundColor Red
    Write-Host "当前解释器：$((Get-Command python).Source)" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n[1/6] 种子表" -ForegroundColor Cyan
Invoke-Py src/crawl/build_seed.py --us $Us --uk $Uk

Write-Host "`n[2/6] 字段级兜底语料" -ForegroundColor Cyan
Invoke-Py src/prep/build_corpus_from_fields.py

Write-Host "`n[3/6] 数据集划分" -ForegroundColor Cyan
Invoke-Py src/prep/split_dataset.py --corpus data/corpus/corpus_fields.jsonl

Write-Host "`n[4/6] 伪造 3 篇模型输出（冒烟）" -ForegroundColor Cyan
Invoke-Py tools/smoke_test.py

Write-Host "`n[5/6] 后处理 + 转标注模板 + 评测" -ForegroundColor Cyan
Invoke-Py src/llm/postprocess.py --run-id smoke_test
Invoke-Py tools/make_gold_template.py --split test --n 3 --run-id smoke_test --out data/gold/gold_smoke.jsonl
Invoke-Py src/eval/evaluate.py --run-id smoke_test --gold data/gold/gold_smoke.jsonl --split test

Write-Host "`n[6/6] 图谱 CSV" -ForegroundColor Cyan
Invoke-Py src/kg/build_nodes.py --runs smoke_test

if (-not $KeepSmoke) {
    Write-Host "`n清理冒烟产物（加 -KeepSmoke 可保留）" -ForegroundColor DarkGray
    Remove-Item -Recurse -Force data/runs/smoke_test -ErrorAction SilentlyContinue
    Remove-Item -Force data/gold/gold_smoke.jsonl -ErrorAction SilentlyContinue
    Remove-Item -Force data/kg/nodes.csv, data/kg/rels.csv -ErrorAction SilentlyContinue
}

Write-Host "`n离线链路全部通过。" -ForegroundColor Green
Write-Host "产物：data/seed/seed.csv、data/corpus/corpus_fields*.jsonl、data/corpus/splits.json"
