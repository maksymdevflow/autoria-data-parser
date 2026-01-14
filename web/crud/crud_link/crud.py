from database.db import SessionLocal
from database.models import Link
from datetime import datetime, timezone


def create_new_link(url: str, car_type: str | None = None, owner: str | None = None) -> Link:
    """
    Створює новий Link або повертає існуючий, якщо такий URL вже є.
    Якщо передані car_type / owner, оновлює їх у існуючому записі.
    """
    db = SessionLocal()
    try:
        # Перевіряємо, чи такий лінк вже існує
        link_obj = db.query(Link).filter(Link.link == url).first()

        if link_obj:
            # Оновлюємо car_type / власника, якщо вони прийшли з форми / API
            if car_type:
                link_obj.car_type = car_type
            if owner:
                link_obj.owner = owner

            link_obj.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(link_obj)
            return link_obj

        # Якщо лінка ще немає — створюємо
        link_obj = Link(
            link=url,
            car_type=car_type,
            owner=owner,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            last_processed_at=None,
        )
        db.add(link_obj)
        db.commit()
        db.refresh(link_obj)
        return link_obj
    finally:
        db.close()