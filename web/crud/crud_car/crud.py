import re
from database.db import SessionLocal
from database.models import Car, Link, StatusProcessed
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple

# Укр/помилки -> англ марка (для пошуку: Рено, Рино, мерседес тощо)
SEARCH_UKR_TO_BRAND: Dict[str, str] = {
    "рено": "Renault",
    "рино": "Renault",
    "ренолт": "Renault",
    "мерседес": "Mercedes-Benz",
    "мерс": "Mercedes-Benz",
    "мерседес-бенц": "Mercedes-Benz",
    "бмв": "BMW",
    "фольксваген": "Volkswagen",
    "ву": "Volkswagen",
    "вольксваген": "Volkswagen",
    "опель": "Opel",
    "пежо": "Peugeot",
    "пежжо": "Peugeot",
    "фіат": "Fiat",
    "форд": "Ford",
    "ніссан": "Nissan",
    "тойота": "Toyota",
    "ситроен": "Citroen",
    "цитроен": "Citroen",
    "citroen": "Citroen",
    "івеко": "Iveco",
    "iveco": "Iveco",
    "мастер": "Master",
    "спринтер": "Sprinter",
    "мазда": "Mazda",
    "хюндай": "Hyundai",
    "hyundai": "Hyundai",
    "кіа": "Kia",
    "kia": "Kia",
    "скода": "Skoda",
    "skoda": "Skoda",
    "ман": "MAN",
    "man": "MAN",
    "volkswagen": "Volkswagen",
    "mercedes": "Mercedes-Benz",
    "renault": "Renault",
    "opel": "Opel",
    "ford": "Ford",
    "fiat": "Fiat",
    "nissan": "Nissan",
    "toyota": "Toyota",
    "peugeot": "Peugeot",
}


def _search_patterns_and_year(q: str) -> Tuple[List[str], Optional[List[int]]]:
    """З запиту q витягує список пошукових рядків (оригінал + укр->англ марки) та роки (19xx, 20xx)."""
    q = (q or "").strip()
    if not q:
        return [], None
    # Роки 19xx, 20xx
    year_matches = re.findall(r"\b(19\d{2}|20\d{2})\b", q)
    years = [int(y) for y in year_matches] if year_matches else None
    # Текст без чисел для марки/моделі (залишаємо цифри в одному слові, наприклад C250)
    tokens = re.findall(r"[^\s]+", q)
    patterns = [q]
    for t in tokens:
        t_lower = t.lower()
        if t_lower in SEARCH_UKR_TO_BRAND:
            patterns.append(SEARCH_UKR_TO_BRAND[t_lower])
        if len(t) > 1 and t not in patterns:
            patterns.append(t)
    return list(dict.fromkeys(patterns)), years


