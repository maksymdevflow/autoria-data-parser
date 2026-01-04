from database.models import Link
from datetime import datetime, timedelta
from datetime import datetime, timezone
from database.db import SessionLocal
from database.models import Link, Car
 

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


def save_data_to_db(auto_params: dict) -> int:
    """
    Зберігає результати парсингу в БД.
    Повертає id створеного/оновленого Car.
    """
    db = SessionLocal()
    try:
        url = auto_params["link"]

        link_obj = db.query(Link).filter(Link.link == url).one_or_none()
        if link_obj is None:
            link_obj = Link(link=url, last_processed_at=datetime.now(timezone.utc))
            db.add(link_obj)
            db.flush()  
        else:
            link_obj.last_processed_at = datetime.now(timezone.utc)

        full_title = auto_params.get("full_title") or ""
        price_raw = auto_params.get("price") or ""
        mileage_raw = auto_params.get("millage") or ""

        brand = (full_title.split(" ")[0] if full_title else "Unknown")[:50]

        car_data = {
            "link_id": link_obj.id,
            "car_type": "Unknown",  # краще витягнути з cat_dict або зі сторінки
            "brand": brand,
            "fuel_type": "Unknown",  # теж витягнути з cat_dict
            "transmission": "Unknown",  # теж витягнути з cat_dict
            "price": _safe_int(price_raw),
            "year": _safe_int(full_title),  # спроба дістати рік з title
            "mileage": _safe_int(mileage_raw),
            "color": None,
            "location": (auto_params.get("location") or "")[:50] or None,
            "source": "auto_ria",
            "car_values": auto_params.get("cat_dict") or {},
            "description": auto_params.get("description") or "",
            "processed_status": None,
            "is_published": False,
        }

        existing = (
            db.query(Car)
            .filter(
                Car.link_id == link_obj.id,
                Car.year == car_data["year"],
                Car.price == car_data["price"],
            )
            .one_or_none()
        )

        if existing:
            for k, v in car_data.items():
                setattr(existing, k, v)
            car_obj = existing
        else:
            car_obj = Car(**car_data)
            db.add(car_obj)

        db.commit()
        db.refresh(car_obj)
        return car_obj.id

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
