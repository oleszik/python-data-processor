from pathlib import Path

import pandas as pd
import pytest

from data_processor.cleaning import clean_data, inspect_dataset
from data_processor.errors import InputFileError, UnsupportedFormatError
from data_processor.io import export_dataset, load_dataset
from data_processor.reporting import build_summary


def test_load_csv(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    path.write_text("name,score\nAda,10\n", encoding="utf-8")

    result = load_dataset(path)

    assert result.to_dict("records") == [{"name": "Ada", "score": 10}]


def test_load_xlsx(tmp_path: Path) -> None:
    path = tmp_path / "input.xlsx"
    pd.DataFrame({"name": ["Ada"], "score": [10]}).to_excel(path, index=False)

    result = load_dataset(path)

    assert result.to_dict("records") == [{"name": "Ada", "score": 10}]


def test_inspection_reports_schema_and_quality_counts() -> None:
    dataframe = pd.DataFrame({"Full Name": ["Ada", None], "Score": [10, 10]})

    inspection = inspect_dataset(dataframe)

    assert inspection["row_count"] == 2
    assert inspection["column_count"] == 2
    assert inspection["columns"] == ["Full Name", "Score"]
    assert inspection["data_types"]["Full Name"] in {"object", "str"}
    assert inspection["data_types"]["Score"] == "int64"
    assert inspection["missing_values"] == {"Full Name": 1, "Score": 0}
    assert inspection["duplicate_rows"] == 0


def test_cleaning_trims_normalizes_and_removes_empty_and_duplicate_rows() -> None:
    dataframe = pd.DataFrame(
        {
            " Full Name ": [" Ada ", "Ada", "  ", None],
            "Annual Score!": [10, 10, None, None],
        }
    )

    cleaned, stats = clean_data(dataframe)

    assert cleaned.to_dict("records") == [{"full_name": "Ada", "annual_score": 10}]
    assert stats.empty_rows_removed == 2
    assert stats.duplicates_removed == 1


def test_normalized_column_name_collisions_are_made_unique() -> None:
    dataframe = pd.DataFrame([[1, 2, 3]], columns=["Score", " score ", "Score!"])

    cleaned, _ = clean_data(dataframe)

    assert list(cleaned.columns) == ["score", "score_2", "score_3"]


def test_missing_keep_strategy_preserves_missing_values() -> None:
    dataframe = pd.DataFrame({"name": ["Ada", None], "score": [10, 20]})

    cleaned, _ = clean_data(dataframe, missing_strategy="keep")

    assert len(cleaned) == 2
    assert int(cleaned.isna().sum().sum()) == 1


def test_missing_drop_strategy_drops_rows_with_missing_values() -> None:
    dataframe = pd.DataFrame({"name": ["Ada", None], "score": [10, 20]})

    cleaned, _ = clean_data(dataframe, missing_strategy="drop")

    assert cleaned.to_dict("records") == [{"name": "Ada", "score": 10}]


def test_missing_fill_strategy_uses_provided_value() -> None:
    dataframe = pd.DataFrame({"name": ["Ada", None], "score": [10, 20]})

    cleaned, _ = clean_data(dataframe, missing_strategy="fill", fill_value="unknown")

    assert cleaned["name"].tolist() == ["Ada", "unknown"]


def test_fill_strategy_requires_value() -> None:
    with pytest.raises(ValueError, match="fill_value is required"):
        clean_data(pd.DataFrame({"name": [None]}), missing_strategy="fill")


@pytest.mark.parametrize("suffix", [".csv", ".xlsx"])
def test_export_and_read_back(tmp_path: Path, suffix: str) -> None:
    dataframe = pd.DataFrame({"name": ["Ada"], "score": [10]})
    path = tmp_path / f"output{suffix}"

    export_dataset(dataframe, path)
    result = load_dataset(path)

    assert result.to_dict("records") == [{"name": "Ada", "score": 10}]


def test_unsupported_input_and_output_formats(tmp_path: Path) -> None:
    with pytest.raises(UnsupportedFormatError, match="Supported formats"):
        load_dataset(tmp_path / "data.json")
    with pytest.raises(UnsupportedFormatError, match="Supported formats"):
        export_dataset(pd.DataFrame(), tmp_path / "data.json")


def test_missing_input_file_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(InputFileError, match="does not exist"):
        load_dataset(tmp_path / "missing.csv")


def test_invalid_xlsx_raises_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "invalid.xlsx"
    path.write_text("not an Excel workbook", encoding="utf-8")

    with pytest.raises(InputFileError, match="Could not read input file"):
        load_dataset(path)


def test_directory_input_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(InputFileError, match="not a file"):
        load_dataset(tmp_path)


def test_summary_counts_rows_missing_values_and_operations() -> None:
    original = pd.DataFrame(
        {"Full Name": [" Ada ", "Ada", None], "Score": [10, 10, 30]}
    )
    cleaned, stats = clean_data(original)

    summary = build_summary(
        original,
        cleaned,
        stats.duplicates_removed,
        stats.empty_rows_removed,
        "cleaned.csv",
    )

    assert summary.original_row_count == 3
    assert summary.final_row_count == 2
    assert summary.duplicates_removed == 1
    assert summary.missing_values_before == 1
    assert summary.missing_values_after == 1
    assert summary.columns_processed == ["full_name", "score"]
