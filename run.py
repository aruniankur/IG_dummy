from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from route import register_routes 
from models import db
import os

app = Flask(__name__, template_folder='templates')

#this is the local data

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/intaligendb2'

#this the public data

#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://intaligen2dummy_user:pb9897lDoJOHzvZTvZfzDTMkw17Wi0Oy@dpg-cp686fg21fec738d8vqg-a.oregon-postgres.render.com/intaligen2dummy'
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Intaligen1234@intaligen-dev-db.cp2ww2yimaft.ap-south-1.rds.amazonaws.com:5432/postgres'
db.init_app(app)
register_routes(app, db)
migrate = Migrate(app, db)
if __name__ == '__main__': 
    app.run(debug=True)
    