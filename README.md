# OLG Lotto Max Web Scraper

A Python-based web scraper for collecting Lotto Max winning numbers from the Ontario Lottery and Gaming (OLG) website. Fully containerized with Docker and Selenium for reliable, automated data collection.

## Features

- **Selenium-based scraping**: Handles dynamic JavaScript content
- **Flexible date ranges**: Scrape last 7/30/90 days, year-to-date, or custom ranges
- **Multiple output formats**: JSON and/or CSV
- **Docker containerized**: Consistent environment, easy deployment
- **Data deduplication**: Automatically handles duplicate entries
- **Robust error handling**: Retry logic and structured logging
- **On-demand execution**: Run manually when needed

## Project Structure

```
lotto/
├── src/
│   ├── scraper/          # Core scraping logic
│   │   ├── browser_client.py   # Selenium WebDriver management
│   │   ├── models.py           # Data models
│   │   └── parser.py           # HTML parsing
│   ├── storage/          # Output writers
│   │   ├── json_writer.py
│   │   └── csv_writer.py
│   └── config/           # Configuration
│       └── settings.py
├── scripts/
│   └── run_scraper.py    # CLI entry point
├── data/                 # Output directory
│   ├── json/
│   └── csv/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Prerequisites

- Docker and Docker Compose
- OR Python 3.11+ with Chromium/ChromeDriver (for local development)

## Quick Start

### Using Docker (Recommended)

1. **Build the container:**
   ```bash
   docker-compose build
   ```

2. **Run with default settings (last 30 days):**
   ```bash
   docker-compose run --rm lotto-scraper
   ```

3. **Check the output:**
   ```bash
   ls -lh data/json/
   ls -lh data/csv/
   ```

### Local Development

1. **Create virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt  # For development
   ```

3. **Install Chromium and ChromeDriver:**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install chromium chromium-driver

   # macOS
   brew install chromium chromedriver
   ```

4. **Run the scraper:**
   ```bash
   python scripts/run_scraper.py
   ```

## Usage

### Basic Commands

```bash
# Run with defaults (last 30 days, both JSON and CSV)
docker-compose run --rm lotto-scraper

# Custom date range
docker-compose run --rm lotto-scraper --start-date 2025-01-01 --end-date 2025-12-31

# JSON output only
docker-compose run --rm lotto-scraper --format json

# CSV output only
docker-compose run --rm lotto-scraper --format csv

# Debug mode with visible browser
docker-compose run --rm lotto-scraper --log-level DEBUG --no-headless

# Dry run (no file output)
docker-compose run --rm lotto-scraper --dry-run
```

### CLI Options

```
Options:
  --start-date TEXT              Start date in YYYY-MM-DD format
  --end-date TEXT                End date in YYYY-MM-DD format
  --format [json|csv|both]       Output format (default: both)
  --log-level [DEBUG|INFO|WARNING|ERROR]
                                 Logging level (default: INFO)
  --dry-run                      Run without writing output files
  --headless / --no-headless     Run Chrome in headless mode (default: headless)
  --help                         Show this message and exit
```

## Configuration

### Environment Variables

Create a `.env` file in the project root (see `.env.example`):

```env
# Target URL
TARGET_URL=https://www.olg.ca/en/lottery/play-lotto-max-encore/past-results.html

# Browser Settings
CHROME_HEADLESS=true
PAGE_LOAD_TIMEOUT=30
ELEMENT_WAIT_TIMEOUT=10

# Output Settings
OUTPUT_FORMAT=both  # Options: json, csv, both
OUTPUT_DIR=./data

# Date Range
DATE_RANGE=last_30_days  # Options: last_7_days, last_30_days, last_90_days, year_to_date

# Logging
LOG_LEVEL=INFO  # Options: DEBUG, INFO, WARNING, ERROR

