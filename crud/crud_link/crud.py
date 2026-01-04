from database.db import SessionLocal
from database.models import Link
from datetime import datetime, timezone


def create_new_link(url: str) -> Link:
    db = SessionLocal()
    try:
        link_obj = Link(
            link=url,
            last_processed_at=None
        )
        db.add(link_obj)
        db.commit()
        db.refresh(link_obj)
        return link_obj
    finally:
        db.close()
