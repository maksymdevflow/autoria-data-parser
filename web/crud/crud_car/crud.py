from database.db import SessionLocal
from database.models import Car, Link, StatusProcessed
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
from typing import Optional, Dict, List


def get_cars(
    status: Optional[str] = None,
    link_id: Optional[int] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 50
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
        
        # Пошук
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Car.brand.ilike(search_pattern),
                    Car.description.ilike(search_pattern),
                    Car.link_path.ilike(search_pattern)
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
            "pages": (total + per_page - 1) // per_page
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


def get_statistics() -> Dict:
    """Отримує статистику по авто"""
    db = SessionLocal()
    try:
        # Загальна кількість
        total = db.query(func.count(Car.id)).scalar()
        
        # По статусах
        status_counts = db.query(
            Car.processed_status,
            func.count(Car.id)
        ).group_by(Car.processed_status).all()
        
        status_stats = {status.value if status else "None": count for status, count in status_counts}
        
        # По датах (останні 7 днів)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        daily_stats = db.query(
            func.date(Car.created_at).label("date"),
            func.count(Car.id).label("count")
        ).filter(
            Car.created_at >= seven_days_ago
        ).group_by(
            func.date(Car.created_at)
        ).order_by(
            func.date(Car.created_at)
        ).all()
        
        daily_data = {str(date): count for date, count in daily_stats}
        
        # По батьківських лінках
        link_stats = db.query(
            Link.id,
            Link.link,
            Link.car_type,
            Link.owner,
            func.count(Car.id).label("cars_count")
        ).join(
            Car, Link.id == Car.link_id
        ).group_by(
            Link.id, Link.link, Link.car_type, Link.owner
        ).all()
        
        links_data = [
            {
                "id": link_id,
                "link": link,
                "car_type": car_type,
                "owner": owner,
                "cars_count": count
            }
            for link_id, link, car_type, owner, count in link_stats
        ]
        
        return {
            "total": total,
            "by_status": status_stats,
            "daily": daily_data,
            "by_link": links_data
        }
    finally:
        db.close()

