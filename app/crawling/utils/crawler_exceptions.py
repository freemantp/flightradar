"""Exceptions used by the aircraft crawler for error handling and backoff logic."""


class SourceException(Exception):
    """Base exception for source query failures"""
    pass


class RetryableSourceException(SourceException):
    """Exception that should trigger retry/backoff (e.g., 429, 500, network errors)"""
    pass


class NonRetryableSourceException(SourceException):
    """Exception that should not trigger retry (e.g., 404, invalid aircraft)"""
    pass