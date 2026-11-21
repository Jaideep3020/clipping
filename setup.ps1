# setup.ps1 - Windows-native one-time setup for ClipForge SOTA Video Studio

Write-Host ""
Write-Host "── ClipForge SOTA Video Studio Setup (Windows) ──" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check System Binaries ───────────────────────────────────────────────────
Write-Host "[1] Checking system binaries..." -ForegroundColor Yellow

$ffmpegCmd = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobeCmd = Get-Command ffprobe -ErrorAction SilentlyContinue

if (-not $ffmpegCmd -or -not $ffprobeCmd) {
    Write-Host "    [!] FFmpeg or FFprobe not found in PATH." -ForegroundColor Red
    Write-Host "        Please install FFmpeg using: winget install Gyan.FFmpeg" -ForegroundColor Gray
    Write-Host "        Or download from: https://www.gyan.dev/ffmpeg/builds/" -ForegroundColor Gray
    exit 1
} else {
    $ffmpegVer = (& ffmpeg -version 2>$null | Select-Object -First 1)
    Write-Host "    [OK] FFmpeg present: $ffmpegVer" -ForegroundColor Green
}

$ytdlpCmd = Get-Command yt-dlp -ErrorAction SilentlyContinue
if ($ytdlpCmd) {
    Write-Host "    [OK] yt-dlp present" -ForegroundColor Green
} else {
    Write-Host "    [!] yt-dlp not found in system PATH (will use virtual environment)" -ForegroundColor DarkYellow
}

# Find appropriate Python executable
$pythonExec = $null
$pyLauncher = Get-Command py -ErrorAction SilentlyContinue

if ($pyLauncher) {
    foreach ($ver in @('-3.12', '-3.11', '-3.10', '-3')) {
        $testPy = (& py $ver -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0 -and $testPy) {
            $pythonExec = "py $ver"
            $pyVerStr = (& py $ver --version 2>$null)
            Write-Host "    [OK] Python launcher found: $pyVerStr ($pythonExec)" -ForegroundColor Green
            break
        }
    }
}

if (-not $pythonExec) {
    $sysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($sysPython) {
        $pythonExec = "python"
        $pyVerStr = (& python --version 2>$null)
        Write-Host "    [OK] System Python found: $pyVerStr" -ForegroundColor Green
    } else {
        Write-Host "    [ERROR] Python not found! Please install Python 3.10-3.12" -ForegroundColor Red
        exit 1
    }
}

# ── 2. Virtual Environment ─────────────────────────────────────────────────────
Write-Host ""
Write-Host "[2] Preparing Python virtual environment..." -ForegroundColor Yellow
$venvDir = Join-Path -Path $PSScriptRoot -ChildPath '.venv'
$venvPython = Join-Path -Path (Join-Path -Path $venvDir -ChildPath 'Scripts') -ChildPath 'python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "    Creating .venv with $pythonExec..." -ForegroundColor Gray
    Invoke-Expression "$pythonExec -m venv .venv"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    [ERROR] Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "    [OK] Created .venv/" -ForegroundColor Green
} else {
    Write-Host "    [OK] .venv/ already exists" -ForegroundColor Green
}

# ── 3. Configuration (.env) ────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3] Checking environment configuration..." -ForegroundColor Yellow
$envPath = Join-Path -Path $PSScriptRoot -ChildPath '.env'
$envExamplePath = Join-Path -Path $PSScriptRoot -ChildPath '.env.example'

if (-not (Test-Path -LiteralPath $envPath) -and (Test-Path -LiteralPath $envExamplePath)) {
    Copy-Item -LiteralPath $envExamplePath -Destination $envPath
    Write-Host "    [OK] Created .env from .env.example" -ForegroundColor Green
} else {
    Write-Host "    [OK] .env file present" -ForegroundColor Green
}

# ── 4. Dependencies ────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[4] Checking dependencies from requirements.txt..." -ForegroundColor Yellow
$requirementsPath = Join-Path -Path $PSScriptRoot -ChildPath 'requirements.txt'

if (Test-Path -LiteralPath $requirementsPath) {
    & $venvPython -m pip install -r $requirementsPath -q
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    [!] Pip returned non-zero code during dependency check." -ForegroundColor DarkYellow
    } else {
        Write-Host "    [OK] Dependencies verified and up to date" -ForegroundColor Green
    }
}

# ── 5. Neural Weights ──────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[5] Verifying SOTA Neural Weights..." -ForegroundColor Yellow
$weightsDir = Join-Path -Path $PSScriptRoot -ChildPath 'engine'
$yunetModel = Join-Path -Path $weightsDir -ChildPath 'face_detection_yunet.onnx'

if (Test-Path -LiteralPath $yunetModel) {
    $fileSize = (Get-Item -LiteralPath $yunetModel).Length
    $kb = [math]::Round($fileSize / 1024, 1)
    Write-Host "    [OK] YuNet Face Tracker Model present ($kb KB)" -ForegroundColor Green
} else {
    Write-Host "    Downloading YuNet neural face tracker model..." -ForegroundColor Gray
    if (-not (Test-Path -LiteralPath $weightsDir)) {
        New-Item -ItemType Directory -Path $weightsDir | Out-Null
    }
    $yunetUrl = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
    Invoke-WebRequest -Uri $yunetUrl -OutFile $yunetModel
    Write-Host "    [OK] YuNet model downloaded" -ForegroundColor Green
}

# ── 6. Verification ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[6] Running dependency verification check..." -ForegroundColor Yellow
& $venvPython -c "import torch, whisper, cv2, scenedetect, PIL, gradio; print('    [OK] Core libraries (torch, whisper, cv2, scenedetect, PIL, gradio) verified!')"

# ── 7. Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ClipForge SOTA Studio Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Usage Modes:" -ForegroundColor White
Write-Host "    1. Web Studio UI:     .\.venv\Scripts\python.exe start_ui.py" -ForegroundColor Cyan
Write-Host "    2. Auto Pipeline:     .\.venv\Scripts\python.exe pipeline.py `"https://youtu.be/ID`" --vertical --captions" -ForegroundColor Cyan
Write-Host "    3. GTA 6 / Gaming:    .\.venv\Scripts\python.exe pipeline.py `"https://youtu.be/ID`" --gta6 --vertical" -ForegroundColor Cyan
Write-Host "    4. Chapters CLI:      .\.venv\Scripts\python.exe clipper.py `"https://youtu.be/ID`"" -ForegroundColor Cyan
Write-Host ""
