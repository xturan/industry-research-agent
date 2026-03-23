from collections.abc import Generator

from sqlalchemy.orm import Session

from packages.db.session import SessionLocal


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