def get_cars(
    status: Optional[str] = None,
    link_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> Dict:
    """
    Отримує список авто з фільтрами та пагінацією.

    Args:
        status: Фільтр по статусу (CREATED, UPDATED, DELETED, NOT_PROCESSED)
        link_id: Фільтр по ID батьківського лінка
        search: Пошук по brand, description
        page: Номер сторінки
        per_page: Кількість записів на сторінці

    Returns:
        Dict з cars та pagination info
    """
    db = SessionLocal()
    try:
        query = db.query(Car)

        # Фільтр по статусу
        if status:
            try:
                status_enum = StatusProcessed[status.upper()]
                query = query.filter(Car.processed_status == status_enum)
            except KeyError:
                pass

        # Фільтр по link_id
        if link_id:
            query = query.filter(Car.link_id == link_id)

        # Пошук (по id, brand, description, link_path)
        if search:
            search = search.strip()
            if search.isdigit():
                query = query.filter(
                    or_(
                        Car.id == int(search),
                        Car.brand.ilike(f"%{search}%"),
                        Car.description.ilike(f"%{search}%"),
                        Car.link_path.ilike(f"%{search}%"),
                    )
                )
            else:
                search_pattern = f"%{search}%"
                query = query.filter(
                    or_(
                        Car.brand.ilike(search_pattern),
                        Car.description.ilike(search_pattern),
                        Car.link_path.ilike(search_pattern),
                    )
                )

        # Підрахунок загальної кількості
        total = query.count()

        # Сортування та пагінація
        query = query.order_by(Car.created_at.desc())
        offset = (page - 1) * per_page
        cars = query.offset(offset).limit(per_page).all()

        return {
            "cars": cars,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page,
        }
    finally:
        db.close()


def get_car_by_id(car_id: int) -> Optional[Car]:
    """Отримує авто по ID"""
    db = SessionLocal()
    try:
        return db.query(Car).filter(Car.id == car_id).first()
    finally:
        db.close()


def _car_to_detail_dict(car: Car, owner: Optional[str] = None) -> Dict:
    """Словник авто для відображення: owner, auto_ria_url, усі поля. auto_ria_url = link_path, якщо не починається з http — дописати base."""
    link_path = (car.link_path or "").strip()
    auto_ria_url = link_path
    if link_path and not link_path.startswith("http"):
        auto_ria_url = "https://auto.ria.com" + (link_path if link_path.startswith("/") else "/" + link_path)
    return {
        "id": car.id,
        "owner": (owner or "").strip() or "—",
        "auto_ria_url": auto_ria_url,
        "link_path": car.link_path,
        "brand": car.brand,
        "model": car.model,
        "year": car.year,
        "price": car.price,
        "mileage": car.mileage,
        "fuel_type": car.fuel_type,
        "transmission": car.transmission,
        "color": car.color,
        "location": car.location,
        "description": car.description or "",
        "full_description": getattr(car, "full_description", None) or "",
        "processed_status": car.processed_status.value if car.processed_status else None,
        "truck_car_id": car.truck_car_id,
        "link_id": car.link_id,
        "created_at": car.created_at.isoformat() if car.created_at else None,
    }


def get_car_with_owner(car_id: int) -> Optional[Dict]:
    """Повна інфа по авто з власником (Link.owner) для сторінки пошуку."""
    db = SessionLocal()
    try:
        row = (
            db.query(Car, Link.owner)
            .join(Link, Car.link_id == Link.id)
            .filter(Car.id == car_id)
            .first()
        )
        if not row:
            return None
        car, owner = row
        return _car_to_detail_dict(car, owner)
    finally:
        db.close()


def search_cars(
    q: Optional[str] = None,
    truck_car_id: Optional[int] = None,
    limit: int = 50,
    for_suggest: bool = False,
) -> List[Dict]:
    """
    Розумний пошук: по truck_car_id або по q (id, марка, модель, власник, опис, link_path).
    Марка/модель в БД англійською — пошук по будь-якому тексту (укр/анг).
    Повертає список словників з owner і auto_ria_url для кожного авто.
    for_suggest=True — обмежений набір полів для підказок (limit 15).
    """
    db = SessionLocal()
    try:
        query = (
            db.query(Car, Link.owner)
            .join(Link, Car.link_id == Link.id)
            .filter(Car.truck_car_id.isnot(None))
            .filter(Car.processed_status.notin_([StatusProcessed.DELETED, StatusProcessed.FAILED]))
        )

        if truck_car_id is not None:
            query = query.filter(Car.truck_car_id == truck_car_id)
        elif q:
            q = q.strip()
            if not q:
                return []
            if q.isdigit():
                num = int(q)
                query = query.filter(
                    or_(Car.id == num, Car.truck_car_id == num)
                )
            else:
                patterns, years = _search_patterns_and_year(q)
                conditions = []
                for p in patterns:
                    pat = f"%{p}%"
                    conditions.extend([
                        Car.brand.ilike(pat),
                        Car.model.ilike(pat),
                        Link.owner.ilike(pat),
                        Car.description.ilike(pat),
                        Car.link_path.ilike(pat),
                    ])
                    if hasattr(Car, "full_description"):
                        conditions.append(Car.full_description.ilike(pat))
                query = query.filter(or_(*conditions))
                if years:
                    query = query.filter(Car.year.in_(years))

        query = query.order_by(Link.owner.asc().nullsfirst(), Car.created_at.desc())
        limit = min(limit, 100)
        rows = query.limit(limit).all()

        result = []
        for car, owner in rows:
            if for_suggest:
                result.append({
                    "id": car.id,
                    "brand": car.brand,
                    "model": car.model,
                    "owner": (owner or "").strip() or "—",
                    "truck_car_id": car.truck_car_id,
                    "link_path": car.link_path,
                    "year": car.year,
                })
            else:
                result.append(_car_to_detail_dict(car, owner))
        return result
    finally:
        db.close()


def update_car(car_id: int, data: Dict) -> Optional[Car]:
    """Оновлює дані авто"""
    db = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            return None

        # Оновлюємо поля
        if "brand" in data:
            car.brand = data["brand"]
        if "fuel_type" in data:
            car.fuel_type = data["fuel_type"]
        if "transmission" in data:
            car.transmission = data["transmission"]
        if "price" in data:
            car.price = int(data["price"]) if data["price"] else 0
        if "year" in data:
            car.year = int(data["year"]) if data["year"] else 0
        if "mileage" in data:
            car.mileage = int(data["mileage"]) if data["mileage"] else 0
        if "color" in data:
            car.color = data["color"]
        if "location" in data:
            car.location = data["location"]
        if "description" in data:
            car.description = data["description"]
        if "is_published" in data:
            car.is_published = bool(data["is_published"])
        if "processed_status" in data:
            try:
                car.processed_status = StatusProcessed[data["processed_status"].upper()]
            except KeyError:
                pass

        car.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(car)
        return car
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


def bulk_update_processed_status(
    car_ids: List[int], processed_status: str
) -> int:
    """Множинне оновлення processed_status для обраних авто. Повертає кількість оновлених."""
    if not car_ids:
        return 0
    try:
        status_enum = StatusProcessed[processed_status.strip().upper()]
    except KeyError:
        return 0
    db = SessionLocal()
    try:
        updated = (
            db.query(Car)
            .filter(Car.id.in_(car_ids))
            .update(
                {
                    Car.processed_status: status_enum,
                    Car.updated_at: datetime.utcnow(),
                },
                synchronize_session="fetch",
            )
        )
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_statistics() -> Dict:
    """Отримує статистику по авто"""
    db = SessionLocal()
    try:
        # Загальна кількість
        total = db.query(func.count(Car.id)).scalar()

        # По статусах
        status_counts = (
            db.query(Car.processed_status, func.count(Car.id))
            .group_by(Car.processed_status)
            .all()
        )

        status_stats = {
            status.value if status else "None": count for status, count in status_counts
        }

        # По датах (останні 7 днів)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        daily_stats = (
            db.query(
                func.date(Car.created_at).label("date"),
                func.count(Car.id).label("count"),
            )
            .filter(Car.created_at >= seven_days_ago)
            .group_by(func.date(Car.created_at))
            .order_by(func.date(Car.created_at))
            .all()
        )

        daily_data = {str(date): count for date, count in daily_stats}

        # По батьківських лінках
        link_stats = (
            db.query(
                Link.id,
                Link.link,
                Link.car_type,
                Link.owner,
                func.count(Car.id).label("cars_count"),
            )
            .join(Car, Link.id == Car.link_id)
            .group_by(Link.id, Link.link, Link.car_type, Link.owner)
            .all()
        )

        links_data = [
            {
                "id": link_id,
                "link": link,
                "car_type": car_type,
                "owner": owner,
                "cars_count": count,
            }
            for link_id, link, car_type, owner, count in link_stats
        ]

        return {
            "total": total,
            "by_status": status_stats,
            "daily": daily_data,
            "by_link": links_data,
        }
    finally:
        db.close()


