#!/usr/bin/env powershell
#Requires -Version 5.1

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  DrugDesign Agent Backend 启动脚本" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# 加载 .env 文件
$envFile = Join-Path $scriptDir ".env"
if (Test-Path $envFile) {
    Write-Host "[INFO] 加载环境变量 .env ..." -ForegroundColor Gray
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*([^#\s][^=]*)\s*=\s*(.*)\s*$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
    Write-Host "[OK] 环境变量已加载" -ForegroundColor Green
} else {
    Write-Host "[WARNING] 未找到 .env 文件，使用默认配置" -ForegroundColor Yellow
    Write-Host "[HINT] 复制 .env.example 为 .env 并配置 KIMI_API_KEY" -ForegroundColor Yellow
    Write-Host ""
}

# 检查 KIMI_API_KEY
if (-not $env:KIMI_API_KEY) {
    Write-Host "[WARNING] KIMI_API_KEY 未设置，AI 聊天功能将不可用！" -ForegroundColor Yellow
    Write-Host "[HINT] 在 .env 文件中设置 KIMI_API_KEY" -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 2
} else {
    Write-Host "[OK] KIMI_API_KEY 已配置" -ForegroundColor Green
}

Write-Host ""
Write-Host "[INFO] 启动 Flask 后端..." -ForegroundColor Gray
Write-Host "[INFO] 端口: $($env:FLASK_PORT)" -ForegroundColor Gray
Write-Host ""

# 确定 Python 路径
$pythonPaths = @(
    "D:\anaconda3\envs\drugdesign\python.exe",
    "python",
    "python3"
)

$python = $null
foreach ($p in $pythonPaths) {
    if (Test-Path $p -ErrorAction SilentlyContinue) {
        $python = $p
        break
    }
}

if (-not $python) {
    Write-Host "[ERROR] 未找到 Python！请确保 Anaconda 环境已安装" -ForegroundColor Red
    exit 1
}

Set-Location $scriptDir
& $python -m backend.app

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[ERROR] 启动失败！请检查：" -ForegroundColor Red
    Write-Host "  1. Anaconda 环境路径是否正确" -ForegroundColor Yellow
    Write-Host "  2. 依赖包是否安装完整" -ForegroundColor Yellow
    Write-Host "  3. 端口是否被占用" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "按 Enter 键退出"
}
