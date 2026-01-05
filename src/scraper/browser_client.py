"""Browser client for interacting with OLG website using Selenium."""
import structlog
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException
)
from tenacity import retry, stop_after_attempt, wait_exponential
from typing import Optional

from src.config.settings import settings

logger = structlog.get_logger()


class OLGBrowserClient:
    """Selenium-based browser client for scraping OLG Lotto Max data."""

    def __init__(self):
        """Initialize the browser client."""
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None

    def __enter__(self):
        """Context manager entry."""
        self.setup_driver()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.close()

    def setup_driver(self) -> None:
        """Initialize Chrome WebDriver with appropriate options."""
        logger.info("setting_up_chrome_driver")

        options = Options()

        # Headless mode for Docker
        if settings.chrome_headless:
            options.add_argument('--headless')

        # Required for Docker/containerized environments
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')

        # Window size for consistent rendering
        options.add_argument('--window-size=1920,1080')

        # Set binary location if specified
        if settings.chrome_binary_location:
            options.binary_location = settings.chrome_binary_location

        # Disable unnecessary features
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')

        # User agent to avoid detection
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        # Create service if driver path is specified
        service = None
        if settings.chromedriver_path:
            service = Service(executable_path=settings.chromedriver_path)

        try:
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)

            self.driver.set_page_load_timeout(settings.page_load_timeout)
            self.wait = WebDriverWait(self.driver, settings.element_wait_timeout)

            logger.info("chrome_driver_initialized")
        except Exception as e:
            logger.error("failed_to_initialize_driver", error=str(e))
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def load_page(self, url: Optional[str] = None) -> None:
        """
        Load the OLG Lotto Max past results page.

        Args:
            url: URL to load. If None, uses settings.target_url
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized. Call setup_driver() first.")

        target = url or settings.target_url
        logger.info("loading_page", url=target)

        try:
            self.driver.get(target)
            logger.info("page_loaded_successfully", url=target)
        except TimeoutException as e:
            logger.error("page_load_timeout", url=target, error=str(e))
            raise
        except Exception as e:
            logger.error("page_load_failed", url=target, error=str(e))
            raise

    def wait_for_element(
        self,
        by: By,
        value: str,
        timeout: Optional[int] = None
    ) -> webdriver.remote.webelement.WebElement:
        """
        Wait for an element to be present on the page.

        Args:
            by: Selenium By locator strategy
            value: Locator value
            timeout: Optional custom timeout

        Returns:
            WebElement when found

        Raises:
            TimeoutException: If element not found within timeout
        """
        wait_time = timeout or settings.element_wait_timeout
        wait = WebDriverWait(self.driver, wait_time)

        try:
            logger.debug("waiting_for_element", by=by, value=value)
            element = wait.until(EC.presence_of_element_located((by, value)))
            logger.debug("element_found", by=by, value=value)
            return element
        except TimeoutException:
            logger.error("element_not_found", by=by, value=value, timeout=wait_time)
            raise

    def wait_for_clickable(
        self,
        by: By,
        value: str,
        timeout: Optional[int] = None
    ) -> webdriver.remote.webelement.WebElement:
        """
        Wait for an element to be clickable.

        Args:
            by: Selenium By locator strategy
            value: Locator value
            timeout: Optional custom timeout

        Returns:
            WebElement when clickable
        """
        wait_time = timeout or settings.element_wait_timeout
        wait = WebDriverWait(self.driver, wait_time)

        try:
            element = wait.until(EC.element_to_be_clickable((by, value)))
            return element
        except TimeoutException:
            logger.error("element_not_clickable", by=by, value=value, timeout=wait_time)
            raise

    def get_page_source(self) -> str:
        """
        Get the current page's HTML source.

        Returns:
            Page source as string
        """
        if not self.driver:
            raise RuntimeError("Driver not initialized.")

        return self.driver.page_source

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        reraise=True
    )
    def click_element(self, by: By, value: str) -> None:
        """
        Click an element with retry logic for stale element references.

        Args:
            by: Selenium By locator strategy
            value: Locator value
        """
        try:
            element = self.wait_for_clickable(by, value)
            element.click()
            logger.debug("element_clicked", by=by, value=value)
        except StaleElementReferenceException:
            logger.warning("stale_element_encountered", by=by, value=value)
            raise
        except Exception as e:
            logger.error("click_failed", by=by, value=value, error=str(e))
            raise

    def interact_with_datepicker(
        self,
        target_draw_date: datetime = None
    ) -> bool:
        """
        Interact with the OLG datepicker to select a specific draw date.

        Args:
            target_draw_date: Specific draw date to select (Tuesday or Friday)

        Returns:
            True if date was selected successfully, False otherwise

        Note:
            The OLG datepicker only allows selecting individual draw dates (Tuesday/Friday),
            not a date range.
        """
        import time

        if not target_draw_date:
            logger.warning("no_target_date_provided")
            return False

        logger.info("interacting_with_datepicker", target_date=target_draw_date.strftime('%Y-%m-%d'))

        try:
            # Wait for the page to fully load
            self.wait.until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # Click the datepicker button
            # Class: "datepicker-button bootstrap3 btn bootstrap olg-web"
            datepicker_selector = ".datepicker-button.bootstrap3.btn.bootstrap.olg-web"

            try:
                datepicker_btn = self.wait_for_clickable(By.CSS_SELECTOR, datepicker_selector, timeout=10)
                logger.info("datepicker_button_found")
                datepicker_btn.click()
                logger.info("datepicker_button_clicked")
                time.sleep(2)  # Wait for calendar to appear
            except (TimeoutException, NoSuchElementException) as e:
                logger.warning("datepicker_button_not_found", selector=datepicker_selector, error=str(e))
                return False

            # OLG Calendar Navigation Flow:
            # 1. Click month/year header ONCE to open month selector
            # 2. Click year header AGAIN to open year selector
            # 3. Click year (cell0=2024, cell1=2025, cell2=2026, etc.)
            # 4. Click month (cell1=Jan, cell2=Feb, ..., cell12=Dec)
            # 5. Click day (cell1-31)

            date_str = target_draw_date.strftime('%Y-%m-%d')
            day = target_draw_date.day
            month = target_draw_date.month  # 1-indexed (1=Jan, 12=Dec)
            year = target_draw_date.year

            try:
                # Step 1: Click on month/year header ONCE to open month selector
                month_year_header = self.wait_for_clickable(
                    By.ID,
                    "datepicker-month-winning-numbers-calendar-picker-startDate",
                    timeout=5
                )
                month_year_header.click()
                logger.info("opened_month_selector")
                time.sleep(1)

                # Step 2: Click on year header AGAIN to open year selector
                year_header = self.wait_for_clickable(
                    By.ID,
                    "datepicker-month-winning-numbers-calendar-picker-startDate",
                    timeout=5
                )
                year_header.click()
                logger.info("opened_year_selector")
                time.sleep(1)

                # Step 3: Select the year
                # Years are in cells: cell0=2024, cell1=2025, cell2=2026, etc.
                # Calculate offset from base year (assuming 2024 is cell0)
                base_year = 2024
                year_offset = year - base_year
                year_cell_id = f"cell{year_offset}-winning-numbers-calendar-picker-startDate"

                year_elem = self.wait_for_clickable(By.ID, year_cell_id, timeout=5)
                year_elem.click()
                logger.info("selected_year", year=year, cell_id=year_cell_id)
                time.sleep(1)

                # Step 4: Select the month
                # Months are 1-indexed: cell1=Jan, cell2=Feb, ..., cell12=Dec
                month_cell_id = f"cell{month}-winning-numbers-calendar-picker-startDate"

                month_elem = self.wait_for_clickable(By.ID, month_cell_id, timeout=5)
                month_elem.click()
                logger.info("selected_month", month=month, cell_id=month_cell_id)
                time.sleep(1)

                # Step 5: Select the day
                day_cell_id = f"cell{day}-winning-numbers-calendar-picker-startDate"

                day_elem = self.wait_for_clickable(By.ID, day_cell_id, timeout=5)
                day_elem.click()
                logger.info("selected_day", day=day, date=date_str, cell_id=day_cell_id)

                # Blur focus from calendar to prevent hover effects from overlaying submit button
                self.driver.execute_script("document.activeElement.blur();")

                time.sleep(2)  # Increased wait to allow calendar animations to complete

            except (TimeoutException, NoSuchElementException) as e:
                logger.warning("calendar_navigation_failed", date=date_str, error=str(e))
                # Try to close the calendar
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                except Exception:
                    pass
                return False

            # Capture reference to play-content BEFORE submitting
            # This will be used to detect when content updates
            old_content_element = None
            try:
                play_content = self.driver.find_element(By.CLASS_NAME, "play-content")
                old_content_element = play_content.find_element(By.CSS_SELECTOR, ".ball-list, div, p")
                logger.info("captured_content_reference_before_submit")
            except NoSuchElementException:
                logger.warning("could_not_capture_content_reference")

            # Click the apply/submit button
            # Button ID: winning-numbers-calendar-picker-submit
            submit_selectors = [
                (By.ID, "winning-numbers-calendar-picker-submit"),  # Primary - it's an ID!
                (By.CSS_SELECTOR, "#winning-numbers-calendar-picker-submit"),
                (By.CLASS_NAME, "winning-numbers-calendar-picker-submit"),
                (By.XPATH, "//button[@id='winning-numbers-calendar-picker-submit']"),
                (By.XPATH, "//button[contains(text(), 'Apply')]"),
                (By.XPATH, "//button[contains(text(), 'Submit')]"),
            ]

            submit_clicked = False
            for by, selector in submit_selectors:
                try:
                    submit_btn = self.wait_for_clickable(by, selector, timeout=3)

                    # Scroll button into center of viewport to avoid overlapping elements
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                        submit_btn
                    )
                    time.sleep(0.5)  # Wait for scroll to complete

                    # Use JavaScript click directly (standard click always fails due to overlays)
                    self.driver.execute_script("arguments[0].click();", submit_btn)
                    logger.info("calendar_picker_submitted", date=date_str, selector=selector)

                    # Wait for the .play-content div to update
                    if old_content_element:
                        try:
                            # Wait for the old element to become stale (content updated)
                            WebDriverWait(self.driver, 15).until(EC.staleness_of(old_content_element))
                            logger.info("play_content_updated_detected")
                            time.sleep(2)  # Additional time for rendering
                        except TimeoutException:
                            logger.warning("play_content_did_not_update", timeout=15)
                            time.sleep(3)  # Fallback wait
                    else:
                        # Fallback if we couldn't capture reference
                        time.sleep(5)

                    submit_clicked = True
                    break
                except (TimeoutException, NoSuchElementException):
                    continue

            if not submit_clicked:
                logger.warning("submit_button_not_found_all_selectors")
                # Try to close the picker by clicking elsewhere
                try:
                    self.driver.find_element(By.TAG_NAME, "body").click()
                except Exception:
                    pass
                return False

            return True

        except Exception as e:
            logger.error("datepicker_interaction_failed", error=str(e))
            return False

    def wait_for_content_update(self, timeout: int = 15) -> bool:
        """
        Wait for the .play-content div to update after datepicker submission.
        Uses staleness detection to know when content has changed.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if content updated, False otherwise
        """
        import time
        from selenium.common.exceptions import StaleElementReferenceException

        logger.info("waiting_for_content_update")

        try:
            # Get reference to an element inside .play-content before it updates
            play_content = self.driver.find_element(By.CLASS_NAME, "play-content")

            # Get a child element to watch for staleness
            # Try to find any element inside that we can track
            old_element = None
            try:
                old_element = play_content.find_element(By.CSS_SELECTOR, ".ball-list, div, p")
            except NoSuchElementException:
                # If we can't find a child element, just use the parent
                old_element = play_content

            if old_element:
                logger.info("tracking_element_for_staleness")

                # Wait for the element to become stale (meaning DOM was updated)
                try:
                    WebDriverWait(self.driver, timeout).until(
                        EC.staleness_of(old_element)
                    )
                    logger.info("content_updated_detected_via_staleness")

                    # Give it a moment to fully render
                    time.sleep(2)
                    return True

                except TimeoutException:
                    logger.warning("content_did_not_become_stale", timeout=timeout)
                    # Content might not have changed, but continue anyway
                    time.sleep(2)
                    return False

        except NoSuchElementException:
            logger.warning("play_content_div_not_found")
            # Fall back to simple wait
            time.sleep(3)
            return False

        except Exception as e:
            logger.error("content_update_wait_failed", error=str(e))
            time.sleep(3)
            return False

    def wait_for_results_table(self, timeout: int = 15) -> bool:
        """
        Wait for the results table/container to be loaded and visible.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if results are found, False otherwise
        """
        logger.info("waiting_for_results_table")

        # Selectors for OLG lottery results
        # Primary: ul with class "ball-list" (contains the winning numbers)
        result_selectors = [
            (By.CLASS_NAME, "ball-list"),  # Primary selector for OLG
            (By.CLASS_NAME, "lotto-balls"),  # Alternative
            (By.CLASS_NAME, "past-results"),
            (By.CLASS_NAME, "results-table"),
            (By.TAG_NAME, "table"),  # Fallback
        ]

        wait = WebDriverWait(self.driver, timeout)

        for by, selector in result_selectors:
            try:
                element = wait.until(EC.presence_of_element_located((by, selector)))
                if element:
                    logger.info("results_table_found", selector=selector)
                    # Additional wait for content to populate
                    import time
                    time.sleep(2)
                    return True
            except TimeoutException:
                continue

        logger.warning("results_table_not_found_using_timeout")
        return False

    def scroll_to_results(self) -> None:
        """Scroll to the results section if needed."""
        try:
            # Try to find and scroll to results anchor
            anchors = [
                "pastResultsHeader",
                "past-results",
                "results",
            ]

            for anchor_id in anchors:
                try:
                    element = self.driver.find_element(By.ID, anchor_id)
                    if element:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        logger.info("scrolled_to_results", anchor=anchor_id)
                        import time
                        time.sleep(1)
                        return
                except NoSuchElementException:
                    continue

            logger.debug("no_scroll_anchor_found")
        except Exception as e:
            logger.error("scroll_failed", error=str(e))

    def load_more_results(self, max_clicks: int = 50) -> int:
        """
        Click "Load More" or "Show More" button repeatedly to load all results.

        Args:
            max_clicks: Maximum number of times to click (safety limit)

        Returns:
            Number of times the button was clicked
        """
        import time

        clicks = 0
        logger.info("attempting_to_load_more_results", max_clicks=max_clicks)

        # Common selectors for "Load More" buttons
        load_more_selectors = [
            (By.CLASS_NAME, "load-more"),
            (By.CLASS_NAME, "show-more"),
            (By.CSS_SELECTOR, "button[class*='load-more']"),
            (By.CSS_SELECTOR, "button[class*='show-more']"),
            (By.CSS_SELECTOR, "a[class*='load-more']"),
            (By.XPATH, "//button[contains(text(), 'Load More')]"),
            (By.XPATH, "//button[contains(text(), 'Show More')]"),
            (By.XPATH, "//a[contains(text(), 'Load More')]"),
        ]

        while clicks < max_clicks:
            button_found = False

            for by, selector in load_more_selectors:
                try:
                    # Try to find the button
                    button = self.driver.find_element(by, selector)

                    # Check if button is visible and enabled
                    if button.is_displayed() and button.is_enabled():
                        # Scroll to button
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", button)
                        time.sleep(0.5)

                        # Click it
                        button.click()
                        clicks += 1
                        button_found = True
                        logger.info("clicked_load_more", clicks=clicks)

                        # Wait for new content to load
                        time.sleep(2)
                        break

                except (NoSuchElementException, Exception):
                    continue

            if not button_found:
                logger.info("no_more_load_more_button", total_clicks=clicks)
                break

        logger.info("load_more_completed", total_clicks=clicks)
        return clicks

    def scroll_to_load_infinite(self, scroll_pause_time: float = 2.0, max_scrolls: int = 50) -> int:
        """
        Scroll down to trigger infinite scroll loading.

        Args:
            scroll_pause_time: Time to wait after each scroll
            max_scrolls: Maximum number of scrolls (safety limit)

        Returns:
            Number of scrolls performed
        """
        import time

        logger.info("attempting_infinite_scroll", max_scrolls=max_scrolls)

        last_height = self.driver.execute_script("return document.body.scrollHeight")
        scrolls = 0

        while scrolls < max_scrolls:
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            scrolls += 1

            # Wait for content to load
            time.sleep(scroll_pause_time)

            # Check if new content loaded
            new_height = self.driver.execute_script("return document.body.scrollHeight")

            if new_height == last_height:
                # No more content
                logger.info("reached_end_of_page", scrolls=scrolls)
                break

            last_height = new_height
            logger.debug("scrolled", scrolls=scrolls, height=new_height)

        logger.info("infinite_scroll_completed", total_scrolls=scrolls)
        return scrolls

    def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self.driver:
            logger.info("closing_browser")
            try:
                self.driver.quit()
                logger.info("browser_closed")
            except Exception as e:
                logger.error("error_closing_browser", error=str(e))
            finally:
                self.driver = None
                self.wait = None
