from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate



# from flask import Flask, jsonify
# from flask_sqlalchemy import SQLAlchemy

# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:1234@localhost:5432/dummy'


# db = SQLAlchemy(app)

# class Task(db.Model):
#     __tablename__ = 'person'
#     pid = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.Text, nullable=False)
#     age = db.Column(db.Integer)
#     job = db.Column(db.Text)
    
#     def __repr__(self):
#         return f'Person {self.name} {self.age} {self.job}'

# with app.app_context():
#     db.create_all()

# @app.route('/')
# def index():
#     return jsonify({'key':'hello'})

# @app.route('/tasks')
# def index():
#     task = Task.query.all()
#     return jsonify(task)

# if __name__ == '__main__':
#     app.run(debug=True)