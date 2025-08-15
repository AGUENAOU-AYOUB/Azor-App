from flask import Flask, g, session
from flask_wtf import CSRFProtect
from dotenv import load_dotenv
import os

load_dotenv()

csrf = CSRFProtect()

TRANSLATIONS = {
    'home': {'en': 'Home', 'fr': 'Accueil'},
    'percentage': {'en': 'Percentage', 'fr': 'Pourcentage'},
    'variant': {'en': 'Variant', 'fr': 'Variante'},
    'logout': {'en': 'Logout', 'fr': 'Déconnexion'},
    'language': {'en': 'Français', 'fr': 'English'},
    'login': {'en': 'Login', 'fr': 'Connexion'},
    'username': {'en': 'Username', 'fr': "Nom d'utilisateur"},
    'password': {'en': 'Password', 'fr': 'Mot de passe'},
    'welcome': {'en': 'Welcome', 'fr': 'Bienvenue'},
    'percentage_card_title': {'en': 'Percentage Price Updater', 'fr': 'Mise à jour par pourcentage'},
    'percentage_card_desc': {
        'en': 'Adjust all product prices by a percentage.',
        'fr': 'Ajuster tous les prix des produits par un pourcentage.'
    },
    'variant_card_title': {'en': 'Variant Price Updater', 'fr': 'Mise à jour des variantes'},
    'variant_card_desc': {
        'en': 'Update variant surcharges individually.',
        'fr': 'Mettre à jour chaque supplément de variante individuellement.'
    },
    'baseprice_card_title': {
        'en': 'Base Price Initialization',
        'fr': 'Initialisation du prix de base'
    },
    'baseprice_card_desc': {
        'en': 'Create base_price metafield for all products.',
        'fr': 'Créer le champ base_price pour tous les produits.'
    },
    'percentage_title': {'en': 'Percentage Price Update', 'fr': 'Mise à jour des prix par pourcentage'},
    'enter_percentage': {'en': 'Enter percentage', 'fr': 'Entrez le pourcentage'},
    'run': {'en': 'Run', 'fr': 'Exécuter'},
    'reset': {'en': 'Reset', 'fr': 'Réinitialiser'},
    'update_completed': {'en': 'Update completed!', 'fr': 'Mise à jour terminée !'},
    'reset_completed': {'en': 'Reset completed!', 'fr': 'Réinitialisation terminée !'},
    'variant_title': {'en': 'Variant Price Update', 'fr': 'Mise à jour des prix des variantes'},
    'save_changes': {'en': 'Save Changes', 'fr': 'Enregistrer'},
    'run_update': {'en': 'Run Update', 'fr': 'Exécuter la mise à jour'},
    'price_reset_title': {'en': 'Price Reset', 'fr': 'Réinitialisation des prix'},
    'price_reset_intro': {
        'en': 'This will restore all prices from the last backup file.',
        'fr': 'Ceci restaurera tous les prix depuis la dernière sauvegarde.'
    },
    'run_reset': {'en': 'Run Reset', 'fr': 'Exécuter la réinitialisation'},
    'login_error': {'en': 'Invalid credentials', 'fr': 'Identifiants invalides'},
    'surcharges_saved': {'en': 'Surcharges saved.', 'fr': 'Suppléments enregistrés.'},
    'invalid_value': {
        'en': 'Invalid value for {chain}',
        'fr': 'Valeur invalide pour {chain}'
    },
    'baseprice_title': {
        'en': 'Base Price Initialization',
        'fr': 'Initialisation du prix de base'
    },
    'baseprice_intro': {
        'en': 'Set each product\'s base_price metafield to its current price.',
        'fr': 'Définir le champ base_price de chaque produit sur son prix actuel.'
    },
    'run_baseprice': {
        'en': 'Run Initialization',
        'fr': "Exécuter l'initialisation"
    },
    'baseprice_completed': {
        'en': 'Initialization completed!',
        'fr': 'Initialisation terminée !'
    },
}


def translate(key, lang=None, **kwargs):
    if lang is None:
        lang = g.get('lang', 'en')
    text = TRANSLATIONS.get(key, {}).get(lang, key)
    try:
        return text.format(**kwargs)
    except Exception:
        return text

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv('SECRET_KEY', 'change-me')
    app.config['WTF_CSRF_ENABLED'] = os.getenv('WTF_CSRF_ENABLED', 'true').lower() == 'true'
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
        return dict(t=translate)

    return app
