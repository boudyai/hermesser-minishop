from typing import Any, cast

from sqlalchemy.engine import CursorResult, Result


def rowcount(result: Result[Any]) -> int:
    """Return DML rowcount from SQLAlchemy results whose async stubs are generic."""
    return int(cast(CursorResult[Any], result).rowcount or 0)
