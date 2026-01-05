#!/usr/bin/env python3
"""Debug script to inspect the OLG page structure and save HTML for analysis."""
import sys
from pathlib import Path
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import settings
from src.scraper.browser_client import OLGBrowserClient

# Force non-headless mode for debugging
settings.chrome_headless = False


def main():
    """
    Run browser in visible mode to inspect page structure.
    Saves the page HTML for offline analysis.
    """
    print("=" * 60)
    print("OLG Page Structure Debugger")
    print("=" * 60)
    print()
    print("This will open a visible Chrome browser.")
    print("You can manually interact with the page to see how it works.")
    print()
    print("Actions to take:")
    print("1. Wait for the page to fully load")
    print("2. Scroll to the past results section")
    print("3. Try clicking the datepicker button")
    print("4. Right-click on lottery numbers and 'Inspect Element'")
    print("5. Note the CSS classes and structure")
    print()
    input("Press Enter to start...")

    try:
        with OLGBrowserClient() as client:
            print("\n[1/5] Loading page...")
            client.load_page()

            print("[2/5] Scrolling to results...")
            client.scroll_to_results()

            print("[3/5] Waiting for results table...")
            found = client.wait_for_results_table(timeout=20)
            if found:
                print("    ✓ Results table detected")
            else:
                print("    ⚠ Results table not detected (may need manual scrolling)")

            # Save initial HTML
            html = client.get_page_source()
            output_path = Path(__file__).parent.parent / "tests" / "fixtures" / "olg_page_raw.html"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)

            print(f"\n[4/5] HTML saved to: {output_path}")
            print()
            print("=" * 60)
            print("BROWSER INSPECTION TIME")
            print("=" * 60)
            print()
            print("The browser will stay open for 2 minutes.")
            print("Use this time to:")
            print()
            print("1. Open Chrome DevTools (F12 or right-click > Inspect)")
            print("2. Find the lottery numbers in the HTML")
            print("3. Note down:")
            print("   - Container element (table, div, ul?)")
            print("   - Row element selector")
            print("   - Date element selector")
            print("   - Number element selectors")
            print("   - Bonus number selector")
            print()
            print("Look for patterns like:")
            print("   - class='draw-result'")
            print("   - class='winning-number'")
            print("   - class='bonus'")
            print("   - data-draw-number='...'")
            print()
            print("You can also interact with the datepicker to see how it works.")
            print()

            # Keep browser open for inspection
            for remaining in range(120, 0, -10):
                print(f"\rBrowser will close in {remaining} seconds... ", end='', flush=True)
                time.sleep(10)

            print("\n\n[5/5] Saving final HTML after any interactions...")

            # Save HTML again after user interactions
            html_after = client.get_page_source()
            output_path_after = Path(__file__).parent.parent / "tests" / "fixtures" / "olg_page_after_interaction.html"

            with open(output_path_after, 'w', encoding='utf-8') as f:
                f.write(html_after)

            print(f"Final HTML saved to: {output_path_after}")

            print("\n" + "=" * 60)
            print("Next Steps:")
            print("=" * 60)
            print()
            print("1. Open the saved HTML files in a text editor")
            print(f"   - {output_path}")
            print(f"   - {output_path_after}")
            print()
            print("2. Search for lottery numbers (e.g., search for recent draw dates)")
            print()
            print("3. Update src/scraper/parser.py with the correct selectors")
            print()
            print("4. Run the actual scraper with:")
            print("   docker-compose run --rm lotto-scraper --dry-run")
            print()

    except KeyboardInterrupt:
        print("\n\nDebug session interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
