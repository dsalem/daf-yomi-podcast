# Regenerate feed.xml from the current DB and push it to GitHub.
# Run this after each chunk completes.
#
#   .\publish.ps1
#
# Spotify and Apple repoll the feed every few hours, so new episodes appear
# automatically — usually within 6–24 hours of running this.

$ErrorActionPreference = "Stop"

# Pick up ffmpeg / rclone from system PATH (winget installs may not be in
# the inherited shell PATH on first run).
$env:PATH = [System.Environment]::GetEnvironmentVariable('PATH','User') + ';' + [System.Environment]::GetEnvironmentVariable('PATH','Machine')

Push-Location $PSScriptRoot
try {
    Write-Host "==> Regenerating feed.xml" -ForegroundColor Cyan
    .\.venv\Scripts\python.exe -m dafyomi.cli rss

    $changes = git status --porcelain feed.xml
    if (-not $changes) {
        Write-Host "feed.xml unchanged; nothing to push." -ForegroundColor Yellow
        return
    }

    Write-Host "==> Committing and pushing" -ForegroundColor Cyan
    git add feed.xml
    $count = & .\.venv\Scripts\python.exe -c "from sqlalchemy import select, func; from dafyomi.db import make_engine, make_session_factory, init_schema; from dafyomi.models import Episode; e=make_engine(); init_schema(e); s=make_session_factory(e)(); print(s.scalar(select(func.count(Episode.id)).where(Episode.ia_uploaded_at.is_not(None))))"
    git commit -m "Update feed.xml ($count episodes)"
    git push

    Write-Host "==> Done. Spotify/Apple will see new episodes within a few hours." -ForegroundColor Green
}
finally {
    Pop-Location
}
