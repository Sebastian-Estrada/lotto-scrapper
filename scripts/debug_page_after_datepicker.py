#!/usr/bin/env python3
"""Debug script to see what's on the page after datepicker submission."""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scraper.browser_client import OLGBrowserClient
from src.config.settings import settings

# Use headless=False to see what's happening
settings.chrome_headless = False

target_date = datetime(2025, 1, 3)  # Friday, January 3, 2025

with OLGBrowserClient() as client:
    print(f"Loading page: {settings.target_url}")
    client.load_page()
    client.scroll_to_results()

    print(f"\nSelecting date: {target_date.strftime('%Y-%m-%d')}")
    success = client.interact_with_datepicker(target_date)

    if success:
        print("✓ Datepicker submitted successfully")

        # Wait for page update
        client.wait_for_page_update(timeout=10)
        client.wait_for_results_table(timeout=10)

        # Get the page HTML and save it for inspection
        html = client.get_page_source()

        # Save to file
        output_file = Path(__file__).parent.parent / "debug_page_output.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"\n✓ Page HTML saved to: {output_file}")
        print("\nSearching for dates in the HTML...")

        # Search for date patterns in HTML
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Look for all text that might be dates
        all_text = soup.get_text()
        lines_with_2025 = [line.strip() for line in all_text.split('\n') if '2025' in line or '2026' in line]

        print("\nLines containing dates (2025/2026):")
        for line in lines_with_2025[:20]:  # First 20
            if line:
                print(f"  - {line}")

        # Check what the datepicker field shows
        datepicker_input = soup.find('input', {'id': 'winning-numbers-calendar-picker-startDate'})
        if datepicker_input:
            print(f"\nDatepicker input value: {datepicker_input.get('value')}")

        input("\nPress Enter to close browser...")
    else:
        print("✗ Datepicker submission failed")
