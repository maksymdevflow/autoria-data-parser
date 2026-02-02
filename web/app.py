import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix

from web.config.settings import DevelopmentConfig
from web.crud.crud_link.crud import (
    create_new_link,
    get_links,
    get_links_grouped_by_owner,
    get_link_by_id,
    get_owners_list,
    get_links_for_filter,
)
from web.crud.crud_car.crud import (
    get_cars,
    get_car_by_id,
    update_car,
    bulk_update_processed_status,
    get_statistics,
    get_statistics_filtered,
    search_cars,
    get_car_with_owner,
)
from web.crud.crud_process_run.crud import (
    get_process_run_by_id,
    get_process_runs,
    get_process_run_stats,
)
from functions.process_monitor import TASK_NAMES
from tasks.config import (
    process_link_car_urls,
    parse_links_to_create,
    delete_link as delete_link_task,
    process_car_add_truck_market,
    process_links_to_delete,
)

app = Flask(__name__)
config = DevelopmentConfig()
app.config.from_object(config)

# За nginx: коректні https-посилання та Host (X-Forwarded-Proto, X-Forwarded-For, Host)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


@app.route("/")
def index():
    return render_template("upload.html")


@app.route("/upload-link", methods=["GET", "POST"])
def upload_link():
    if request.method == "GET":
        return render_template("upload.html")

    url = request.form.get("link", "").strip()
    car_type = request.form.get("category", "").strip()
    owner = request.form.get("owner", "").strip()

    if not url:
        return render_template(
            "upload.html",
            message="URL посилання обовʼязковий",
            message_type="error",
        ), 400

    if not car_type:
        return render_template(
            "upload.html",
            message="Оберіть категорію",
            message_type="error",
        ), 400

    try:
        link_obj = create_new_link(
            url,
            car_type=car_type or None,
            owner=owner or None,
        )
        process_link_car_urls.delay(link_obj.id)
        return render_template(
            "upload.html",
            message=f"Посилання додано (ID: {link_obj.id}). Задачу відправлено в чергу.",
            message_type="success",
        )
    except Exception as e:
        return render_template(
            "upload.html",
            message=f"Помилка: {str(e)}",
            message_type="error",
        ), 500


@app.route("/run-parse-to-create", methods=["POST"])
def run_parse_to_create():
    """Запустити парсер по links_to_create вручну (без beat). Відправляє задачу в чергу Celery."""
    try:
        t = parse_links_to_create.delay()
        return jsonify(
            {"status": "ok", "message": "Задачу відправлено в чергу", "task_id": t.id}
        ), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _week_start_utc():
    """Початок поточного тижня (понеділок 00:00 Europe/Kiev) у naive UTC для порівняння з last_recheck_at."""
    from datetime import datetime, timezone, timedelta
    from zoneinfo import ZoneInfo
    kiev = ZoneInfo("Europe/Kiev")
    now_kiev = datetime.now(kiev)
    days = now_kiev.weekday()
    monday = (now_kiev.replace(hour=0, minute=0, second=0, microsecond=0)
              - timedelta(days=days))
    return monday.astimezone(timezone.utc).replace(tzinfo=None)


@app.route("/links")
def links_list():
    raw = request.args.get("parse_status", "").strip()
    parse_status = raw.lower() if raw else None
    groups = get_links_grouped_by_owner(parse_status=parse_status)
    week_start_utc = _week_start_utc()  # для колонки «Цього тижня» (✓ якщо last_recheck_at >= week_start_utc)
    return render_template(
        "links.html",
        groups=groups,
        parse_status=parse_status,
        week_start_utc=week_start_utc,
    )


@app.route("/links/<int:link_id>")
def link_detail(link_id):
    """Деталі лінка: авто, to create, to delete у вкладках."""
    link = get_link_by_id(link_id)
    if not link:
        return "Link not found", 404
    week_start_utc = _week_start_utc()
    return render_template("link_detail.html", link=link, week_start_utc=week_start_utc)


@app.route("/links/<int:link_id>/send-to-delete", methods=["POST"])
def send_link_to_delete(link_id):
    """Поставити лінк в чергу на видалення: Celery видалить авто з TruckMarket і лінк з БД."""
    from database.db import SessionLocal
    from database.models import Link

    db = SessionLocal()
    try:
        link = db.query(Link).filter(Link.id == link_id).first()
        if not link:
            return jsonify({"error": "Link not found"}), 404
        task = delete_link_task.delay(link_id)
        return jsonify(
            {
                "status": "ok",
                "message": "Посилання поставлено в чергу на видалення. Celery видалить авто з сайту (TruckMarket) і посилання з БД.",
                "task_id": task.id,
            }
        ), 200
    finally:
        db.close()


