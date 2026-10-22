param(
    [Parameter(Mandatory = $true)]
    [string]$Message,
    [string]$Thread
)

$ErrorActionPreference = 'Stop'
if (-not $Thread) {
    $peerFile = Join-Path $PSScriptRoot '../.tools/codex-peer.json'
    if (-not (Test-Path -LiteralPath $peerFile)) {
        throw 'No local CAF peer configured. Supply -Thread with the verified CAF session UUID.'
    }
    $peer = Get-Content -LiteralPath $peerFile -Raw | ConvertFrom-Json
    $Thread = $peer.thread_id
}
$peerId = [guid]::Empty
if (-not [guid]::TryParse($Thread, [ref]$peerId)) {
    throw 'Peer thread must be a verified session UUID.'
}
if ($Thread -eq $env:CODEX_THREAD_ID) {
    throw 'Refusing to send the teammate message to the current session.'
}
& codex.cmd queue --thread $Thread --message $Message
if ($LASTEXITCODE -ne 0) {
    throw "Codex failed to queue the peer message (exit $LASTEXITCODE)."
}
