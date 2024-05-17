
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from routes import register_routes 
from models import db
import os

app = Flask(__name__, template_folder='templates')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/dummy'
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/intaligen_db'
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://intaligen:RlTBS2h3UfRDYtcoqRPJgklcwvXm3yuM@dpg-cp2fgm8l6cac73de0ra0-a.oregon-postgres.render.com/intaligen_dummy'
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
db.init_app(app)
register_routes(app, db)
migrate = Migrate(app, db)
if __name__ == '__main__': 
    app.run(debug=True)
    