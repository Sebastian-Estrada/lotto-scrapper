"""HTML parser for extracting Lotto Max draw data from OLG pages."""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import structlog
from bs4 import BeautifulSoup
from pydantic import ValidationError

from src.scraper.models import LottoMaxDraw

logger = structlog.get_logger()


class LottoMaxParser:
    """Parser for extracting Lotto Max data from HTML."""

    def __init__(self, html_content: str):
        """
        Initialize the parser with HTML content.

        Args:
            html_content: Raw HTML string
        """
        self.soup = BeautifulSoup(html_content, 'lxml')
        logger.debug("parser_initialized")

    def parse_draws(self) -> List[LottoMaxDraw]:
        """
        Parse all lottery draws from the HTML.

        Returns:
            List of LottoMaxDraw objects

        Note:
            The exact implementation depends on the HTML structure of the OLG page.
            This is a template that will need to be adjusted based on actual page structure.
        """
        draws = []
        logger.info("starting_draw_parsing")

        # TODO: Identify actual HTML selectors from the OLG page
        # These are placeholder selectors that need to be updated
        # after inspecting the actual page structure

        try:
            # Example: Find all draw result containers
            # This selector needs to be updated based on actual page structure
            draw_containers = self.soup.find_all('div', class_='draw-result')

            if not draw_containers:
                logger.warning("no_draw_containers_found")
                # Try alternative selectors
                draw_containers = self.soup.find_all('tr', class_='result-row')

            for container in draw_containers:
                try:
                    draw = self._parse_single_draw(container)
                    if draw:
                        draws.append(draw)
                except Exception as e:
                    logger.error(
                        "failed_to_parse_draw",
                        container=str(container)[:200],
                        error=str(e)
                    )
                    continue

            logger.info("draw_parsing_completed", total_draws=len(draws))
            return draws

        except Exception as e:
            logger.error("draw_parsing_failed", error=str(e))
            raise

    def _parse_single_draw(self, container) -> Optional[LottoMaxDraw]:
        """
        Parse a single draw from its HTML container.

        Args:
            container: BeautifulSoup element containing a single draw

        Returns:
            LottoMaxDraw object or None if parsing fails

        Note:
            This method contains placeholder logic and needs to be updated
            based on the actual HTML structure of the OLG page.
        """
        try:
            # Example structure - needs to be updated based on actual page
            # The selectors below are placeholders

            # Extract draw date
            date_elem = container.find('span', class_='draw-date')
            if not date_elem:
                date_elem = container.find('td', class_='date')

            draw_date = self._parse_date(date_elem.text.strip()) if date_elem else None

            # Extract draw number
            number_elem = container.find('span', class_='draw-number')
            draw_number = int(number_elem.text.strip()) if number_elem else None

            # Extract winning numbers
            number_elems = container.find_all('span', class_='winning-number')
            if not number_elems:
                number_elems = container.find_all('td', class_='number')

            winning_numbers = []
            for elem in number_elems[:7]:  # First 7 are winning numbers
                try:
                    num = int(elem.text.strip())
                    winning_numbers.append(num)
                except (ValueError, AttributeError):
                    continue

            # Extract bonus number
            bonus_elem = container.find('span', class_='bonus-number')
            if not bonus_elem and len(number_elems) > 7:
                bonus_elem = number_elems[7]  # 8th number is bonus

            bonus_number = None
            if bonus_elem:
                try:
                    bonus_number = int(bonus_elem.text.strip())
                except (ValueError, AttributeError):
                    pass

            # Extract jackpot (optional)
            jackpot_elem = container.find('span', class_='jackpot')
            jackpot_amount = None
            if jackpot_elem:
                jackpot_amount = self._parse_money(jackpot_elem.text.strip())

            # Validate we have minimum required data
            if not all([draw_date, draw_number, len(winning_numbers) == 7, bonus_number]):
                logger.warning(
                    "incomplete_draw_data",
                    date=draw_date,
                    number=draw_number,
                    winning_count=len(winning_numbers)
                )
                return None

            # Create and validate the draw object
            draw = LottoMaxDraw(
                draw_date=draw_date,
                draw_number=draw_number,
                winning_numbers=winning_numbers,
                bonus_number=bonus_number,
                jackpot_amount=jackpot_amount
            )

            logger.debug("draw_parsed", draw_number=draw_number, date=draw_date)
            return draw

        except ValidationError as e:
            logger.error("draw_validation_failed", error=str(e))
            return None
        except Exception as e:
            logger.error("unexpected_parsing_error", error=str(e))
            return None

    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """
        Parse date string to datetime object.

        Args:
            date_str: Date string in various formats

        Returns:
            datetime object

        Note:
            May need to handle multiple date formats from the OLG site
        """
        # Common date formats on Canadian sites
        formats = [
            "%B %d, %Y",  # January 05, 2026
            "%b %d, %Y",  # Jan 05, 2026
            "%Y-%m-%d",   # 2026-01-05
            "%m/%d/%Y",   # 01/05/2026
            "%d/%m/%Y",   # 05/01/2026
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {date_str}")

    @staticmethod
    def _parse_money(money_str: str) -> Optional[Decimal]:
        """
        Parse money string to Decimal.

        Args:
            money_str: Money string like "$70,000,000" or "70000000"

        Returns:
            Decimal amount or None if parsing fails
        """
        try:
            # Remove currency symbols, commas, and spaces
            cleaned = money_str.replace('$', '').replace(',', '').replace(' ', '').strip()
            return Decimal(cleaned)
        except (ValueError, decimal.InvalidOperation):
            logger.warning("failed_to_parse_money", value=money_str)
            return None
