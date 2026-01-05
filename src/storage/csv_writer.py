"""CSV output writer for lottery data."""
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import structlog

from src.scraper.models import LottoMaxDraw

logger = structlog.get_logger()


class CSVWriter:
    """Writer for outputting lottery data to CSV files."""

    def __init__(self, output_dir: str = "./data/csv"):
        """
        Initialize CSV writer.

        Args:
            output_dir: Directory to write CSV files to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("csv_writer_initialized", output_dir=str(self.output_dir))

    def write(
        self,
        draws: List[LottoMaxDraw],
        filename: str = None
    ) -> Path:
        """
        Write lottery draws to a CSV file.

        Args:
            draws: List of lottery draws
            filename: Optional custom filename. If None, generates timestamped name

        Returns:
            Path to the written file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"lotto_max_{timestamp}.csv"

        filepath = self.output_dir / filename

        try:
            # Convert draws to a list of dictionaries
            rows = []
            for draw in draws:
                row = {
                    'draw_date': draw.draw_date.strftime('%Y-%m-%d'),
                    'draw_number': draw.draw_number,
                }

                # Add individual winning numbers as separate columns
                for i, num in enumerate(draw.winning_numbers, 1):
                    row[f'num_{i}'] = num

                row['bonus'] = draw.bonus_number

                # Add optional fields
                if draw.jackpot_amount is not None:
                    row['jackpot'] = str(draw.jackpot_amount)
                else:
                    row['jackpot'] = ''

                if draw.winners is not None:
                    row['winners'] = draw.winners
                else:
                    row['winners'] = ''

                rows.append(row)

            # Create DataFrame
            df = pd.DataFrame(rows)

            # Sort by date descending
            df = df.sort_values('draw_date', ascending=False)

            # Write to temporary file first for atomic operation
            temp_filepath = filepath.with_suffix('.tmp')
            df.to_csv(temp_filepath, index=False)

            # Atomic rename
            temp_filepath.replace(filepath)

            logger.info(
                "csv_file_written",
                filepath=str(filepath),
                draws_count=len(draws)
            )
            return filepath

        except Exception as e:
            logger.error("csv_write_failed", filepath=str(filepath), error=str(e))
            # Cleanup temporary file if it exists
            if 'temp_filepath' in locals() and temp_filepath.exists():
                temp_filepath.unlink()
            raise

    def append(
        self,
        new_draws: List[LottoMaxDraw],
        filename: str
    ) -> Path:
        """
        Append new draws to an existing CSV file with deduplication.

        Args:
            new_draws: List of new draws to append
            filename: Name of the existing file

        Returns:
            Path to the updated file
        """
        filepath = self.output_dir / filename

        try:
            if filepath.exists():
                # Read existing data
                existing_df = pd.read_csv(filepath)
                existing_draw_numbers = set(existing_df['draw_number'].values)

                # Filter out duplicates
                unique_new_draws = [
                    draw for draw in new_draws
                    if draw.draw_number not in existing_draw_numbers
                ]

                if not unique_new_draws:
                    logger.info("no_new_draws_to_append", filepath=str(filepath))
                    return filepath

                # Write all draws (existing + new)
                all_draws = self._csv_to_draws(existing_df) + unique_new_draws
                return self.write(all_draws, filename)

            else:
                # File doesn't exist, just write new draws
                logger.warning("file_not_found_creating_new", filepath=str(filepath))
                return self.write(new_draws, filename)

        except Exception as e:
            logger.error("csv_append_failed", filepath=str(filepath), error=str(e))
            raise

    @staticmethod
    def _csv_to_draws(df: pd.DataFrame) -> List[LottoMaxDraw]:
        """
        Convert a DataFrame back to LottoMaxDraw objects.

        Args:
            df: DataFrame with lottery data

        Returns:
            List of LottoMaxDraw objects
        """
        draws = []
        for _, row in df.iterrows():
            winning_numbers = [
                int(row[f'num_{i}']) for i in range(1, 8)
            ]

            jackpot = None
            if row['jackpot'] and str(row['jackpot']).strip():
                from decimal import Decimal
                jackpot = Decimal(str(row['jackpot']))

            winners = None
            if row['winners'] and str(row['winners']).strip():
                winners = int(row['winners'])

            draw = LottoMaxDraw(
                draw_date=pd.to_datetime(row['draw_date']),
                draw_number=int(row['draw_number']),
                winning_numbers=winning_numbers,
                bonus_number=int(row['bonus']),
                jackpot_amount=jackpot,
                winners=winners
            )
            draws.append(draw)

        return draws
