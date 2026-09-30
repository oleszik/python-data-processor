"""File loading and exporting for supported tabular formats."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from data_processor.errors import InputFileError, UnsupportedFormatError

SUPPORTED_FORMATS = {".csv", ".xlsx"}


def _validate_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        supported = ", ".join(sorted(SUPPORTED_FORMATS))
        raise UnsupportedFormatError(
            f"Unsupported file format '{path.suffix or '(no extension)'}'. "
            f"Supported formats: {supported}."
        )
    return suffix


def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load a CSV or XLSX file, selecting its reader from the extension."""
    source = Path(path)
    if source.exists() and not source.is_file():
        raise InputFileError(f"Input path is not a file: {source}")
    file_format = _validate_format(source)
    if not source.exists():
        raise InputFileError(f"Input file does not exist: {source}")

    try:
        if file_format == ".csv":
            return pd.read_csv(source)
        return pd.read_excel(source, engine="openpyxl")
    except Exception as exc:
        raise InputFileError(f"Could not read input file '{source}': {exc}") from exc


def load_csv_chunks(path: str | Path, chunksize: int) -> Iterator[pd.DataFrame]:
    """Return an iterator that loads a CSV file in bounded-size chunks."""
    source = Path(path)
    if source.exists() and not source.is_file():
        raise InputFileError(f"Input path is not a file: {source}")
    if _validate_format(source) != ".csv":
        raise UnsupportedFormatError(
            "Chunked processing is only supported for CSV files."
        )
    if not source.exists():
        raise InputFileError(f"Input file does not exist: {source}")
    try:
        reader = pd.read_csv(source, chunksize=chunksize)
        found_chunk = False
        for chunk in reader:
            found_chunk = True
            yield chunk
        if not found_chunk:
            yield pd.read_csv(source, nrows=0)
    except (
        OSError,
        ValueError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ) as exc:
        raise InputFileError(f"Could not read input file '{source}': {exc}") from exc


def export_dataset(dataframe: pd.DataFrame, path: str | Path) -> Path:
    """Write a dataframe as CSV or XLSX based on the output extension."""
    destination = Path(path)
    file_format = _validate_format(destination)
    try:
        if file_format == ".csv":
            dataframe.to_csv(destination, index=False)
        else:
            dataframe.to_excel(destination, index=False, engine="openpyxl")
    except (OSError, ValueError) as exc:
        message = f"Could not write output file '{destination}': {exc}"
        raise InputFileError(message) from exc
    return destination
