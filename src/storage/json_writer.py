"""JSON output writer for lottery data."""
import json
from datetime import datetime
from pathlib import Path
from typing import List

import structlog

from src.scraper.models import LottoMaxDraw, ScraperMetadata, ScraperResult

logger = structlog.get_logger()


class JSONWriter:
    """Writer for outputting lottery data to JSON files."""

    def __init__(self, output_dir: str = "./data/json"):
        """
        Initialize JSON writer.

        Args:
            output_dir: Directory to write JSON files to
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("json_writer_initialized", output_dir=str(self.output_dir))

    def write(
        self,
        draws: List[LottoMaxDraw],
        metadata: ScraperMetadata,
        filename: str = None
    ) -> Path:
        """
        Write lottery draws to a JSON file.

        Args:
            draws: List of lottery draws
            metadata: Metadata about the scraping session
            filename: Optional custom filename. If None, generates timestamped name

        Returns:
            Path to the written file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"lotto_max_{timestamp}.json"

        filepath = self.output_dir / filename

        # Create the complete result object
        result = ScraperResult(metadata=metadata, draws=draws)

        try:
            # Write to temporary file first for atomic operation
            temp_filepath = filepath.with_suffix('.tmp')

            with open(temp_filepath, 'w', encoding='utf-8') as f:
                # Use model_dump() to convert to dict, then json.dump for formatting
                data = result.model_dump(mode='json')
                json.dump(data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_filepath.replace(filepath)

            logger.info(
                "json_file_written",
                filepath=str(filepath),
                draws_count=len(draws)
            )
            return filepath

        except Exception as e:
            logger.error("json_write_failed", filepath=str(filepath), error=str(e))
            # Cleanup temporary file if it exists
            if temp_filepath.exists():
                temp_filepath.unlink()
            raise

    def append(
        self,
        new_draws: List[LottoMaxDraw],
        filename: str
    ) -> Path:
        """
        Append new draws to an existing JSON file with deduplication.

        Args:
            new_draws: List of new draws to append
            filename: Name of the existing file

        Returns:
            Path to the updated file
        """
        filepath = self.output_dir / filename

        try:
            # Read existing data
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)

                existing_result = ScraperResult(**existing_data)
                existing_draw_numbers = {draw.draw_number for draw in existing_result.draws}

                # Filter out duplicates
                unique_new_draws = [
                    draw for draw in new_draws
                    if draw.draw_number not in existing_draw_numbers
                ]

                if not unique_new_draws:
                    logger.info("no_new_draws_to_append", filepath=str(filepath))
                    return filepath

                # Combine and sort
                all_draws = existing_result.draws + unique_new_draws
                all_draws.sort(key=lambda d: d.draw_date, reverse=True)

                # Update metadata
                metadata = existing_result.metadata
                metadata.total_draws = len(all_draws)
                metadata.scrape_date = datetime.now()

                # Write updated data
                return self.write(all_draws, metadata, filename)

            else:
                # File doesn't exist, just write new draws
                logger.warning("file_not_found_creating_new", filepath=str(filepath))
                metadata = ScraperMetadata(
                    total_draws=len(new_draws),
                    date_range_start=min(d.draw_date for d in new_draws),
                    date_range_end=max(d.draw_date for d in new_draws)
                )
                return self.write(new_draws, metadata, filename)

        except Exception as e:
            logger.error("json_append_failed", filepath=str(filepath), error=str(e))
            raise
