from flask import Flask
from routes.main import main_bp
from routes.load_cml import load_cml_bp

app = Flask(__name__)

# Register Blueprints
app.register_blueprint(main_bp)
app.register_blueprint(load_cml_bp)

if __name__ == '__main__':
    app.run(debug=True)