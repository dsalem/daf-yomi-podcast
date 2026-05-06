"""dafyomi CLI — entrypoints for scan, normalize, upload, rss, run, status."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import func, select

from .db import init_schema, make_engine, make_session_factory, project_root
from .ia import upload_pending
from .models import Episode, Season
from .normalize import ensure_ffmpeg, normalize_pending
from .rss import write_feed
from .scan import scan_into_db

# Load .env if present so env vars apply to all subcommands.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv()
except ImportError:
    pass

app = typer.Typer(
    add_completion=False,
    help="Bulk-publish a Daf Yomi shiur back-catalog to Internet Archive.",
)
console = Console()


def _session():
    engine = make_engine()
    init_schema(engine)
    return make_session_factory(engine)()


@app.command("init-db")
def cmd_init_db() -> None:
    """Create the SQLite schema and seed the seasons table."""
    engine = make_engine()
    init_schema(engine)
    console.print(f"[green]Schema initialized at[/] {engine.url}")


@app.command("scan")
def cmd_scan(folder: Path = typer.Argument(..., exists=True, file_okay=False)) -> None:
    """Walk <folder>, parse audio filenames, populate the DB. Idempotent."""
    with _session() as session:
        report = scan_into_db(folder, session)
    console.print(
        f"[green]Scan complete:[/] added {report.added}, "
        f"already-present {report.already_present}"
    )
    for f in report.unmatched_folders:
        console.print(f"[yellow]warning:[/] folder did not match any masechet: {f}")
    for f in report.misfiled:
        console.print(f"[yellow]misfiled:[/] {f}")
    for f in report.unparseable_files[:20]:
        console.print(f"[yellow]warning:[/] could not parse filename: {f}")
    if len(report.unparseable_files) > 20:
        console.print(
            f"[yellow]... and {len(report.unparseable_files) - 20} more unparseable files[/]"
        )


@app.command("normalize")
def cmd_normalize(limit: Optional[int] = typer.Option(None, "--limit", "-n")) -> None:
    """Run ffmpeg loudnorm on episodes that have not been normalized yet."""
    ensure_ffmpeg()
    with _session() as session:
        n = normalize_pending(session, limit=limit)
    console.print(f"[green]Normalized {n} episode(s).[/]")


@app.command("upload")
def cmd_upload(
    limit: Optional[int] = typer.Option(None, "--limit", "-n"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print what would happen, don't upload."),
) -> None:
    """Upload normalized episodes to Internet Archive."""
    with _session() as session:
        n = upload_pending(session, limit=limit, dry_run=dry_run)
    label = "Would upload" if dry_run else "Uploaded"
    console.print(f"[green]{label} {n} episode(s).[/]")


@app.command("rss")
def cmd_rss(
    out: Path = typer.Option(
        project_root() / "feed.xml", "--out", "-o", help="Output path for feed.xml"
    ),
) -> None:
    """Generate the podcast RSS XML from the DB."""
    with _session() as session:
        path = write_feed(session, out)
    console.print(f"[green]Wrote[/] {path}")


@app.command("run")
def cmd_run(
    folder: Optional[Path] = typer.Argument(None, exists=True, file_okay=False),
    limit: Optional[int] = typer.Option(None, "--limit", "-n"),
) -> None:
    """Chain scan -> normalize -> upload -> rss."""
    with _session() as session:
        if folder is not None:
            report = scan_into_db(folder, session)
            console.print(
                f"[green]scan:[/] added {report.added}, "
                f"already-present {report.already_present}"
            )
        ensure_ffmpeg()
        n_norm = normalize_pending(session, limit=limit)
        console.print(f"[green]normalize:[/] {n_norm}")
        n_up = upload_pending(session, limit=limit, dry_run=False)
        console.print(f"[green]upload:[/] {n_up}")
        path = write_feed(session, project_root() / "feed.xml")
        console.print(f"[green]rss:[/] {path}")


@app.command("status")
def cmd_status() -> None:
    """Print a summary: episodes scanned / normalized / uploaded, by season."""
    with _session() as session:
        rows = session.execute(
            select(
                Season.season_number,
                Season.masechet_name_en,
                func.count(Episode.id),
                func.count(Episode.normalized_at),
                func.count(Episode.ia_uploaded_at),
            )
            .join(Episode, Episode.season_id == Season.id, isouter=True)
            .group_by(Season.id)
            .order_by(Season.season_number)
        ).all()

    table = Table(title="Daf Yomi Podcast — status")
    table.add_column("#", justify="right")
    table.add_column("Masechet")
    table.add_column("Scanned", justify="right")
    table.add_column("Normalized", justify="right")
    table.add_column("Uploaded", justify="right")

    totals = [0, 0, 0]
    for season_n, name, scanned, normalized, uploaded in rows:
        if scanned == 0:
            continue
        table.add_row(
            str(season_n), name, str(scanned), str(normalized), str(uploaded)
        )
        totals[0] += scanned
        totals[1] += normalized
        totals[2] += uploaded

    table.add_section()
    table.add_row("", "[bold]Total[/]", str(totals[0]), str(totals[1]), str(totals[2]))
    console.print(table)


if __name__ == "__main__":
    app()
