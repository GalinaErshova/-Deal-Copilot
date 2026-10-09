$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$server = Join-Path $repoRoot ".local-model\runtime\llama-server.exe"
$model = Join-Path $repoRoot ".local-model\MiMo-7B-RL-Q4_K_M.gguf"

if (-not (Test-Path -LiteralPath $server)) {
    throw "Не найден llama-server.exe: $server. Скачайте CPU-сборку llama.cpp из официальных релизов."
}
if (-not (Test-Path -LiteralPath $model)) {
    throw "Не найдена модель MiMo: $model. Скачайте MiMo-7B-RL-Q4_K_M.gguf из Hugging Face."
}

& $server `
    --model $model `
    --alias mimo-7b-rl-q4_k_m `
    --ctx-size 8192 `
    --api-key local `
    --host 127.0.0.1 `
    --port 8080
