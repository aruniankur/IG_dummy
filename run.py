from flask_migrate import Migrate
from route import register_routes 
from models import db
from config import app
from flasgger import Swagger

#this is the local data

#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/intaligendb2'

#this the public data

#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://intaligen2dummy_user:pb9897lDoJOHzvZTvZfzDTMkw17Wi0Oy@dpg-cp686fg21fec738d8vqg-a.oregon-postgres.render.com/intaligen2dummy'
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Intaligen1234@intaligen-dev-db.cp2ww2yimaft.ap-south-1.rds.amazonaws.com:5432/postgres'
app.config['SQLALCHEMY_BINDS'] = {
    'chatappdb': 'postgresql://postgres:1234@localhost:5432/conversationdb'
}
db.init_app(app)
swagger = Swagger(app)
register_routes(app, db)
migrate = Migrate(app, db)
if __name__ == '__main__': 
    app.run(debug=True, host="0.0.0.0")
    