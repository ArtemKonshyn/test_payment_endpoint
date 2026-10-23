from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction(session: Session) -> Iterator[None]:
    """Commit when the block finishes and roll back when it raises."""
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise
