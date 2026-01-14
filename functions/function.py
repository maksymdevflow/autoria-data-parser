from database.models import Link
from datetime import datetime, timedelta
from datetime import datetime, timezone
from database.db import SessionLocal
from database.models import Link, Car, StatusProcessed

from sqlalchemy.orm import Session
from database.models import Link
from datetime import datetime, timezone

def get_or_create_link(session: Session, url: str) -> Link:
    link = session.query(Link).filter(Link.link == url).first()

    if link:
        link.updated_at = datetime.utcnow()
        link.last_processed_at = datetime.now(timezone.utc)
        return link

    link = Link(
        link=url,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_processed_at=datetime.now(timezone.utc),
    )

    session.add(link)
    session.flush()  # 💥 щоб зʼявився link.id без commit
    return link

import re

def parse_int(value: str | int | None) -> int:
    """
    Парсить число з рядка або повертає число якщо воно вже int.
    """
    if value is None:
        return 0
    
    # Якщо вже число, повертаємо його
    if isinstance(value, int):
        return value
    
    # Якщо рядок, парсимо його
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else 0
    
    # Для інших типів намагаємося конвертувати в рядок
    try:
        digits = re.sub(r"[^\d]", "", str(value))
        return int(digits) if digits else 0
    except:
        return 0

def check_period_link_to_process():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=1)

        links = (
            db.query(Link)
            .filter(
                (Link.last_processed_at == None) |
                (Link.last_processed_at < threshold)
            )
            .all()
        )

        return links
    finally:
        db.close()

def _safe_int(value: str) -> int:
    """Дістає число з рядка типу '12 300 $' або '123 тис. км'."""
    if value is None:
        return 0
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else 0


def save_data_to_db(data: dict, parent_link: str, car_link: str):
    """
    Зберігає дані про авто в БД.
    
    Args:
        data: Словник з даними про авто
        parent_link: Батьківський лінк (той що для парсингу)
        car_link: Персональний лінк авто
    """
    session = SessionLocal()

    try:
        # Отримуємо або створюємо батьківський лінк
        parent_link_obj = get_or_create_link(session, parent_link)
        
        # Перевіряємо чи вже існує запис з цим link_path
        existing_car = session.query(Car).filter(Car.link_path == car_link).first()
        if existing_car:
            # Оновлюємо існуючий запис
            existing_car.brand = data.get("brand", "Unknown")
            existing_car.fuel_type = data.get("fuel_type", "Unknown")
            existing_car.transmission = data.get("transmission", "Unknown")
            existing_car.price = parse_int(data.get("price"))
            existing_car.year = parse_int(data.get("year"))
            existing_car.mileage = parse_int(data.get("mileage"))
            existing_car.color = data.get("color")
            existing_car.location = data.get("location")
            existing_car.car_values = data.get("car_values", {})
            existing_car.description = data.get("description", "")
            existing_car.processed_status = StatusProcessed.UPDATED
            session.commit()
            return

        car = Car(
            link_id=parent_link_obj.id,
            link_path=car_link,  # Персональний лінк авто
            brand=data.get("brand", "Unknown"),
            fuel_type=data.get("fuel_type", "Unknown"),
            transmission=data.get("transmission", "Unknown"),
            price = parse_int(data.get("price")),
            year = parse_int(data.get("year")),
            mileage = parse_int(data.get("mileage")),
            color=data.get("color"),
            location=data.get("location"),
            source="auto_ria",

            car_values=data.get("car_values", {}),

            description=data.get("description", ""),
            is_published=False,
            processed_status=StatusProcessed.CREATED,
        )

        session.add(car)
        session.commit()

    except Exception as e:
        session.rollback()
        # Спробуємо зберегти запис з FAILED статусом
        try:
            parent_link_obj = get_or_create_link(session, parent_link)
            # Перевіряємо чи вже існує запис з цим link_path
            existing_car = session.query(Car).filter(Car.link_path == car_link).first()
            if existing_car:
                existing_car.processed_status = StatusProcessed.FAILED
                session.commit()
            else:
                # Створюємо мінімальний запис з FAILED
                car = Car(
                    link_id=parent_link_obj.id,
                    link_path=car_link,
                    brand="Unknown",
                    fuel_type="Unknown",
                    transmission="Unknown",
                    price=0,
                    year=0,
                    mileage=0,
                    source="auto_ria",
                    car_values={},
                    description=f"Error: {str(e)}",
                    is_published=False,
                    processed_status=StatusProcessed.DELETED,
                )
                session.add(car)
                session.commit()
        except Exception as save_error:
            session.rollback()
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to save FAILED status: {save_error}")
        finally:
            session.close()
        raise
    finally:
        session.close()


def period_check_link(link):
    links_to_check=Car.objects.filter(link).only("link")
    
    # run scraper to get all links via link
    # check_website_aviable_links(link)
    
    links_after_check=[]

    for link in links_to_check:
        if link in links_after_check:
            links_to_check.last_processed_at=datetime.now
        else:
            links_to_check.last_processed_at=datetime.now
            # STATUS TO DELETE

    for link in links_after_check:
        if link not in links_to_check:
            # STATUS TO CREATE
            pass
    return

