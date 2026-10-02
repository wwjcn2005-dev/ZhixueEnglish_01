# P2-1-C1 offline audio decode: MP3 -> WAV (source read-only; output goes to the given dir)
#
# Uses the built-in Windows media transcoder (WinRT MediaTranscoder). This machine has no
# ffmpeg, and this approach installs nothing and never touches the network.
#
# Usage:
#   powershell -NoProfile -STA -ExecutionPolicy Bypass -File mp3_to_wav.ps1 `
#       -Src <input.mp3> -OutDir <dir> -OutName <out.wav>
#
# Note: TranscodeAsync returns an IAsyncAction that PowerShell cannot await directly, so this
# script starts the transcode and waits until the output file size has been stable for a while.
param(
    [Parameter(Mandatory = $true)][string]$Src,
    [Parameter(Mandatory = $true)][string]$OutDir,
    [Parameter(Mandatory = $true)][string]$OutName,
    [int]$StableChecks = 4,
    [int]$SleepMs = 500
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
$asTaskGenericOp = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -like 'IAsyncOperation*' -and
    $_.GetParameters()[0].ParameterType.Name -notlike '*WithProgress*'
})[0]
function AwaitOp($op, $type) {
    $t = $asTaskGenericOp.MakeGenericMethod($type).Invoke($null, @($op))
    $t.Wait(-1) | Out-Null
    $t.Result
}
$SF   = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$SD   = [Windows.Storage.StorageFolder, Windows.Storage, ContentType = WindowsRuntime]
$CC   = [Windows.Storage.CreationCollisionOption, Windows.Storage, ContentType = WindowsRuntime]
$MB   = [Windows.Media.MediaProperties.MediaEncodingProfile, Windows.Media, ContentType = WindowsRuntime]
$AQ   = [Windows.Media.MediaProperties.AudioEncodingQuality, Windows.Media, ContentType = WindowsRuntime]
$PREP = [Windows.Media.Transcoding.PrepareTranscodeResult, Windows.Media, ContentType = WindowsRuntime]

$srcFile = AwaitOp ($SF::GetFileFromPathAsync($Src)) $SF
$folder = AwaitOp ($SD::GetFolderFromPathAsync($OutDir)) $SD
$dstFile = AwaitOp ($folder.CreateFileAsync($OutName, $CC::ReplaceExisting)) $SF
$outPath = $dstFile.Path
$profile = $MB::CreateWav($AQ::High)
$tr = New-Object -TypeName Windows.Media.Transcoding.MediaTranscoder
$tr.AlwaysReencode = $true
$prep = AwaitOp ($tr.PrepareFileTranscodeAsync($srcFile, $dstFile, $profile)) $PREP
if (-not $prep.CanTranscode) {
    Write-Output ('ABORT FailureReason=' + $prep.FailureReason)
    exit 2
}
$null = $prep.TranscodeAsync()
$sw = [Diagnostics.Stopwatch]::StartNew()
$last = -1
$stable = 0
while ($sw.Elapsed.TotalSeconds -lt 600) {
    Start-Sleep -Milliseconds $SleepMs
    $len = 0
    if (Test-Path -LiteralPath $outPath) { $len = (Get-Item -LiteralPath $outPath).Length }
    if ($len -gt 0 -and $len -eq $last) { $stable++ } else { $stable = 0 }
    $last = $len
    if ($stable -ge $StableChecks) { break }
}
$sw.Stop()
Write-Output ('OK out=' + $outPath + ' bytes=' + $last + ' ms=' + $sw.ElapsedMilliseconds)
