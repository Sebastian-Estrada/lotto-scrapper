"""Browser client for interacting with OLG website using Selenium."""
import structlog
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
