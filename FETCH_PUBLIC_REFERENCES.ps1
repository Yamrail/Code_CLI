# Optional reviewer reference fetch; requires only standard Git and PowerShell.
# It never changes Code_CLI, machine-global config, credentials, or CAD projects.
param([string]$Root = (Join-Path $PSScriptRoot 'reference'))
$ErrorActionPreference = 'Stop'
$git = Get-Command git -ErrorAction SilentlyContinue
if (-not $git) {
  Write-Output 'HOLD_REFERENCE_GIT_UNAVAILABLE: main offline fixture remains usable.'
  exit 2
}
New-Item -ItemType Directory -Path $Root -Force | Out-Null
$specs = @(
  @{Name='EEA'; URL='https://github.com/Yamrail/EEA.git'; SHA='8cd2c0286213ff51b7e95587040aedef55c1181e'},
  @{Name='GPLCore'; URL='https://github.com/Yamrail/Yamrail.git'; SHA='0d6f1532a496c2033502d11adbebdda18b11e963'}
)
$results = @()
foreach ($s in $specs) {
  $target = Join-Path $Root $s.Name
  if (-not (Test-Path -LiteralPath $target)) {
    & git clone --no-checkout -- $s.URL $target
    if ($LASTEXITCODE -ne 0) { throw "HOLD_CLONE_FAILED:$($s.Name)" }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $target '.git'))) {
    throw "HOLD_EXISTING_NON_GIT_PATH:$($s.Name)"
  }
  $origin = (& git -C $target remote get-url origin).Trim()
  if ($origin -notin @($s.URL, ($s.URL -replace '\.git$',''))) {
    throw "HOLD_WRONG_ORIGIN:$($s.Name)"
  }
  & git -C $target checkout --detach $s.SHA
  if ($LASTEXITCODE -ne 0) { throw "HOLD_PIN_CHECKOUT_FAILED:$($s.Name)" }
  $actual = (& git -C $target rev-parse HEAD).Trim()
  if ($actual -ne $s.SHA) { throw "HOLD_PIN_MISMATCH:$($s.Name)" }
  $results += [ordered]@{name=$s.Name; repo=$s.URL; commit=$actual; state='PASS_PINNED_SOURCE'}
}
$receipt = Join-Path $Root 'PUBLIC_SOURCE_PINS_RECEIPT.json'
if (Test-Path -LiteralPath $receipt) { throw 'HOLD_EXISTING_RECEIPT_PRESERVE_OR_USE_NEW_DIRECTORY' }
$results | ConvertTo-Json -Depth 5 | Set-Content -Path $receipt -Encoding utf8
Write-Output "PASS_PUBLIC_SOURCE_PINS: $receipt"
Write-Output 'References are read-only review material, not executable Code_CLI runtime authority.'
