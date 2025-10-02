"""Custom exception hierarchy for the ruleset compiler."""

class RulesetCompilerError(Exception):
    """Base exception for Module3-3 failures."""


class ValidationError(RulesetCompilerError):
    """Raised on schema, conflict, or integrity issues."""


class LoaderError(RulesetCompilerError):
    """Raised when input files cannot be parsed."""
