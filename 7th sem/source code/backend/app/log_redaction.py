"""Keep credentials out of server logs.

Uvicorn logs every request path including its query string, so a token passed as
`?token=...` (older WebSocket clients) would otherwise be written to the log in full.
"""
import logging
import re

_TOKEN_IN_QUERY = re.compile(r"((?:^|[?&])(?:token|access_token)=)[^&\s\"']+", re.IGNORECASE)


def redact_tokens(text: str) -> str:
    return _TOKEN_IN_QUERY.sub(r"\1<redacted>", text)


class RedactTokensFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_tokens(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_tokens(a) if isinstance(a, str) else a for a in record.args)
        return True


def install_log_redaction() -> None:
    """Attach the filter to uvicorn's request loggers (HTTP access and WebSocket lines)."""
    for name in ("uvicorn.access", "uvicorn.error"):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactTokensFilter) for f in logger.filters):
            logger.addFilter(RedactTokensFilter())
