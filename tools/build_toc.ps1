param(
    [string]$Md = "docs\论文初稿.md",
    [string]$Out = "docs\论文初稿-模板版.docx",
    [string]$Toc = "docs\toc.json"
)

$ErrorActionPreference = "Stop"
$proj = Split-Path -Parent $PSScriptRoot
Set-Location $proj

$dshPy = "C:\Users\18191\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
$venvPy = Join-Path $proj ".venv\Scripts\python.exe"
$pdf = [System.IO.Path]::ChangeExtension((Join-Path $proj $Out), ".pdf")
$env:PYTHONIOENCODING = "utf-8"

function Export-Pdf([string]$docx, [string]$pdfPath) {
    if (Test-Path $pdfPath) { Remove-Item $pdfPath -Force }
    $app = New-Object -ComObject KWps.Application
    try {
        $app.Visible = $false
        $doc = $app.Documents.Open((Join-Path $proj $docx))
        $doc.ExportAsFixedFormat($pdfPath, 17)
        $doc.Close(0)
    } finally {
        $app.Quit()
    }
    if (-not (Test-Path $pdfPath)) { throw "PDF 导出失败：$pdfPath" }
}

Write-Host "[1/6] 生成初版 docx（目录页码留空）" -ForegroundColor Cyan
& $dshPy "tools\md_to_template_docx.py" --src $Md --out $Out
if ($LASTEXITCODE -ne 0) { throw "生成 docx 失败" }

Write-Host "[2/6] 导出 PDF 量页码" -ForegroundColor Cyan
Export-Pdf $Out $pdf

Write-Host "[3/6] 抽取标题页码 -> $Toc" -ForegroundColor Cyan
& $venvPy "tools\toc_extract.py" --md $Md --pdf $pdf --out $Toc

Write-Host "[4/6] 用真实页码重建 docx" -ForegroundColor Cyan
& $dshPy "tools\md_to_template_docx.py" --src $Md --out $Out --toc $Toc
if ($LASTEXITCODE -ne 0) { throw "重建 docx 失败" }

Write-Host "[5/6] 再导出 PDF" -ForegroundColor Cyan
Export-Pdf $Out $pdf

Write-Host "[6/6] 校验页码与目录是否一致" -ForegroundColor Cyan
& $venvPy "tools\toc_extract.py" --md $Md --pdf $pdf --out $Toc --verify

Write-Host "完成：$Out" -ForegroundColor Green
Write-Host "PDF：$pdf" -ForegroundColor Green
