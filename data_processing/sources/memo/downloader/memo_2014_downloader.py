#!/usr/bin/env python3
"""
MEMO 2014 Downloader

Pass-through downloader for MEMO 2014 data. The data is provided as local ODS files
and must be copied manually to the raw directory.
"""

from pathlib import Path


def get_raw_filename() -> str:
    """Get the filename for the raw ODS file (individual results)."""
    return "individual.ods"


def download_2014(output_dir: Path, force: bool = False) -> Path:
    """
    'Download' MEMO 2014 data (pass-through - expects file to already exist).

    The MEMO 2014 data is not available online and must be provided locally.
    This function just returns the expected path.

    Args:
        output_dir: Directory where raw ODS should be (the 2014 year subdirectory)
        force: Ignored for pass-through downloader

    Returns:
        Path to the expected raw file

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    output_file = output_dir / get_raw_filename()

    if not output_file.exists():
        raise FileNotFoundError(
            f"MEMO 2014 data file not found at {output_file}. "
            f"Please copy the ODS file to this location."
        )

    return output_file
