import os
import logging
import sys
from flask import Flask, jsonify, request
from src.config import DevelopmentConfig, config as config_map
from src.models.database import db
from flask_migrate import Migrate
from src.route.website_route.home import home_bp
from src.route.ai_route.agent import agent_bp
from livekit import api
from dotenv import load_dotenv
from src.models.database import VisitorLog
from src.route.admin_route.admin import admin_bp


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Initialize Flask app
app = Flask(__name__, template_folder="src/templates", static_folder="src/static")
config_name = (os.getenv("FLASK_CONFIG") or os.getenv("FLASK_ENV") or "development").lower()
app_config = config_map.get(config_name, DevelopmentConfig)
app.config.from_object(app_config)
app.secret_key = app.config["SECRET_KEY"]
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

# Initialize database properly
db.init_app(app)
migrate = Migrate(app, db)

# Register Blueprints
app.register_blueprint(home_bp)
app.register_blueprint(agent_bp)

app.register_blueprint(admin_bp)


@app.before_request
def log_visitor():
    if request.endpoint in ("static", None) or request.path in ("/favicon.ico", "/robots.txt"):
        return

    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        country, city = "Unknown", "Unknown"

        # Parse UTM parameters
        utm_source = request.args.get("utm_source")
        utm_medium = request.args.get("utm_medium")
        utm_campaign = request.args.get("utm_campaign")
        utm_term = request.args.get("utm_term")
        utm_content = request.args.get("utm_content")

        # Lookup country/city (optional)
        if ip and not ip.startswith(("127.", "192.168.", "172.")):
            try:
                res = request.get(f"https://ipapi.co/{ip}/json/", timeout=3)
                data = res.json()
                country = data.get("country_name", "Unknown")
                city = data.get("city", "Unknown")
            except Exception:
                pass

        new_log = VisitorLog(
            ip_address=ip,
            country=country,
            city=city,
            user_agent=request.headers.get("User-Agent"),
            referrer=request.referrer,
            path=request.path,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_term=utm_term,
            utm_content=utm_content,
        )

        db.session.add(new_log)
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        print("Visitor logging failed:", e)


@app.after_request
def _log_response(response):
    app.logger.info("Response %s %s -> %s", request.method, request.path, response.status)
    return response

LIVEKIT_URL = "wss://testing-mwtbjpwy.livekit.cloud"
API_KEY = os.getenv("LIVEKIT_API_KEY")
API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Import models after db initialization to avoid circular imports

from src.models.database import Lead, Message, Interaction  # noqa: E402
from src.models.database import User


@app.cli.command("create-admin")
def create_admin():
    """Create a new admin user from the command line."""
    name = input('Name: ').strip()
    email = input('Email: ').strip().lower()
    password = input('Password: ').strip()

    if not name or not email or not password:
        print('All fields are required.')
        return

    with app.app_context():
        if User.query.filter_by(email=email).first():
            print('A user with that email already exists.')
            return
        user = User(name=name, email=email, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f'Admin user {name} <{email}> created.')

if __name__ == '__main__':
    # Run with the debug setting defined by the active configuration
    app.run(debug=app.config.get("DEBUG", False))
