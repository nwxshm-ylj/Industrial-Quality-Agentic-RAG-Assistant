class DocumentParsingError(ValueError):
    """Base error exposed by the parser compatibility layer."""


class UnsupportedDocumentFormatError(DocumentParsingError):
    """Raised when no registered parser supports the file extension."""


class EmptyDocumentError(DocumentParsingError):
    """Raised when parsing produces no usable text elements."""


class ParserUnavailableError(DocumentParsingError):
    """Raised when a configured optional parser runtime cannot be loaded."""
