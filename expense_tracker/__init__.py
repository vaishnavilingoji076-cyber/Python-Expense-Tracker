import os
from datetime import datetime
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .db import init_app as init_db_app

csrf = CSRFProtect()


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "local-development-key"),
        DATABASE=str(Path(app.instance_path) / "expenses.sqlite3"),
        CURRENCY_SYMBOL=os.environ.get("CURRENCY_SYMBOL", "₹"),
    )

    if test_config is not None:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db_app(app)
    csrf.init_app(app)

    from .routes import bp

    app.register_blueprint(bp)
    app.jinja_env.filters["money"] = lambda cents: (
        f"{int(cents) // 100:,}.{int(cents) % 100:02d}"
    )
    app.jinja_env.globals["now"] = datetime.now
    app.jinja_env.globals["currency_symbol"] = app.config["CURRENCY_SYMBOL"]
    return app
