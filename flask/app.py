import sys
import os

# Додаємо корінь проекту до шляху для правильних імпортів
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Імпортуємо Flask БІБЛІОТЕКУ (не папку)
import flask as flask_lib
Flask = flask_lib.Flask
request = flask_lib.request
jsonify = flask_lib.jsonify
render_template_string = flask_lib.render_template_string

# Імпортуємо налаштування
import importlib.util
settings_path = os.path.join(os.path.dirname(__file__), "config", "settings.py")
spec = importlib.util.spec_from_file_location("flask_config_settings", settings_path)
settings_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings_module)
DevelopmentConfig = settings_module.DevelopmentConfig

from crud.crud_link.crud import create_new_link
from app.scraper.scraper_service import run_scraper_for_link

app = Flask(__name__)

# Шаблон HTML форми
UPLOAD_LINK_FORM = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Завантаження лінка для парсингу</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
        }
        h1 {
            color: #333;
            margin-bottom: 30px;
            text-align: center;
            font-size: 28px;
        }
        .form-group {
            margin-bottom: 25px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            color: #555;
            font-weight: 600;
            font-size: 14px;
        }
        input[type="text"],
        select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s;
        }
        input[type="text"]:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        button:active {
            transform: translateY(0);
        }
        .message {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            font-weight: 500;
        }
        .success {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .error {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .info {
            background-color: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 Завантаження лінка для парсингу</h1>
        <form method="POST" action="/upload-link">
            <div class="form-group">
                <label for="link">URL лінка для парсингу:</label>
                <input 
                    type="text" 
                    id="link" 
                    name="link" 
                    placeholder="https://auto.ria.com/uk/search/..." 
                    required
                >
            </div>
            
            <div class="form-group">
                <label for="category">Категорія:</label>
                <select id="category" name="category" required>
                    <option value="">Оберіть категорію</option>
                    <option value="3-5 тон">3-5 тон</option>
                    <option value="5-15 тон">5-15 тон</option>
                    <option value="Тягач +">Тягач +</option>
                </select>
            </div>
            
            <div class="form-group">
                <label for="owner">Власник (текст):</label>
                <input 
                    type="text" 
                    id="owner" 
                    name="owner" 
                    placeholder="Введіть назву власника"
                >
            </div>
            
            <button type="submit">🚀 Запустити парсер</button>
        </form>
        
        {% if message %}
        <div class="message {{ message_type }}">
            {{ message }}
        </div>
        {% endif %}
    </div>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(UPLOAD_LINK_FORM)


@app.route("/upload-link", methods=["GET", "POST"])
def upload_link():
    if request.method == "GET":
        return render_template_string(UPLOAD_LINK_FORM)
    
    # POST запит
    url = request.form.get("link", "").strip()
    category = request.form.get("category", "").strip()
    owner = request.form.get("owner", "").strip()
    
    if not url:
        return render_template_string(
            UPLOAD_LINK_FORM,
            message="Помилка: URL лінка обов'язковий",
            message_type="error"
        ), 400
    
    if not category:
        return render_template_string(
            UPLOAD_LINK_FORM,
            message="Помилка: Оберіть категорію",
            message_type="error"
        ), 400
    
    try:
        # Створюємо лінк в БД
        link_obj = create_new_link(url, category=category if category else None, owner=owner if owner else None)
        
        # Запускаємо парсер в окремому потоці
        run_scraper_for_link(url, link_obj.id)
        
        return render_template_string(
            UPLOAD_LINK_FORM,
            message=f"✅ Лінк успішно додано! ID: {link_obj.id}. Парсер запущено в фоновому режимі.",
            message_type="success"
        )
    except Exception as e:
        return render_template_string(
            UPLOAD_LINK_FORM,
            message=f"❌ Помилка: {str(e)}",
            message_type="error"
        ), 500


@app.route("/links", methods=["POST"])
def create_link_api():
    """API endpoint для створення лінка (JSON)"""
    data = request.get_json(silent=True) or {}
    url = data.get("link", "").strip()
    category = data.get("category", "").strip()
    owner = data.get("owner", "").strip()

    if not url:
        return jsonify({"error": "link is required"}), 400

    try:
        link_obj = create_new_link(
            url, 
            category=category if category else None, 
            owner=owner if owner else None
        )
        
        # Запускаємо парсер в окремому потоці
        run_scraper_for_link(url, link_obj.id)
        
        return jsonify(
            {
                "id": link_obj.id,
                "link": link_obj.link,
                "category": link_obj.category,
                "owner": link_obj.owner,
                "last_processed_at": link_obj.last_processed_at.isoformat() if link_obj.last_processed_at else None,
            }
        ), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    config = DevelopmentConfig()
    app.config.from_object(config)
    app.run(debug=True)
