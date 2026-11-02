<#
.SYNOPSIS
    在线主链路：解析 -> 划分 -> 抽取 -> 后处理 -> 评测 ->（可选）图谱。

.DESCRIPTION
    以 5 篇起步验证，再全量。模型跑得久，建议晚上挂机；
    中断后直接重跑，runner 会跳过已完成的文档。

.EXAMPLE
    .\run_pipeline.ps1 -Limit 5 -Split dev            # 先试 5 篇
    .\run_pipeline.ps1 -Split dev                     # dev 全量（57 篇）
    .\run_pipeline.ps1 -Split test -Model "llama3.1:8b-instruct" -Strategy p1
    .\run_pipeline.ps1 -RunKg
#>
param(
    [string]$Corpus = "data\corpus\corpus_fields_split.jsonl",
    [ValidateSet("p0", "p1", "p2")][string]$Strategy = "p1",
    [string]$Model = "qwen2.5:7b-instruct",
    [ValidateSet("train", "dev", "test", "all")][string]$Split = "dev",
    [int]$Limit = 0,
    [string]$RunId = "",
    [switch]$Parse,
    [switch]$SplitData,
    [switch]$RunKg
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

if (-not (Test-Path $Corpus)) {
    Write-Host "找不到语料 $Corpus" -ForegroundColor Red
    Write-Host "可用兜底语料：data\corpus\corpus_fields_split.jsonl" -ForegroundColor Yellow
    exit 1
}

if ($Parse) {
    Write-Host "`n[1/5] 解析 PDF/HTML/TXT" -ForegroundColor Cyan
    Invoke-Py src/prep/parse_pdf.py --include-txt
}

if ($SplitData) {
    Write-Host "`n[2/5] 划分数据集" -ForegroundColor Cyan
    $base = [System.IO.Path]::ChangeExtension($Corpus, $null)
    Invoke-Py src/prep/split_dataset.py --corpus $Corpus
    $Corpus = $base + "_split.jsonl"
}

Write-Host "`n[3/5] 抽取（$Model / $Strategy / $Split）" -ForegroundColor Cyan
$arguments = @("src/llm/runner.py", "--strategy", $Strategy, "--model", $Model,
               "--split", $Split, "--corpus", $Corpus)
if ($RunId) { $arguments += @("--run-id", $RunId) }
if ($Limit -gt 0) { $arguments += @("--limit", "$Limit") }
Invoke-Py @arguments

if (-not $RunId) {
    $safe = ($Model -replace "[^A-Za-z0-9]", "_")
    $RunId = "${Strategy}_${safe}_${Split}"
}

Write-Host "`n[4/5] 后处理（run_id=$RunId）" -ForegroundColor Cyan
Invoke-Py src/llm/postprocess.py --run-id $RunId --corpus $Corpus

if (Test-Path "data\gold\gold.jsonl") {
    Write-Host "`n[5/5] 评测" -ForegroundColor Cyan
    Invoke-Py src/eval/evaluate.py --run-id $RunId --split $Split
} else {
    Write-Host "`n[5/5] 跳过评测：还没有 data\gold\gold.jsonl" -ForegroundColor Yellow
    Write-Host "  生成模板：python tools/make_gold_template.py --split $Split --n 43 --run-id $RunId" -ForegroundColor Yellow
}

if ($RunKg) {
    Write-Host "`n[+] 图谱 CSV 与导入" -ForegroundColor Cyan
    Invoke-Py src/kg/build_nodes.py --runs $RunId
    Invoke-Py src/kg/load_neo4j.py
    Invoke-Py src/kg/queries.py --run q1 --limit 20
}

Write-Host "`n完成。结果目录：data/runs/$RunId" -ForegroundColor Green
Write-Host "  triples.jsonl     清洗后三元组"
Write-Host "  ${RunId}_eval.csv 评测明细"
Write-Host "  errors.jsonl      被丢弃的违规项（错误分析用）"
