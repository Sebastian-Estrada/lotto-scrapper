#!/usr/bin/env python3
"""Main CLI entry point for the OLG Lotto Max scraper."""
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import click
import structlog
from rich.console import Console
from rich.table import Table

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.scraper.browser_client import OLGBrowserClient
from src.scraper.parser import LottoMaxParser
from src.scraper.models import ScraperMetadata, LottoMaxDraw
from src.scraper.date_generator import generate_draw_dates, generate_year_draw_dates
from src.storage.json_writer import JSONWriter
from src.storage.csv_writer import CSVWriter

# Initialize console and logger
console = Console()
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()


def parse_date_range(date_range: str) -> tuple[datetime, datetime]:
    """
    Parse date range string into start and end dates.

    Args:
        date_range: Either a predefined range or "YYYY-MM-DD:YYYY-MM-DD"

    Returns:
        Tuple of (start_date, end_date)
    """
    today = datetime.now()

    # Predefined ranges
    if date_range == "last_7_days":
        return today - timedelta(days=7), today
    elif date_range == "last_30_days":
        return today - timedelta(days=30), today
    elif date_range == "last_90_days":
        return today - timedelta(days=90), today
    elif date_range == "year_to_date":
        return datetime(today.year, 1, 1), today
    elif ":" in date_range:
        # Custom range "YYYY-MM-DD:YYYY-MM-DD"
        start_str, end_str = date_range.split(":")
        start_date = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        end_date = datetime.strptime(end_str.strip(), "%Y-%m-%d")
        return start_date, end_date
    else:
        raise ValueError(f"Invalid date range: {date_range}")


