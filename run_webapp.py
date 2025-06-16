import os
from webapp import create_app

app = create_app()

if __name__ == '__main__':
    debug_env = os.getenv('DEBUG', 'False')
    debug = debug_env.lower() in {'1', 'true', 'yes'}
    app.run(host='0.0.0.0', port=5000, debug=debug)