# Compatibility entry point; use the repository's complete portable build.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot '../build.ps1') @args