@click.command()
@click.option(
    '--draw-date',
    type=str,
    help='Single draw date in YYYY-MM-DD format (e.g., 2025-01-03)'
)
@click.option(
    '--date-range',
    type=str,
    help='Date range in YYYY-MM-DD:YYYY-MM-DD format (e.g., 2025-01-01:2025-01-31)'
)
@click.option(
    '--year',
    type=int,
    help='Scrape all draws from a specific year (e.g., 2025)'
)
@click.option(
    '--format',
    'output_format',
    type=click.Choice(['json', 'csv', 'both']),
    default=settings.output_format,
    help='Output format'
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
    default=settings.log_level,
    help='Logging level'
)
@click.option(
    '--dry-run',
    is_flag=True,
    help='Run without writing output files'
)
@click.option(
    '--headless/--no-headless',
    default=settings.chrome_headless,
    help='Run Chrome in headless mode'
)
def main(
    draw_date: str,
    date_range: str,
    year: int,
    output_format: str,
    log_level: str,
    dry_run: bool,
    headless: bool
):
    """
    OLG Lotto Max Web Scraper.

    Scrapes winning lottery numbers from the OLG website and saves them to JSON/CSV files.
    """
    # Update settings with CLI options
    settings.log_level = log_level
    settings.chrome_headless = headless

    console.print("[bold blue]OLG Lotto Max Scraper[/bold blue]")
    console.print("=" * 50)

    # Determine which dates to scrape
    draw_dates = []
    date_range_start = None
    date_range_end = None

    if year:
        # Scrape entire year
        console.print(f"[cyan]Scraping all draws from year: {year}[/cyan]")
        draw_dates = generate_year_draw_dates(year)
        date_range_start = datetime(year, 1, 1)
        date_range_end = datetime(year, 12, 31)
    elif draw_date:
        # Single draw date
        single_date = datetime.strptime(draw_date, "%Y-%m-%d")
        draw_dates = [single_date]
        date_range_start = single_date
        date_range_end = single_date
        console.print(f"[cyan]Scraping single draw date: {draw_date}[/cyan]")
    elif date_range:
        # Custom date range
        start_str, end_str = date_range.split(":")
        date_range_start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        date_range_end = datetime.strptime(end_str.strip(), "%Y-%m-%d")
        draw_dates = generate_draw_dates(date_range_start, date_range_end)
        console.print(f"[cyan]Date range: {start_str} to {end_str}[/cyan]")
    else:
        # Use default - just scrape current results on page
        date_range_start, date_range_end = parse_date_range(settings.date_range)
        console.print(f"[cyan]Scraping default results (no date iteration)[/cyan]")
        console.print(f"Date range: {settings.date_range}")

    if draw_dates:
        console.print(f"[green]Found {len(draw_dates)} draw dates (Tuesday/Friday)[/green]")

    console.print(f"Output format: {output_format}")
    if dry_run:
        console.print("[yellow]DRY RUN - No files will be written[/yellow]")

    console.print()

    try:
        all_draws: List[LottoMaxDraw] = []

        # Initialize browser client
        console.print("[cyan]Initializing browser...[/cyan]")
        with OLGBrowserClient() as client:
            # Load the page once
            console.print(f"[cyan]Loading page: {settings.target_url}[/cyan]")
            client.load_page()
            client.scroll_to_results()

            if draw_dates:
                # Loop through each draw date and scrape individually
                console.print(f"\n[cyan]Starting date iteration for {len(draw_dates)} dates...[/cyan]\n")

                for idx, draw_date in enumerate(draw_dates, 1):
                    date_str = draw_date.strftime('%Y-%m-%d')
                    console.print(f"[{idx}/{len(draw_dates)}] Scraping {date_str}...", end=" ")

                    # Select the date in the datepicker
                    # This now waits for .play-content to update before returning
                    success = client.interact_with_datepicker(draw_date)

                    if not success:
                        console.print("[yellow]Failed[/yellow]")
                        continue

                    # Wait for results table to be visible
                    client.wait_for_results_table(timeout=10)

                    # Extract the results for this date
                    html_content = client.get_page_source()
                    parser = LottoMaxParser(html_content)
                    date_draws = parser.parse_draws(target_date=draw_date)

                    if date_draws:
                        all_draws.extend(date_draws)
                        console.print(f"[green]✓ Found {len(date_draws)} draw(s)[/green]")
                    else:
                        console.print("[dim]No results[/dim]")

                    # Small delay to be polite to the server
                    import time
                    time.sleep(0.5)

                draws = all_draws
                console.print(f"\n[green]Total draws collected: {len(draws)}[/green]\n")

            else:
                # Default behavior - scrape what's on the page
                console.print("[cyan]Extracting lottery data from current page...[/cyan]")
                client.wait_for_results_table(timeout=20)
                html_content = client.get_page_source()
                parser = LottoMaxParser(html_content)
                draws = parser.parse_draws()

                if not draws:
                    console.print("[yellow]No lottery draws found![/yellow]")
                    return

                console.print(f"[green]Found {len(draws)} lottery draws[/green]")

            # Display summary table
            table = Table(title="Scraped Draws Summary")
            table.add_column("Draw Number", style="cyan")
            table.add_column("Date", style="magenta")
            table.add_column("Winning Numbers", style="green")
            table.add_column("Bonus", style="yellow")

            for draw in draws[:10]:  # Show first 10
                numbers = ", ".join(str(n) for n in draw.winning_numbers)
                table.add_row(
                    str(draw.draw_number),
                    draw.draw_date.strftime("%Y-%m-%d"),
                    numbers,
                    str(draw.bonus_number)
                )

            console.print(table)

            if len(draws) > 10:
                console.print(f"[dim]... and {len(draws) - 10} more[/dim]")

            # Create metadata
            metadata = ScraperMetadata(
                total_draws=len(draws),
                date_range_start=date_range_start or datetime.now(),
                date_range_end=date_range_end or datetime.now()
            )

            # Write output files
            if not dry_run:
                console.print("\n[cyan]Writing output files...[/cyan]")

                if output_format in ['json', 'both']:
                    json_writer = JSONWriter(output_dir=f"{settings.output_dir}/json")
                    json_path = json_writer.write(draws, metadata)
                    console.print(f"[green]✓[/green] JSON file: {json_path}")

                if output_format in ['csv', 'both']:
                    csv_writer = CSVWriter(output_dir=f"{settings.output_dir}/csv")
                    csv_path = csv_writer.write(draws)
                    console.print(f"[green]✓[/green] CSV file: {csv_path}")

            console.print("\n[bold green]Scraping completed successfully![/bold green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Scraping interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        logger.error("scraping_failed", error=str(e), exc_info=True)
        console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