# Retry Settings
MAX_RETRIES=3
RETRY_DELAY=2.0
```

### Predefined Date Ranges

- `last_7_days`: Last 7 days
- `last_30_days`: Last 30 days
- `last_90_days`: Last 90 days
- `year_to_date`: From January 1 to today
- Custom: `YYYY-MM-DD:YYYY-MM-DD` format

## Output Formats

### JSON Output

```json
{
  "metadata": {
    "scrape_date": "2026-01-05T10:00:00Z",
    "total_draws": 150,
    "date_range_start": "2025-01-01T00:00:00",
    "date_range_end": "2026-01-05T00:00:00",
    "errors": []
  },
  "draws": [
    {
      "draw_date": "2026-01-03T00:00:00",
      "draw_number": 1234,
      "winning_numbers": [1, 15, 23, 34, 42, 45, 49],
      "bonus_number": 8,
      "jackpot_amount": "70000000.00",
      "winners": 0
    }
  ]
}
```

### CSV Output

```csv
draw_date,draw_number,num_1,num_2,num_3,num_4,num_5,num_6,num_7,bonus,jackpot,winners
2026-01-03,1234,1,15,23,34,42,45,49,8,70000000.00,0
```

## Development

### Running Tests

```bash
pytest tests/
pytest --cov=src tests/  # With coverage
```

### Code Formatting

```bash
black src/ scripts/ tests/
ruff check src/ scripts/ tests/
```

### Type Checking

```bash
mypy src/
```

## Architecture

### Selenium Browser Client

- Uses headless Chrome for automation
- Implements explicit waits (not sleep) for reliability
- Retry logic with exponential backoff
- Proper cleanup and resource management

### HTML Parser

- BeautifulSoup for HTML parsing
- Pydantic models for data validation
- Handles various date and number formats
- Robust error handling

### Storage Writers

- JSON: Full metadata with structured data
- CSV: Simple format for spreadsheet analysis
- Atomic writes (temp file + rename)
- Automatic deduplication by draw number

## Troubleshooting

### Browser/Chrome Issues

**Error: Chrome binary not found**
```bash
# Update Dockerfile or set environment variable
export CHROME_BIN=/usr/bin/chromium-browser
```

**Error: ChromeDriver version mismatch**
```bash
# Update ChromeDriver in Dockerfile or locally
# Or use webdriver-manager (commented in requirements)
```

### Scraping Issues

**No results found:**
1. Check if the page structure has changed
2. Run with `--no-headless --log-level DEBUG` to see the browser
3. Update HTML selectors in `src/scraper/parser.py`

**Timeout errors:**
```bash
# Increase timeouts
docker-compose run --rm -e PAGE_LOAD_TIMEOUT=60 -e ELEMENT_WAIT_TIMEOUT=20 lotto-scraper
```

### Docker Issues

**Permission denied on data directory:**
```bash
chmod -R 755 data/
```

**Out of disk space:**
```bash
docker system prune
```

## Important Notes

### HTML Selectors

⚠️ **The HTML parser (`src/scraper/parser.py`) contains placeholder selectors** that need to be updated based on the actual OLG page structure. Before first use:

1. Visit https://www.olg.ca/en/lottery/play-lotto-max-encore/past-results.html
2. Inspect the page HTML using browser DevTools
3. Identify the correct CSS selectors/XPath for:
   - Draw date elements
   - Draw number elements
   - Winning number elements
   - Bonus number element
   - Jackpot amount (if available)
4. Update the selectors in `src/scraper/parser.py`

### Date Filter Interaction

The CLI entry point (`scripts/run_scraper.py`) has a TODO comment where date filter interaction needs to be implemented. This requires:

1. Identifying the date filter UI elements (dropdowns, inputs, buttons)
2. Implementing the Selenium interactions to set date ranges
3. Waiting for results to load after applying filters

## Responsible Scraping

- Respect robots.txt
- Implement rate limiting
- Run during off-peak hours if scheduling
- Don't overload the OLG servers
- Cache results to avoid repeated requests

## License

This project is for educational and personal use only. Please respect OLG's terms of service.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run tests and linting
4. Submit a pull request

## Future Enhancements

- [ ] Automatic HTML selector detection
- [ ] Support for other lottery games (Lotto 6/49, Daily Grand, etc.)
- [ ] Database storage option (PostgreSQL, SQLite)
- [ ] REST API for querying results
- [ ] Scheduled runs with cron
- [ ] Web UI for viewing results
- [ ] Statistics and analysis features
- [ ] Email notifications for jackpot milestones

## Contact

For issues, questions, or contributions, please open an issue on the repository.