def get_statistics_filtered(
    period: str = "week",
    owner: Optional[str] = None,
    link_id: Optional[int] = None,
) -> Dict:
    """
    Статистика за період (день/тиждень/місяць), опційно по власнику або по одному посиланню.
    period: 'day' (24 год), 'week' (7 днів), 'month' (30 днів)
    owner: фільтр по Link.owner (усі авто по посиланнях цього власника)
    link_id: фільтр по одному посиланню
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        if period == "day":
            since = now - timedelta(days=1)
        elif period == "month":
            since = now - timedelta(days=30)
        else:
            since = now - timedelta(days=7)

        def base_query(q):
            q = q.filter(Car.created_at >= since)
            if link_id:
                q = q.filter(Car.link_id == link_id)
            if owner is not None and owner != "":
                q = q.join(Link, Car.link_id == Link.id)
                if owner == "—":
                    q = q.filter((Link.owner.is_(None)) | (Link.owner == ""))
                else:
                    q = q.filter(Link.owner == owner)
            return q

        total = base_query(db.query(Car)).count()

        q_status = base_query(
            db.query(Car.processed_status, func.count(Car.id))
        ).group_by(Car.processed_status)
        status_counts = q_status.all()
        by_status = {s.value if s else "None": c for s, c in status_counts}

        q_daily = base_query(
            db.query(func.date(Car.created_at).label("date"), func.count(Car.id).label("count"))
        ).group_by(func.date(Car.created_at)).order_by(func.date(Car.created_at))
        daily = q_daily.all()
        daily_data = {str(d): c for d, c in daily}

        return {
            "total": total,
            "by_status": by_status,
            "daily": daily_data,
            "period": period,
            "since": since,
        }
    finally:
        db.close()
