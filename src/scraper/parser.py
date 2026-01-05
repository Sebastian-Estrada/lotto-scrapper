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
            # Find all winning numbers ball lists
            # Class: "extra-bottom theme-default lotto-balls remove-default-styles ball-list not-daily-grand"
            ball_lists = self.soup.find_all('ul', class_='ball-list')

            if not ball_lists:
                logger.warning("no_ball_lists_found")
                return draws

            logger.info("found_ball_lists", count=len(ball_lists))

            # Each ball list represents one draw
            for ball_list in ball_lists:
                try:
                    draw = self._parse_single_draw(ball_list)
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

    def _parse_single_draw(self, ball_list) -> Optional[LottoMaxDraw]:
        """
        Parse a single draw from a ball list element.

        Args:
            ball_list: BeautifulSoup ul element with class 'ball-list'

        Returns:
            LottoMaxDraw object or None if parsing fails
        """
        try:
            # Find the parent container to get draw date and number
            # Navigate up to find the draw information
            draw_container = ball_list.find_parent()

            # Extract draw date - look for date in parent elements
            draw_date = None
            date_elem = None

            # Try to find date in siblings or parent elements
            for parent in [ball_list.parent, ball_list.parent.parent if ball_list.parent else None]:
                if parent:
                    # Look for common date patterns
                    date_elem = (
                        parent.find('span', class_='draw-date') or
                        parent.find('div', class_='date') or
                        parent.find('time') or
                        parent.find(class_=lambda x: x and 'date' in x.lower() if x else False)
                    )
                    if date_elem:
                        break

            if date_elem:
                try:
                    draw_date = self._parse_date(date_elem.text.strip())
                except Exception as e:
                    logger.warning("failed_to_parse_date", text=date_elem.text, error=str(e))

            # Extract draw number - if available in the structure
            draw_number = None
            number_elem = None

            for parent in [ball_list.parent, ball_list.parent.parent if ball_list.parent else None]:
                if parent:
                    number_elem = (
                        parent.find('span', class_='draw-number') or
                        parent.find(class_=lambda x: x and 'draw-number' in x.lower() if x else False) or
                        parent.find(attrs={'data-draw-number': True})
                    )
                    if number_elem:
                        break

            if number_elem:
                try:
                    # Try to get from text or data attribute
                    draw_number_text = number_elem.get('data-draw-number') or number_elem.text.strip()
                    draw_number = int(''.join(filter(str.isdigit, draw_number_text)))
                except Exception as e:
                    logger.warning("failed_to_parse_draw_number", error=str(e))

            # If we don't have draw_number, generate one from date
            if not draw_number and draw_date:
                # Use timestamp as draw number (temporary solution)
                draw_number = int(draw_date.timestamp())

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

            if not draw_date:
                logger.warning("no_draw_date_found")
                # Try to use current date as fallback
                from datetime import datetime
                draw_date = datetime.now()

            if not draw_number:
                logger.warning("no_draw_number_found")
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