@app.route("/stats")
def stats_page():
    """Статистика за період: день/тиждень/місяць, по всіх авто / по власнику / по одному посиланню."""
    period = request.args.get("period", "week").strip().lower()
    if period not in ("day", "week", "month"):
        period = "week"
    scope = request.args.get("scope", "all").strip().lower()
    if scope not in ("all", "owner", "link"):
        scope = "all"
    owner = request.args.get("owner", "").strip() or None
    link_id = request.args.get("link_id", "").strip()
    link_id = int(link_id) if link_id.isdigit() else None

    owners = get_owners_list()
    links_list = get_links_for_filter()

    stats = get_statistics_filtered(
        period=period,
        owner=owner if scope == "owner" else None,
        link_id=link_id if scope == "link" else None,
    )
    return render_template(
        "stats.html",
        stats=stats,
        period=period,
        scope=scope,
        owner=owner,
        link_id=link_id,
        owners=owners,
        links_list=links_list,
    )


@app.route("/admin/processes")
def processes_monitor():
    """Адмін-панель моніторингу процесів: останні запуски тасків, фільтри, статуси."""
    task_name = request.args.get("task_name", "").strip() or None
    status = request.args.get("status", "").strip() or None
    runs = get_process_runs(task_name=task_name, status=status, limit=150)
    stats = get_process_run_stats()
    return render_template(
        "processes.html",
        runs=runs,
        stats=stats,
        task_names=TASK_NAMES,
        task_name=task_name,
        status=status,
    )


@app.route("/admin/processes/<int:run_id>")
def process_run_detail(run_id: int):
    """Сторінка деталей запуску: інфо + історія логів по тасці."""
    run = get_process_run_by_id(run_id)
    if not run:
        return "Запуск не знайдено", 404
    return render_template(
        "process_run_detail.html",
        run=run,
        task_names=TASK_NAMES,
    )


@app.route("/admin")
def admin_panel():
    status = request.args.get("status", "").strip() or None
    search = request.args.get("search", "").strip() or None
    page = int(request.args.get("page", 1))
    stats = get_statistics()
    result = get_cars(status=status, search=search, page=page, per_page=50)
    return render_template(
        "admin.html",
        cars=result["cars"],
        stats=stats,
        status=status,
        search=search,
        page=result["page"],
        pages=result["pages"],
    )


