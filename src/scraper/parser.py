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

    def parse_draws(self, target_date: Optional[datetime] = None) -> List[LottoMaxDraw]:
        """
        Parse all lottery draws from the HTML.

        Args:
            target_date: Optional date to filter draws by (only return draws matching this date)

        Returns:
            List of LottoMaxDraw objects

        Note:
            The exact implementation depends on the HTML structure of the OLG page.
            This is a template that will need to be adjusted based on actual page structure.
        """
        draws = []
        logger.info("starting_draw_parsing", target_date=target_date.strftime('%Y-%m-%d') if target_date else None)

        try:
            # Find all winning numbers ball lists for Lotto Max
            # Full classes: "extra-bottom theme-default lotto-balls remove-default-styles ball-list not-daily-grand"
            # Use CSS selector to require ALL classes (not just any)
            ball_lists = self.soup.select('ul.ball-list.lotto-balls.not-daily-grand')

            if not ball_lists:
                logger.warning("no_ball_lists_found")
                return draws

            logger.info("found_ball_lists", count=len(ball_lists))

            # Each ball list represents one draw
            for ball_list in ball_lists:
                try:
                    draw = self._parse_single_draw(ball_list, target_date)
                    if draw:
                        draws.append(draw)
                except Exception as e:
                    logger.error(
                        "failed_to_parse_draw",
                        ball_list=str(ball_list)[:200],
                        error=str(e)
                    )
                    continue

            logger.info("draw_parsing_completed", total_draws=len(draws))

            # Filter by target date if provided
            if target_date and draws:
                target_date_only = target_date.date()
                filtered_draws = [d for d in draws if d.draw_date.date() == target_date_only]

                if filtered_draws:
                    logger.info("filtered_draws_by_date",
                               requested=len(filtered_draws),
                               total=len(draws),
                               target_date=target_date.strftime('%Y-%m-%d'))
                    return filtered_draws
                else:
                    logger.warning("no_draws_match_target_date",
                                 target_date=target_date.strftime('%Y-%m-%d'),
                                 available_dates=[d.draw_date.strftime('%Y-%m-%d') for d in draws])

            return draws

        except Exception as e:
            logger.error("draw_parsing_failed", error=str(e))
            raise

    def _parse_single_draw(self, ball_list, target_date: Optional[datetime] = None) -> Optional[LottoMaxDraw]:
        """
        Parse a single draw from a ball list element.

        Args:
            ball_list: BeautifulSoup ul element with class 'ball-list'
            target_date: The date we requested (from datepicker) - use this instead of parsing

        Returns:
            LottoMaxDraw object or None if parsing fails
        """
        try:
            # Use the target_date we already know (from datepicker selection)
            # No need to parse it from the page since we selected it
            draw_date = target_date or datetime.now()

            # Generate draw_number from the date (timestamp)
            draw_number = int(draw_date.timestamp())

            logger.info("using_provided_date", date=draw_date.strftime('%Y-%m-%d'), draw_number=draw_number)

            # Extract winning numbers from regular balls (not special-ball)
            # Class: "ball-number" (but exclude those in "special-ball" li)
            winning_numbers = []

            # Find all li elements that are NOT special-ball
            regular_balls = [li for li in ball_list.find_all('li') if 'special-ball' not in (li.get('class') or [])]

            for li in regular_balls:
                ball_number_elem = li.find(class_='ball-number')
                if ball_number_elem:
                    try:
                        num = int(ball_number_elem.text.strip())
                        winning_numbers.append(num)
                    except (ValueError, AttributeError) as e:
                        logger.warning("failed_to_parse_ball_number", text=ball_number_elem.text, error=str(e))
            logger.info("extracted_winning_numbers", numbers=winning_numbers)
            # Extract bonus number from special-ball
            # Class: li with "special-ball", value in "ball-number"
            bonus_number = None
            special_ball = ball_list.find('li', class_='special-ball')

            if special_ball:
                bonus_elem = special_ball.find(class_='ball-number')
                if bonus_elem:
                    try:
                        bonus_number = int(bonus_elem.text.strip())
                    except (ValueError, AttributeError) as e:
                        logger.warning("failed_to_parse_bonus_number", text=bonus_elem.text, error=str(e))

            # Extract encore numbers (optional - not part of LottoMaxDraw but we can log them)
            encore_numbers = []
            encore_elems = ball_list.find_all(class_='encore-number')
            for encore_elem in encore_elems:
                try:
                    encore_numbers.append(encore_elem.text.strip())
                except Exception:
                    pass

            if encore_numbers:
                logger.debug("found_encore_numbers", encore=encore_numbers)

            # Validate we have minimum required data
            if len(winning_numbers) != 7:
                logger.warning(
                    "incorrect_winning_numbers_count",
                    count=len(winning_numbers),
                    numbers=winning_numbers
                )
                return None

            if not bonus_number:
                logger.warning("no_bonus_number_found")
                return None

            # Create and validate the draw object
            draw = LottoMaxDraw(
                draw_date=draw_date,
                draw_number=draw_number,
                winning_numbers=winning_numbers,
                bonus_number=bonus_number,
                jackpot_amount=None  # Not extracted yet
            )

            logger.debug(
                "draw_parsed_successfully",
                draw_number=draw_number,
                date=draw_date.strftime('%Y-%m-%d') if draw_date else None,
                winning_numbers=winning_numbers,
                bonus=bonus_number
            )
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
        # Strip all whitespace and newlines
        date_str = date_str.strip()

        # Common date formats on Canadian sites
        formats = [
            "%A, %B %d, %Y",  # Friday, January 02, 2026
            "%B %d, %Y",      # January 05, 2026
            "%b %d, %Y",      # Jan 05, 2026
            "%Y-%m-%d",       # 2026-01-05 (ISO format - OLG uses this)
            "%m/%d/%Y",       # 01/05/2026
            "%d/%m/%Y",       # 05/01/2026
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
