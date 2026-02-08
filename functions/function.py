import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Link, Car, StatusProcessed

logger = logging.getLogger(__name__)


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


def parse_float(value: str | float | None) -> float:
    """
    Парсить десяткове число з рядка або повертає число якщо воно вже float.
    """
    if value is None:
        return 0.0

    # Якщо вже число, повертаємо його
    if isinstance(value, (int, float)):
        return float(value)

    # Якщо рядок, парсимо його (витягуємо цифри, крапку та кому)
    if isinstance(value, str):
        # Замінюємо кому на крапку для парсингу
        cleaned = value.replace(",", ".")
        # Витягуємо число з крапкою
        match = re.search(r"\d+\.?\d*", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return 0.0

    return 0.0


def check_period_link_to_process():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(days=1)

        links = (
            db.query(Link)
            .filter(
                (Link.last_processed_at == None) | (Link.last_processed_at < threshold)
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


def save_data_to_db(
    data: dict,
    parent_link: str,
    car_link: str,
    processed_status: StatusProcessed | None = None,
):
    """
    Зберігає дані про авто в БД.

    Args:
        data: Словник з даними про авто
        parent_link: Батьківський лінк (той що для парсингу)
        car_link: Персональний лінк авто
        processed_status: Якщо FAILED — зберігаємо з цим статусом і додаємо в links_to_delete
    """
    session = SessionLocal()
    status_for_new = processed_status or StatusProcessed.CREATED
    status_for_update = processed_status or StatusProcessed.UPDATED

    # Статуси, після яких авто не перезаписуємо при повторному парсингу
    FINAL_STATUSES = (StatusProcessed.CREATED, StatusProcessed.ACTIVE, StatusProcessed.DELETED)

    try:
        parent_link_obj = get_or_create_link(session, parent_link)
        existing_car = session.query(Car).filter(Car.link_path == car_link).first()
        if existing_car:
            if existing_car.processed_status in FINAL_STATUSES:
                return
            existing_car.brand = data.get("brand", "Unknown")
            existing_car.model = data.get("model")
            existing_car.fuel_type = data.get("fuel_type", "Unknown")
            existing_car.transmission = data.get("transmission", "Unknown")
            existing_car.price = parse_int(data.get("price"))
            existing_car.year = parse_int(data.get("year"))
            existing_car.mileage = parse_int(data.get("mileage"))
            existing_car.color = data.get("color")
            existing_car.location = data.get("location")
            existing_car.path_to_images = data.get("path_to_images")
            existing_car.car_values = data.get("car_values", {})
            existing_car.description = data.get("description", "")
            existing_car.full_description = data.get("full_description")
            existing_car.processed_status = status_for_update
            session.commit()
            if processed_status == StatusProcessed.FAILED:
                _add_link_to_delete_if_missing(session, parent_link_obj.id, car_link)
            return

        car = Car(
            link_id=parent_link_obj.id,
            link_path=car_link,
            brand=data.get("brand", "Unknown"),
            model=data.get("model"),
            fuel_type=data.get("fuel_type", "Unknown"),
            transmission=data.get("transmission", "Unknown"),
            price=parse_int(data.get("price")),
            year=parse_int(data.get("year")),
            mileage=parse_int(data.get("mileage")),
            color=data.get("color"),
            location=data.get("location"),
            source="auto_ria",
            path_to_images=data.get("path_to_images"),
            car_values=data.get("car_values", {}),
            description=data.get("description", ""),
            full_description=data.get("full_description"),
            is_published=False,
            processed_status=status_for_new,
        )
        session.add(car)
        session.commit()
        if processed_status == StatusProcessed.FAILED:
            _add_link_to_delete_if_missing(session, parent_link_obj.id, car_link)
    except Exception as e:
        session.rollback()
        try:
            save_failed_car_and_add_to_delete(parent_link, car_link)
        except Exception as save_error:
            logger.error("Failed to save FAILED status: %s", save_error)
    finally:
        session.close()


def _add_link_to_delete_if_missing(
    session: Session, parent_link_id: int, car_link: str
) -> None:
    existing = (
        session.query(LinkToDelete)
        .filter(
            LinkToDelete.parent_link_id == parent_link_id,
            LinkToDelete.link == car_link,
        )
        .first()
    )
    if not existing:
        session.add(
            LinkToDelete(parent_link_id=parent_link_id, link=car_link)
        )
        session.commit()


def period_check_link(link):
    links_to_check = Car.objects.filter(link).only("link")

    # run scraper to get all links via link
    # check_website_aviable_links(link)

    links_after_check = []

    for link in links_to_check:
        if link in links_after_check:
            links_to_check.last_processed_at = datetime.now
        else:
            links_to_check.last_processed_at = datetime.now
            # STATUS TO DELETE

    for link in links_after_check:
        if link not in links_to_check:
            # STATUS TO CREATE
            pass
    return


from database.models import Link, Car, StatusProcessed, LinkToCreate, LinkToDelete


def save_failed_car_and_add_to_delete(parent_link: str, car_link: str) -> None:
    """
    Якщо не вдалося спарсити авто: створює/оновлює Car з processed_status=FAILED
    і додає посилання в links_to_delete (щоб пізніше видалити з TruckMarket або не обробляти).
    """
    session = SessionLocal()
    try:
        parent_link_obj = get_or_create_link(session, parent_link)
        existing_car = session.query(Car).filter(Car.link_path == car_link).first()
        if existing_car:
            existing_car.processed_status = StatusProcessed.FAILED
        else:
            car = Car(
                link_id=parent_link_obj.id,
                link_path=car_link,
                brand="Unknown",
                model=None,
                fuel_type="Unknown",
                transmission="Unknown",
                price=0,
                year=0,
                mileage=0,
                source="auto_ria",
                car_values={},
                description="Parse failed",
                is_published=False,
                processed_status=StatusProcessed.FAILED,
            )
            session.add(car)
        # Додати в links_to_delete, якщо ще немає
        existing_ltd = (
            session.query(LinkToDelete)
            .filter(
                LinkToDelete.parent_link_id == parent_link_obj.id,
                LinkToDelete.link == car_link,
            )
            .first()
        )
        if not existing_ltd:
            session.add(
                LinkToDelete(
                    parent_link_id=parent_link_obj.id,
                    link=car_link,
                )
            )
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error("save_failed_car_and_add_to_delete failed: %s", e)
    finally:
        session.close()


def check_update_link_status(link: str, parsed_links: list[str]) -> bool:
    """
    Для parent link:
    - знаходить всі поточні car.link_path в БД
    - порівнює з parsed_links
    - записує різницю в таблиці links_to_create / links_to_delete
    """
    session = SessionLocal()
    try:
        link_obj = session.query(Link).filter(Link.link == link).first()
        if not link_obj:
            return False

        # Поточні лінки авто з БД
        existing_cars = session.query(Car).filter(Car.link_id == link_obj.id).all()
        existing_links = {car.link_path for car in existing_cars}
        parsed_set = set(parsed_links)

        # Хто зник → to delete
        to_delete = existing_links - parsed_set
        # Хто новий → to create
        to_create = parsed_set - existing_links

        # Почистимо старі записи для цього parent_link,
        # щоб таблиці відображали тільки актуальну різницю
        session.query(LinkToDelete).filter(
            LinkToDelete.parent_link_id == link_obj.id
        ).delete(synchronize_session=False)

        session.query(LinkToCreate).filter(
            LinkToCreate.parent_link_id == link_obj.id
        ).delete(synchronize_session=False)

        # Записуємо "to delete"
        for link_path in to_delete:
            session.add(
                LinkToDelete(
                    parent_link_id=link_obj.id,
                    link=link_path,
                )
            )

        # Записуємо "to create" — лише якщо такого link ще немає в таблиці (унікальність)
        existing_to_create_links = set()
        if to_create:
            existing_to_create_links = {
                row[0]
                for row in session.query(LinkToCreate.link)
                .filter(LinkToCreate.link.in_(to_create))
                .all()
            }
        for link_path in to_create:
            if link_path in existing_to_create_links:
                continue
            session.add(
                LinkToCreate(
                    parent_link_id=link_obj.id,
                    link=link_path,
                )
            )
            existing_to_create_links.add(link_path)

        session.commit()
        return True
    finally:
        session.close()


import requests
from dotenv import load_dotenv
import os
import shutil

load_dotenv()


class TruckMarket:
    def __init__(self, token_provider: "TokenProvider"):
        self.token_provider = token_provider
        self.base_url = os.getenv("TRUCK_BASE_URL")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token_provider.get_token()}",
        }

    def _request(self, method, path, **kwargs):
        response = requests.request(
            method, f"{self.base_url}{path}", headers=self._headers(), **kwargs
        )

        if response.status_code == 401:
            self.token_provider.invalidate()
            response = requests.request(
                method, f"{self.base_url}{path}", headers=self._headers(), **kwargs
            )

        if not response.ok:
            try:
                err_body = response.json()
            except Exception:
                err_body = response.text
            logger.error(
                "TruckMarket API error: %s %s -> %s body=%s",
                method, path, response.status_code, err_body,
            )
        response.raise_for_status()
        return response.json()

    def process_payload(self, car: Car, link_car_type: str | None = None) -> dict:
        """
        Готує фінальний payload у форматі TruckMarket.
        link_car_type — категорія батьківського лінка (Link.car_type), визначає які константи використовувати (3.5т / 5-15т тощо).
        """
        base = prepare_car_data_for_truck_market_api(car, link_car_type)
        print(f"Base payload for car {car.id}: {base}")
        # Отримуємо ID міста (TruckMarket не приймає geo_city=null — потрібен валідний id)
        geo_city_id = None
        city_name = base.get("geo_city_name")
        if city_name:
            try:
                location_response = self.get_location_by_name(city_name)
                data_list = location_response.get("data") or []
                if data_list:
                    geo_city_id = data_list[0].get("id")
                else:
                    logger.warning(
                        "TruckMarket geo/regions/list returned no results for city_name=%r",
                        city_name,
                    )
            except Exception as e:
                logger.warning("Failed to resolve geo_city for '%s': %s", city_name, e)
        # Якщо не знайшли місто — використовуємо місто за замовчуванням з env (API не приймає null)
        if geo_city_id is None:
            default_id = os.getenv("GEO_CITY_ID_DEFAULT")
            if default_id is not None and str(default_id).strip().isdigit():
                geo_city_id = int(str(default_id).strip())
                logger.info("Using GEO_CITY_ID_DEFAULT=%s for listing", geo_city_id)
            else:
                logger.warning(
                    "geo_city is missing and GEO_CITY_ID_DEFAULT not set — API may return 400"
                )

        f_values = base.get("format_f", {}) or {}

        data = {
            "user_id": base.get("user_id"),
            "company": base.get("company"),
            "cat_id": base.get("cat_id"),
            "title": {"uk": base.get("title_uk")},
            "descr": {"uk": base.get("descr_uk")},
            "price": base.get("price"),
            "price_curr": base.get("price_curr"),
            "geo_city": geo_city_id,
        }

        # Додаємо f1..f14 на верхній рівень data
        data.update({k: v for k, v in f_values.items() if v is not None})

        return {
            "car_id": base.get("car_id"),
            "car_photo_path": base.get("car_photo_path"),
            "data": data,
        }

    def _get_link_car_type(self, car: Car) -> str | None:
        """Повертає категорію батьківського лінка (Link.car_type) для вибору констант TruckMarket (3.5т / 5-15т тощо)."""
        db = SessionLocal()
        try:
            link = db.query(Link).filter(Link.id == car.link_id).first()
            return link.car_type if link else None
        finally:
            db.close()

    def process_add_car(self, car: Car):
        """
        Повний цикл:
        - отримати категорію батьківського лінка (Link.car_type);
        - підготувати payload з константами для цієї категорії;
        - створити оголошення;
        - зберегти truck_car_id у БД;
        - завантажити фото.
        """
        link_car_type = self._get_link_car_type(car)
        payload = self.process_payload(car, link_car_type)
        logger.info("TruckMarket payload before create_car: %s", payload)

        car_id = payload.get("car_id")
        car_photo_path = payload.get("car_photo_path", "")
        data = payload.get("data", {})

        # Формуємо список локальних шляхів до фото
        try:
            images = (
                ImagesProcessor().get_images_by_path(car_photo_path)
                if car_photo_path
                else []
            )
        except Exception as e:
            print(f"Error processing images for car {car_id}: {e}")
            images = []

        # Відправляємо тільки структуру {"data": {...}} як в API
        request_body = {"data": data}
        logger.info(
            "TruckMarket create request JSON (car_id=%s): %s",
            car_id,
            json.dumps(request_body, ensure_ascii=False, default=str),
        )
        created = self.create_car(request_body)
        logger.info("TruckMarket create_car response for car %s: %s", car_id, created)
        if not created.get("success"):
            logger.error(
                "TruckMarket create_car failed for car %s: %s", car_id, created
            )
            # Позначаємо авто як FAILED, якщо не вдалося створити оголошення
            self._set_car_status(car_id, StatusProcessed.FAILED)
            return False

        truck_car_id = created.get("data", {}).get("id")
        if not truck_car_id:
            logger.error(
                "TruckMarket did not return id for car %s: %s", car_id, created
            )
            self._set_car_status(car_id, StatusProcessed.FAILED)
            return False

        try:
            save_truck_car_id_to_db(car_id, truck_car_id)
        except Exception as e:
            print(f"Error saving truck car id for car {car_id}: {e}")
            # не перериваємо повністю, оголошення вже створене

        if images:
            try:
                self.update_car_images(truck_car_id, images)
            except Exception as e:
                print(f"Error updating car images for car {car_id}: {e}")

        if car_photo_path:
            try:
                dir_path = os.path.join("car_images", car_photo_path)
                if os.path.isdir(dir_path):
                    shutil.rmtree(dir_path)
                    logger.info("Removed car images folder after upload: %s", dir_path)
            except Exception as e:
                logger.warning(
                    "Could not remove car images folder %s: %s", car_photo_path, e
                )

        return True

    def get_location_by_name(self, location: str):
        """Запит до geo/regions/list: filter по title_uk, з отриманого data беремо перший елемент і його id."""
        return self._request(
            method="POST",
            path="/intapi/v1/geo/regions/list",
            json={
                "filter": {"title_uk": location},
                "fields": ["*"],
                "orderBy": "fav asc",
                "limit": 1,
            },
        )

    def create_car(self, car: dict):
        return self._request(method="POST", path="/intapi/v1/listings/create", json=car)

    def update_car_images(self, truck_car_id: int, images: list[str]):
        """
        Завантажує фото в такому порядку, щоб ГОЛОВНИМ стало перше фото
        у нашому списку `images`.

        За твоїм спостереженням TruckMarket робить головним ПЕРШЕ завантажене
        зображення, тому відправляємо файли у природньому порядку:
        спочатку images[0] (car_1_no_logo.jpg), потім images[1], ...
        """
        for image_path in images:
            with open(image_path, "rb") as f:
                files = {
                    "file": (os.path.basename(image_path), f, "image/jpeg"),
                }
                # Використовуємо _request, який вже додає Authorization
                self._request(
                    method="POST",
                    path=f"/intapi/v1/listings/images/{truck_car_id}",
                    files=files,
                )

    def delete_car_by_id(self, truck_car_id: int | None):
        """Видалення оголошення з TruckMarket. Якщо truck_car_id None — запит не викликається."""
        if truck_car_id is None:
            return
        return self._request(
            method="DELETE",
            path=f"/intapi/v1/listings/delete/{truck_car_id}",
        )

    @staticmethod
    def _set_car_status(car_id: int, status: StatusProcessed):
        """Допоміжний метод для оновлення processed_status у таблиці cars."""
        session = SessionLocal()
        try:
            car = session.query(Car).filter(Car.id == car_id).first()
            if car:
                car.processed_status = status
                session.commit()
        finally:
            session.close()


def save_truck_car_id_to_db(car_id: int, truck_car_id: int):
    session = SessionLocal()
    try:
        car = session.query(Car).filter(Car.id == car_id).first()
        if car:
            car.truck_car_id = truck_car_id
            # Після успішної відправки в TruckMarket вважаємо авто активним
            car.processed_status = StatusProcessed.ACTIVE
            session.commit()
    finally:
        session.close()


class ImagesProcessor:
    def get_images_by_path(self, path: str) -> list[str]:
        """
        Повертає список повних шляхів до всіх зображень у папці `car_images/{path}`.
        `path` очікується як `car_photo_path` з payload (тобто назва/шлях папки).
        """
        base_dir = "car_images"
        dir_path = os.path.join(base_dir, path)

        if not os.path.isdir(dir_path):
            return []

        # os.listdir() + sorted() сортують лексикографічно:
        # car_1..., car_10..., car_11..., car_2...
        # Нам потрібне "людське" сортування за номером у назві файлу.
        def _num_key(name: str) -> tuple[int, str]:
            m = re.search(r"(\d+)", name)
            if m:
                return int(m.group(1)), name
            return 0, name

        filenames = [
            name
            for name in os.listdir(dir_path)
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
        ]

        filenames.sort(key=_num_key)

        image_paths: list[str] = [
            os.path.join(dir_path, filename) for filename in filenames
        ]

        return image_paths


from dataclasses import dataclass


@dataclass
class AccessToken:
    value: str
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.utcnow() >= self.expires_at


class TokenProvider:
    def get_token(self) -> str:
        raise NotImplementedError

    def invalidate(self) -> None:
        raise NotImplementedError


class TruckMarketTokenProvider(TokenProvider):
    def __init__(self):
        self.base_url = os.getenv("TRUCK_BASE_URL")
        self.secret_key = os.getenv("SECRET_KEY")
        self.key_id = os.getenv("KEY_ID")
        self._token: AccessToken | None = None

        if not self.secret_key or not self.key_id:
            raise ValueError("SECRET_KEY and KEY_ID must be set")

    def get_token(self) -> str:
        if self._token is None or self._token.is_expired():
            self._token = self._refresh_token()
        return self._token.value

    def invalidate(self) -> None:
        self._token = None

    def _refresh_token(self) -> AccessToken:
        response = requests.post(
            f"{self.base_url}/intapi/v1/auth",
            json={"secret": self.secret_key, "id": self.key_id},
        )

        if response.status_code != 200:
            raise Exception(
                f"Failed to get API key: {response.status_code} {response.text}"
            )

        token = response.json()["data"]["token"]

        return AccessToken(
            value=token, expires_at=datetime.utcnow() + timedelta(minutes=40)
        )


from .constants import get_constants_for_category


def extract_body_type(description: str) -> str:
    if not description:
        return ""

    base = description.split("•")[0]

    base = re.sub(r"^\s*\d+\s*", "", base)

    return base.strip()


def get_body_type_key(description: str, body_types: dict) -> str | None:
    if not description:
        return None

    body_name = extract_body_type(description)

    for key, names in body_types.items():
        if body_name in names:
            return key

    return None


def get_fuel_type_key(fuel_type: str, fuel_types: dict) -> str | None:
    if not fuel_type:
        return None

    for key, names in fuel_types.items():
        if fuel_type in names:
            return key

    return None


def get_transmission_type_key(
    transmission: str, transmission_types: dict
) -> str | None:
    if not transmission:
        return None

    for key, names in transmission_types.items():
        if transmission in names:
            return key

    return None


def get_mark_id(brand: str, brands: dict) -> str | None:
    if not brand:
        return None

    for key, names in brands.items():
        if brand in names:
            return key

    return None


def get_model_id(model: str, models: dict, brand_id: str | None = None) -> str | None:
    """
    Знаходить ID моделі за назвою.

    Args:
        model: Назва моделі (наприклад "Citan")
        models: Словник моделей format_3_5t_models (brand_id -> {model_id: model_name})
        brand_id: Опціональний ID бренду для пошуку тільки в конкретному бренді

    Returns:
        ID моделі або None, якщо не знайдено
    """
    if not model:
        return None

    if brand_id:
        # Шукаємо тільки в конкретному бренді
        brand_models = models.get(brand_id, {})
        for model_id, model_name in brand_models.items():
            if (
                model_name.lower() == model.lower()
                or model.lower() in model_name.lower()
            ):
                return model_id
    else:
        for brand_models in models.values():
            for model_id, model_name in brand_models.items():
                if (
                    model_name.lower() == model.lower()
                    or model.lower() in model_name.lower()
                ):
                    return model_id

    return None


def get_color_type_key(color: str, color_types: dict) -> str | None:
    if not color:
        return None

    for key, names in color_types.items():
        if color in names:
            return key

    return None


def get_drive_type_key(drive_type: str, drive_types: dict) -> str | None:
    if not drive_type:
        return None

    for key, names in drive_types.items():
        if drive_type in names:
            return key

    return None


def prepare_car_data_for_truck_market_api(
    car: Car, link_car_type: str | None = None
) -> dict:
    """
    Готує дані авто для TruckMarket API. Набір констант (brands, models, …) вибирається
    за категорією батьківського лінка (link_car_type = Link.car_type). Поки тільки 3.5т.
    """
    const = get_constants_for_category(link_car_type)
    body_type_key = get_body_type_key(car.description, const["body_types"])
    fuel_type_key = get_fuel_type_key(car.fuel_type, const["fuel_types"])
    transmission_type_key = get_transmission_type_key(
        car.transmission, const["transmission_types"]
    )
    mark_id = get_mark_id(car.brand, const["brands"])
    model_id = get_model_id(car.model, const["models"], mark_id)

    # Витягуємо об'єм двигуна та потужність з descEngineEngine
    engine_volume = None
    engine_power = None
    desc_engine = car.car_values.get("descEngineEngine")
    if desc_engine:
        # Розділяємо через кому і беремо [1] (другий елемент) для об'єму
        parts = desc_engine.split(",")
        if len(parts) > 1:
            engine_part = parts[1].strip()  # "4.3 л"
            engine_volume = parse_float(engine_part)  # 4.3

        # Витягуємо потужність з дужок (наприклад "(180 к.с. / 132 кВт)")
        power_match = re.search(r"\((\d+)\s*к\.с\.", desc_engine)
        if power_match:
            engine_power = int(power_match.group(1))  # 180

    # Пробіг в тисячах км
    mileage_thousands = car.mileage

    color_type_key = get_color_type_key(car.color, const["color_types"])
    drive_type = car.car_values.get("descDriveTypeDriveType")
    drive_type_key = (
        get_drive_type_key(drive_type, const["drive_types"]) if drive_type else None
    )
    
    # Базове заповнення параметрів f1..f14
    if link_car_type == "5-15 тон":
        format_f = {
            "f17": model_id,               # Модель
            "f1": body_type_key,           # Тип кузову
            "f2": car.year,                # Рік випуску
            "f3": transmission_type_key,   # Коробка передач
            "f4": mileage_thousands,       # Пробіг
            "f5": fuel_type_key,           # Пальне
            "f6": engine_volume,           # Об’єм двигуна
            "f7": engine_power,            # Потужність двигуна
            "f8": drive_type_key,          # Привід
            "f9": color_type_key,          # Колір
            "f13": 1
        }
        logger.info("Prepared format_f for 5-15т: %s", format_f)
    elif link_car_type == "3-5 тон":
        format_f = {
            "f1": body_type_key,
            "f3": fuel_type_key,
            "f4": engine_power,
            "f5": 1,
            "f7": car.year,
            "f8": model_id,
            "f9": engine_volume,
            "f10": mileage_thousands,
            "f12": transmission_type_key,
            "f13": color_type_key,
            "f14": drive_type_key,
        }

        if mark_id == "4222" and model_id is not None:
            format_f["f2"] = model_id
            format_f["f8"] = None
    else:
        raise ValueError(f"Unsupported link_car_type: {link_car_type}")

    # Спеціальне правило для Citroen: модель має бути в полі f2, а не f8.
    # Це стосується всіх Citroen (mark_id == "4222").
            
    user_id = os.getenv("USER_ID")
    company_id = os.getenv("COMPANY_ID")

    # Якщо короткий опис містить символ "•", він, скоріше за все, технічний
    # (типу "Вантажний фургон • ..."), тому для детального опису віддаємо
    # тільки full_description або "чистий" descr_prep.
    descr_prep = car.description or ""
    if "•" in descr_prep:
        descr_prep = ""

    description = car.full_description or descr_prep or ""
    price = car.price
    price_curr = 3

    # Назва оголошення – бренд + модель + рік
    title_parts = [
        part
        for part in [car.brand, car.model, str(car.year) if car.year else None]
        if part
    ]
    title_uk = " ".join(title_parts) if title_parts else "Авто"

    # Назва міста (формат: "UA, Рівненська обл., Дубно, 34272" — витягуємо "Дубно" через re)
    city_name = None
    if car.location and car.location.strip():
        loc = car.location.strip()
        # Формат скрізь: країна, область, місто, індекс — третє поле = місто
        match = re.match(r"^[^,]+, [^,]+, ([^,]+)(?:,|$)", loc)
        if match:
            city_name = match.group(1).strip()
        elif "," in loc:
            parts = [p.strip() for p in loc.split(",") if p.strip()]
            if len(parts) >= 3:
                city_name = parts[2]

    # Категорія для 3.5т – поки що константа, можна винести в env
    # ID бренду для TruckMarket (категорія / марка)
    # Якщо не вдалося знайти в мапі — беремо значення з env як запасний варіант.
    cat_id_env = os.getenv("TRUCK_CAT_ID")
    if mark_id is not None:
        cat_id = int(mark_id)
    elif cat_id_env is not None:
        cat_id = int(cat_id_env)
    else:
        cat_id = None

    return {
        "car_id": car.id,
        "car_photo_path": car.path_to_images,
        "user_id": int(user_id) if user_id is not None else None,
        "company": int(company_id) if company_id is not None else None,
        "cat_id": cat_id,
        "title_uk": title_uk,
        "descr_uk": description,
        "price": price,
        "price_curr": price_curr,
        "geo_city_name": city_name,
        "format_f": format_f,
    }
