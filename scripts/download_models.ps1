# Download HF models for the vLLM reranker + embed services.
# 1) Get a Read token: https://huggingface.co/settings/tokens
# 2) Paste it below (keep the quotes).
# 3) Run:  powershell -ExecutionPolicy Bypass -File scripts\download_models.ps1
# Files land in E:\invest_agent\models\{BAAI\bge-m3, Qwen2.5-7B-Instruct-AWQ}

# NOTE: 2026-08-11 移除硬编码 token（曾泄露真实 HF token，GitHub secret scanning 拦截）。
# 请填入你自己的 token；占位符触发退出。
$token = "hf_XXX_PUT_YOUR_TOKEN_HERE"

if ($token -like "hf_XXX*") {
    Write-Host "请先在脚本里填入你的 HF token（https://huggingface.co/settings/tokens）" -ForegroundColor Red
    exit 1}

$out = Join-Path (Split-Path $PSScriptRoot -Parent) "models"
New-Item -ItemType Directory -Force -Path (Join-Path $out "BAAI\bge-m3") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $out "Qwen2.5-7B-Instruct-AWQ") | Out-Null

$bge = @(
    "config.json",
    "pytorch_model.bin",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model"
)
$qwen = @(
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
    "model.safetensors.index.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json"
)

Write-Host "== BAAI/bge-m3 ==" -ForegroundColor Cyan
foreach ($f in $bge) {
    $dest = Join-Path $out "BAAI\bge-m3\$f"
    if (Test-Path $dest) { Write-Host "  [skip] $f"; continue }
    Write-Host "  [dl] $f"
    curl.exe -L -C - -H "Authorization: Bearer $token" -o $dest "https://huggingface.co/BAAI/bge-m3/resolve/main/$f"
}

Write-Host "== Qwen/Qwen2.5-7B-Instruct-AWQ ==" -ForegroundColor Cyan
foreach ($f in $qwen) {
    $dest = Join-Path $out "Qwen2.5-7B-Instruct-AWQ\$f"
    if (Test-Path $dest) { Write-Host "  [skip] $f"; continue }
    Write-Host "  [dl] $f"
    curl.exe -L -C - -H "Authorization: Bearer $token" -o $dest "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-AWQ/resolve/main/$f"
}

Write-Host ""
Write-Host "DONE. 告诉我下载完成后，我会把模型拷进 WSL 并启动服务。" -ForegroundColor Green
