param(
    [string]$Name = "CATX-Systems-Torch-RCON-Tool",
    [switch]$DebugBuild
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".\main.py")) {
    throw "main.py not found. Run this script from the repository root."
}

python -m pip install --upgrade pip
python -m pip install pyinstaller loguru requests keyring pillow

$iconArgs = @()
$dataArgs = @()

if (Test-Path ".\logo.png") {
    Write-Host "Found logo.png. Generating logo.ico..." -ForegroundColor Green
    python -c "from PIL import Image; img=Image.open('logo.png').convert('RGBA'); img.save('logo.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
    $iconArgs = @("--icon", ".\logo.ico")
    $dataArgs = @("--add-data", "logo.png;.")
}
else {
    Write-Host "logo.png not found. Building without custom EXE icon." -ForegroundColor Yellow
}

$commonArgs = @(
    "--onefile",
    "--name", $Name,
    "--hidden-import", "keyring.backends.Windows",
    "--collect-all", "keyring"
) + $iconArgs + $dataArgs + @(".\main.py")

if ($DebugBuild) {
    pyinstaller @commonArgs
}
else {
    pyinstaller "--windowed" @commonArgs
}

Write-Host "Build complete: dist\$Name.exe" -ForegroundColor Green
