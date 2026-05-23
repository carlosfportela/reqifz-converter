import os
import logging
from flask import Flask

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def create_app():
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 1GB max para múltiplos arquivos

    @app.after_request
    def add_security_headers(response):
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers.pop('Server', None)
        return response

    with app.app_context():
        from app import routes
        app.register_blueprint(routes.bp)

    return app
