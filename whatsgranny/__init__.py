import os
import yaml
from flask import Flask

# needs to load so that all environment variables are set when the submodules are loaded
with open("dev.yaml", "r") as f:
    data = yaml.safe_load(f)
    for key, value in data.items():
        os.environ[key] = str(value)

from .app.routes import main


def create_app():
    app = Flask(__name__)
    app.register_blueprint(main)
    return app
