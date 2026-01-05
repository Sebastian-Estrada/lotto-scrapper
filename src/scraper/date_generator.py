"""Generate Lotto Max draw dates (Tuesday and Friday)."""
from datetime import datetime, timedelta
from typing import List


def generate_draw_dates(start_date: datetime, end_date: datetime) -> List[datetime]:
    """
    Generate all Lotto Max draw dates (Tuesday and Friday) in a date range.

    Args:
        start_date: Start of the date range
        end_date: End of the date range

    Returns:
        List of datetime objects for all draw dates (Tuesday=1, Friday=4)
    """
    draw_dates = []
    current_date = start_date

    # Days of the week: Monday=0, Tuesday=1, Wednesday=2, Thursday=3, Friday=4, Saturday=5, Sunday=6
    draw_weekdays = [1, 4]  # Tuesday and Friday

    while current_date <= end_date:
        if current_date.weekday() in draw_weekdays:
            draw_dates.append(current_date)
        current_date += timedelta(days=1)

    return draw_dates


def generate_year_draw_dates(year: int) -> List[datetime]:
    """
    Generate all draw dates for a specific year.

    Args:
        year: Year to generate dates for

    Returns:
        List of all Tuesday and Friday dates in that year
    """
    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31)
    return generate_draw_dates(start_date, end_date)
