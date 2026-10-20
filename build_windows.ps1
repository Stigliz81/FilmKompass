param([string]$OutputRoot = "")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
foreach ($iconAsset in @('assets/filmkompass.ico','assets/filmkompass.png')) {
  if (!(Test-Path -LiteralPath $iconAsset)) { throw "Verbindliches Filmrollen-Icon fehlt: $iconAsset. Kein Ersatzicon verwenden." }
}
$builder = Join-Path $PSScriptRoot "qa/build-env/Scripts/python.exe"
if (!(Test-Path -LiteralPath $builder)) {
  py -3.13 -m venv qa/build-env
  if ($LASTEXITCODE -ne 0) { throw "Buildumgebung fehlgeschlagen" }
}
& $builder -m pip install -r requirements.txt -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "Buildabhaengigkeiten fehlen" }
$versionParts = & $builder -c "from app_info import APP_VERSION, BUILD_NUMBER; print(APP_VERSION); print(BUILD_NUMBER); from app_info import EXE_STEM; print(EXE_STEM)"
if ($LASTEXITCODE -ne 0) { throw "Versionskonfiguration ungueltig" }
$exeStem = $versionParts[2]
$versionPath = "$($versionParts[0])/Build$($versionParts[1])"
if (!$OutputRoot) { $OutputRoot = "dist/AP12/$versionPath" }
$target = Join-Path $OutputRoot $exeStem
if (Test-Path -LiteralPath $target) { throw "Buildziel existiert bereits. Bestehenden Build erhalten; anderes OutputRoot verwenden." }
$buildRoot = "build/AP12/$versionPath"
$versionResource = "$buildRoot/windows_version_info.txt"
& $builder app_info.py $versionResource
if ($LASTEXITCODE -ne 0) { throw "Versionsressource fehlgeschlagen" }
$versionResource = (Resolve-Path -LiteralPath $versionResource).Path
$assetArgs = @()
$publicAssets = & $builder -c "from package_release import SOURCE_FILES; print('\n'.join(p for p in SOURCE_FILES if p.startswith('assets/')))"
foreach ($asset in $publicAssets) { $destination = Split-Path -Parent $asset; $assetArgs += @('--add-data', "$PSScriptRoot/$asset;$destination") }
& $builder -m PyInstaller --clean --windowed --onedir --name $exeStem --distpath $OutputRoot --workpath $buildRoot --specpath build/AP12 --icon "$PSScriptRoot/assets/filmkompass.ico" --version-file $versionResource @assetArgs --exclude-module playwright moviepilot_manager.py
if ($LASTEXITCODE -ne 0) { throw "Build fehlgeschlagen" }
Get-FileHash -Algorithm SHA256 (Join-Path $target "$exeStem.exe")
