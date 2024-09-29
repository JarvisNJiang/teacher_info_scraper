from flask import Flask
from src.config import Config
from .routes import main as main_blueprint
import logging

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # 设置日志
    logging.basicConfig(filename='app.log', level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    
    app.register_blueprint(main_blueprint)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run()