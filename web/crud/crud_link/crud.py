from database.db import SessionLocal
from database.models import Link, LinkParseStatus, LinkToCreate, LinkToDelete
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any


def get_links_grouped_by_owner(
    parse_status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Список лінків згрупованих по власнику (owner). Для кожного owner — список лінків."""
    db = SessionLocal()
    try:
        query = db.query(Link).order_by(
            Link.owner.asc().nullsfirst(), Link.created_at.desc()
        )
        if parse_status:
            try:
                status_enum = LinkParseStatus(parse_status.upper())
                query = query.filter(Link.parse_status == status_enum)
            except ValueError:
                pass
        links = query.all()
        groups: Dict[str, List[Link]] = {}
        for link in links:
            owner_key = (link.owner or "").strip() or "—"
            if owner_key not in groups:
                groups[owner_key] = []
            groups[owner_key].append(link)
        return [
            {"owner": owner, "links": links_list}
            for owner, links_list in sorted(groups.items())
        ]
    finally:
        db.close()


def get_links(
    parse_status: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
) -> Dict:
    """Список лінків з фільтром по parse_status та пагінацією."""
    db = SessionLocal()
    try:
        query = db.query(Link).order_by(Link.created_at.desc())
        if parse_status:
            try:
                status_enum = LinkParseStatus(parse_status.upper())
                query = query.filter(Link.parse_status == status_enum)
            except ValueError:
                pass
        total = query.count()
        offset = (page - 1) * per_page
        links = query.offset(offset).limit(per_page).all()
        return {
            "links": links,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": max(1, (total + per_page - 1) // per_page),
        }
    finally:
        db.close()


def get_owners_list() -> List[str]:
    """Список унікальних власників (owner) для фільтрів."""
    db = SessionLocal()
    try:
        rows = (
            db.query(Link.owner)
            .distinct()
            .order_by(Link.owner.asc().nullsfirst())
            .all()
        )
        return [r[0] if r[0] and str(r[0]).strip() else "—" for r in rows]
    finally:
        db.close()


def get_links_for_filter() -> List[Dict[str, Any]]:
    """Список посилань (id, link, owner) для вибору в фільтрі статистики."""
    db = SessionLocal()
    try:
        links = db.query(Link).order_by(Link.owner.asc().nullsfirst(), Link.id.asc()).all()
        return [
            {"id": l.id, "link": l.link, "owner": (l.owner or "").strip() or "—"}
            for l in links
        ]
    finally:
        db.close()


def get_link_by_id(link_id: int) -> Optional[Link]:
    """Лінк по id з авто, links_to_create, links_to_delete."""
    db = SessionLocal()
    try:
        return (
            db.query(Link)
            .options(
                joinedload(Link.cars),
                joinedload(Link.links_to_create),
                joinedload(Link.links_to_delete),
            )
            .filter(Link.id == link_id)
            .first()
        )
    finally:
        db.close()


def create_new_link(
    url: str, car_type: str | None = None, owner: str | None = None
) -> Link:
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
