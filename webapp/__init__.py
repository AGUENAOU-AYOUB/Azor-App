from flask import Flask, g, session
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

    @app.before_request
    def set_language():
        g.lang = session.get('lang', 'en')

    @app.context_processor
    def inject_translator():
        translations = {
            'home': {'en': 'Home', 'fr': 'Accueil'},
            'percentage': {'en': 'Percentage', 'fr': 'Pourcentage'},
            'variant': {'en': 'Variant', 'fr': 'Variante'},
            'logout': {'en': 'Logout', 'fr': 'Déconnexion'},
            'language': {'en': 'Français', 'fr': 'English'},
            'login': {'en': 'Login', 'fr': 'Connexion'},
            'username': {'en': 'Username', 'fr': "Nom d'utilisateur"},
            'password': {'en': 'Password', 'fr': 'Mot de passe'},
        }

        def t(key):
            lang = g.get('lang', 'en')
            return translations.get(key, {}).get(lang, key)

        return dict(t=t)

    return app
