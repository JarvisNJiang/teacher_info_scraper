from flask import Flask
from src.config import Config
from .routes import main as main_blueprint
import logging
import os

def create_app():
    template_dir = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(template_dir, 'templates')
    
    app = Flask(__name__, template_folder=template_dir)
    app.config.from_object(Config)
    
    # 设置日志
    logging.basicConfig(filename='app.log', level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    
    app.register_blueprint(main_blueprint)

    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)