class DataProcessorError(Exception):
    """Base exception for errors that can be shown directly to CLI users."""


class InputFileError(DataProcessorError):
    """Raised when an input file cannot be read."""


class UnsupportedFormatError(DataProcessorError):
    """Raised when an input or output file extension is unsupported."""
