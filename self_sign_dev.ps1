param(
    [string]$ExePath = ".\dist\CATX-Systems-Torch-RCON-Tool.exe",
    [string]$CertName = "CATX Systems LLC Development Code Signing",
    [string]$PfxPath = ".\CATX-Dev-CodeSigning.pfx",
    [string]$PfxPassword = ""
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $ExePath)) {
    throw "EXE not found: $ExePath"
}

$cert = Get-ChildItem Cert:\CurrentUser\My |
    Where-Object { $_.Subject -eq "CN=$CertName" } |
    Select-Object -First 1

if (-not $cert) {
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject "CN=$CertName" `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyExportPolicy Exportable `
        -KeyLength 2048 `
        -HashAlgorithm SHA256
}

if ($PfxPassword -ne "") {
    $secure = ConvertTo-SecureString -String $PfxPassword -Force -AsPlainText
    Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $secure | Out-Null
}

$signtoolCandidates = @(
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\x64\signtool.exe",
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.26100.0\x64\signtool.exe",
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe",
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.22000.0\x64\signtool.exe",
    "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe"
)

$signtool = $signtoolCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $signtool) {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) {
        $signtool = $command.Source
    }
}

if (-not $signtool) {
    throw "signtool.exe not found. Install Windows SDK or add signtool to PATH."
}

& $signtool sign `
    /fd SHA256 `
    /sha1 $cert.Thumbprint `
    /tr http://timestamp.digicert.com `
    /td SHA256 `
    $ExePath

& $signtool verify /pa /v $ExePath
