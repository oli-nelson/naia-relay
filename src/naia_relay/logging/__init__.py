from __future__ import annotations

import logging


def _coerce_level(level: int | str) -> int:
    if isinstance(level, int):
        return level
    normalized = level.upper()
    return getattr(logging, normalized, logging.INFO)


class DefaultFieldsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for field, value in {
            "role": "-",
            "protocol_side": "-",
            "transport": "-",
            "session_id": "-",
            "request_id": "-",
            "execution_id": "-",
        }.items():
            if not hasattr(record, field):
                setattr(record, field, value)
        return True


def configure_logging(level: int | str = logging.INFO) -> None:
    resolved_level = _coerce_level(level)
    default_fields_filter = DefaultFieldsFilter()
    handler = logging.StreamHandler()
    handler.addFilter(default_fields_filter)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "[role=%(role)s side=%(protocol_side)s transport=%(transport)s session=%(session_id)s "
            "request=%(request_id)s execution=%(execution_id)s]"
        )
    )
    logging.basicConfig(level=resolved_level, handlers=[handler], force=True)
    logging.getLogger().addFilter(default_fields_filter)
