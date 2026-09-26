# build-css.ps1 — rebuild app.css from input.css + templates
# Run after any template change. Takes ~2 seconds.

$ErrorActionPreference = "Stop"

$css_dir = Join-Path $PSScriptRoot "app\static\css"
$exe = Join-Path $css_dir "tailwindcss.exe"
$input_css = Join-Path $css_dir "input.css"
$output_css = Join-Path $css_dir "app.css"

if (-not (Test-Path $exe)) {
    Write-Error "tailwindcss.exe not found at $exe"
    exit 1
}

Write-Host "Building CSS..." -ForegroundColor Cyan

Push-Location $css_dir
try {
    & $exe -i "input.css" -o "app.css" --minify
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tailwind build failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$size = (Get-Item $output_css).Length
Write-Host "Done. app.css is $([math]::Round($size/1KB, 1)) KB" -ForegroundColor Green