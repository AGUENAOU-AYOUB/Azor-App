from flask import Flask
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
import os

load_dotenv()

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'change-me')
    csrf.init_app(app)

    from .auth import auth_bp
    from .routes import main_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    return app
