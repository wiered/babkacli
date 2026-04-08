"""Errors raised by tool-call execution."""


class CommandExecutionError(RuntimeError):
    """Raised when a command cannot be executed safely."""
