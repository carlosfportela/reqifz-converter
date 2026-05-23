import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    flask_env = os.environ.get('FLASK_ENV', 'development')

    if flask_env == 'development':
        port = int(os.environ.get('PORT', 5000))
        print(f"\n  🛠  Modo: DESENVOLVIMENTO (Flask dev server)")
        print(f"  📍 Acesse: http://localhost:{port}")
        print(f"  ⚠  Para simular produção no Windows: .\\scripts\\start_prod_local.ps1\n")
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        print(
            "\n  ⛔  FLASK_ENV não é 'development'.\n"
            "  Use um servidor WSGI para produção:\n"
            "    Windows : .\\scripts\\start_prod_local.ps1   (Waitress)\n"
            "    OpenShift: gunicorn -c gunicorn.conf.py wsgi:app\n"
        )
