# AIWA Windows Packaging Pipeline (NSIS .exe & WiX .msi)
$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path "$PSScriptRoot\.."
Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "   AIWA Windows Installer Packaging Pipeline     " -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Verify Toolchain
$Tools = @("uv", "node", "npm", "cargo", "rustc")
foreach ($tool in $Tools) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "❌ Required tool '$tool' not found in PATH. Please install it before continuing."
        exit 1
    }
}

# 2. Ensure ICO icon exists for Windows
$IconsDir = "$RepoRoot\apps\desktop\src-tauri\icons"
if (-not (Test-Path "$IconsDir\icon.ico")) {
    Write-Host "🎨 Generating Windows icon.ico..." -ForegroundColor Yellow
    uv run --project "$RepoRoot\backend" python -c "
from PIL import Image
img = Image.open('$IconsDir\icon.png')
img.save('$IconsDir\icon.ico', format='ICO', sizes=[(32,32), (64,64), (128,128), (256,256)])
"
}

# 3. Sync Python & Build Folder-Based Sidecar
Write-Host "📦 Step 1/3: Packaging Python folder-based sidecar (--onedir)..." -ForegroundColor Green
Set-Location $RepoRoot
uv sync --project backend --all-extras
uv run --project backend python scripts\package_sidecar.py

# 4. Build Svelte Frontend
Write-Host "🎨 Step 2/3: Compiling Svelte production assets..." -ForegroundColor Green
Set-Location "$RepoRoot\apps\desktop"
npm install
npm run build

# 5. Build Tauri Windows Installers (NSIS .exe and MSI)
Write-Host "🚀 Step 3/3: Compiling Windows .exe (NSIS) & .msi packages..." -ForegroundColor Green
npx @tauri-apps/cli build --bundles nsis,msi

Write-Host ""
Write-Host "🎉 SUCCESS! Windows Installers generated in:" -ForegroundColor Cyan
Write-Host "   NSIS (.exe): $RepoRoot\apps\desktop\src-tauri\target\release\bundle\nsis\" -ForegroundColor White
Write-Host "   MSI  (.msi): $RepoRoot\apps\desktop\src-tauri\target\release\bundle\msi\" -ForegroundColor White