@app.route("/links", methods=["POST"])
def create_link_api():
    """API: створення лінка (JSON)."""
    data = request.get_json(silent=True) or {}
    url = data.get("link", "").strip()
    car_type = data.get("category", "").strip()
    owner = data.get("owner", "").strip()

    if not url:
        return jsonify({"error": "link is required"}), 400

    try:
        link_obj = create_new_link(
            url,
            car_type=car_type or None,
            owner=owner or None,
        )
        process_link_car_urls.delay(link_obj.id)
        return jsonify(
            {
                "id": link_obj.id,
                "link": link_obj.link,
                "car_type": link_obj.car_type,
                "owner": link_obj.owner,
                "last_processed_at": link_obj.last_processed_at.isoformat()
                if link_obj.last_processed_at
                else None,
            }
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/car/<int:car_id>", methods=["GET"])
def get_car(car_id):
    car = get_car_by_id(car_id)
    if not car:
        return jsonify({"error": "Car not found"}), 404
    return jsonify(
        {
            "id": car.id,
            "brand": car.brand,
            "year": car.year,
            "price": car.price,
            "mileage": car.mileage,
            "fuel_type": car.fuel_type,
            "transmission": car.transmission,
            "color": car.color,
            "location": car.location,
            "description": car.description or "",
            "processed_status": car.processed_status.value
            if car.processed_status
            else None,
            "is_published": car.is_published,
            "link_path": car.link_path,
            "link_id": car.link_id,
            "truck_car_id": car.truck_car_id,
        }
    )


@app.route("/admin/car/<int:car_id>/send-to-delete", methods=["POST"])
def send_car_to_delete(car_id):
    """Додає авто в чергу на видалення з сайту (links_to_delete). Celery потім викличе API TruckMarket."""
    from database.db import SessionLocal
    from database.models import Car, LinkToDelete, StatusLinkChange

    db = SessionLocal()
    try:
        car = db.query(Car).filter(Car.id == car_id).first()
        if not car:
            return jsonify({"error": "Car not found"}), 404
        if not car.truck_car_id:
            return jsonify(
                {"error": "У авто немає truck_car_id, його немає на сайті"}
            ), 400
        existing = (
            db.query(LinkToDelete).filter(LinkToDelete.link == car.link_path).first()
        )
        if existing:
            if existing.status == StatusLinkChange.COMPLETED:
                existing.status = StatusLinkChange.PROCESS
                db.commit()
                return jsonify(
                    {"status": "ok", "message": "Повторно додано в чергу на видалення"}
                ), 200
            return jsonify(
                {"status": "already_queued", "message": "Вже в черзі на видалення"}
            ), 200
        db.add(
            LinkToDelete(
                parent_link_id=car.link_id,
                link=car.link_path,
                status=StatusLinkChange.PROCESS,
            )
        )
        db.commit()
        return jsonify(
            {"status": "ok", "message": "Додано в чергу на видалення з сайту"}
        ), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/admin/cars/bulk-send-to-delete", methods=["POST"])
def bulk_send_to_delete():
    """Множинне додавання обраних авто в чергу на видалення з сайту (links_to_delete)."""
    from database.db import SessionLocal
    from database.models import Car, LinkToDelete, StatusLinkChange

    data = request.get_json(silent=True) or {}
    car_ids = data.get("car_ids", [])
    if not car_ids:
        return jsonify({"error": "car_ids обовʼязковий"}), 400

    db = SessionLocal()
    try:
        added = 0
        skipped_no_truck = 0
        skipped_already = 0
        for car_id in car_ids:
            car = db.query(Car).filter(Car.id == car_id).first()
            if not car:
                continue
            if not car.truck_car_id:
                skipped_no_truck += 1
                continue
            existing = (
                db.query(LinkToDelete)
                .filter(LinkToDelete.link == car.link_path)
                .first()
            )
            if existing:
                if existing.status == StatusLinkChange.COMPLETED:
                    existing.status = StatusLinkChange.PROCESS
                    added += 1
                else:
                    skipped_already += 1
                continue
            db.add(
                LinkToDelete(
                    parent_link_id=car.link_id,
                    link=car.link_path,
                    status=StatusLinkChange.PROCESS,
                )
            )
            added += 1
        db.commit()
        if added:
            process_links_to_delete.delay()
        parts = [f"Додано в чергу: {added}"]
        if skipped_no_truck:
            parts.append(f"без truck_car_id: {skipped_no_truck}")
        if skipped_already:
            parts.append(f"вже в черзі: {skipped_already}")
        return jsonify(
            {
                "status": "ok",
                "added": added,
                "skipped_no_truck": skipped_no_truck,
                "skipped_already": skipped_already,
                "message": ". ".join(parts),
            }
        )
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@app.route("/admin/car/<int:car_id>", methods=["PUT"])
def update_car_route(car_id):
    data = request.get_json() or {}
    try:
        car = update_car(car_id, data)
        if not car:
            return jsonify({"error": "Car not found"}), 404
        return jsonify({"id": car.id, "brand": car.brand, "message": "OK"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/admin/cars/bulk-update-status", methods=["POST"])
def bulk_update_status_route():
    """Множинна зміна статусу обраних авто."""
    data = request.get_json(silent=True) or {}
    car_ids = data.get("car_ids", [])
    processed_status = (data.get("processed_status") or "").strip()
    if not car_ids:
        return jsonify({"error": "car_ids обовʼязковий"}), 400
    if not processed_status:
        return jsonify({"error": "processed_status обовʼязковий"}), 400
    try:
        updated = bulk_update_processed_status(car_ids, processed_status)
        return jsonify({"status": "ok", "updated": updated, "message": f"Оновлено {updated} авто"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/car-search")
def car_search_page():
    """Сторінка пошуку авто: за truck_car_id або за параметрами, з підказками (укр/анг)."""
    return render_template("car_search.html")


@app.route("/api/car-search/suggest", methods=["GET"])
def car_search_suggest():
    """Підказки для пошуку: q — рядок (марка, модель, власник, id, truck_car_id). Марка/модель в БД англійською."""
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify([])
    limit = min(int(request.args.get("limit", 15)), 25)
    results = search_cars(q=q, limit=limit, for_suggest=True)
    return jsonify(results)


@app.route("/api/car-search", methods=["GET"])
def car_search_api():
    """Пошук авто: q (текст або id/truck_car_id) або truck_car_id. Повна інфа з власником і посиланням на AutoRia."""
    q = (request.args.get("q") or "").strip()
    truck_car_id = request.args.get("truck_car_id", type=int)
    if truck_car_id is not None:
        results = search_cars(truck_car_id=truck_car_id, limit=50)
    elif q:
        results = search_cars(q=q, limit=50)
    else:
        results = []
    return jsonify(results)


@app.route("/api/car/<int:car_id>/detail", methods=["GET"])
def car_detail_api(car_id):
    """Повна інфа по одному авто (власник, посилання AutoRia, усі поля)."""
    detail = get_car_with_owner(car_id)
    if not detail:
        return jsonify({"error": "Car not found"}), 404
    return jsonify(detail)


@app.route("/admin/stats", methods=["GET"])
def admin_stats():
    return jsonify(get_statistics())


@app.route("/admin/delete-cars", methods=["POST"])
def delete_cars_route():
    from database.db import SessionLocal
    from database.models import Car

    data = request.get_json(silent=True) or {}
    car_ids = data.get("car_ids", [])
    link_id = data.get("link_id")

    if not car_ids and not link_id:
        return jsonify({"error": "car_ids or link_id required"}), 400

    db = SessionLocal()
    try:
        if car_ids:
            db.query(Car).filter(Car.id.in_(car_ids)).delete(synchronize_session=False)
        if link_id:
            db.query(Car).filter(Car.link_id == link_id).delete(
                synchronize_session=False
            )
        db.commit()
        return jsonify({"status": "deleted", "message": "OK"}), 200
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


if __name__ == "__main__":
    app.run(debug=config.DEBUG)
