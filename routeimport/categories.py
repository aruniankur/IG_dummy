from flask import request
from models import Data, Category
from datetime import datetime, date
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from routeimport.decorators import requires_role

def get_segment(request, id1):
    try:
        database = Data.query.filter_by(id=id1).first()
        segment = request.path.split('/')
        if segment == '':
            segment = 'index'
        print(database.company.name)
        return segment+[database.company.name]
    except:
        return None
    
def createjson(dbt):
    def convert_to_dict(instance):
        if instance is None:
            return {}
        result = {}
        for key, value in instance.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, (datetime.date, datetime.datetime)):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                result[key] = [convert_to_dict(item) if hasattr(item, '__dict__') else item for item in value]
            elif hasattr(value, '__dict__'):  # Check if value is a SQLAlchemy model instance
                result[key] = convert_to_dict(value)
            else:
                result[key] = value
        return result
    
    if isinstance(dbt, list):
        return [convert_to_dict(item) for item in dbt]
    else:
        return convert_to_dict(dbt)

class catogory(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],["VIEWER","EDITOR"],['MASTERS'])
    def get(self):
        current_user = get_jwt_identity()
        try:
            database = Data.query.filter_by(id=current_user["data"]).first()
            CATEGORIES = Category.query.filter_by(database=database).all()
            segment = get_segment(request, current_user['data'])
            return {"categories": createjson(CATEGORIES), "segment": createjson(segment)}, 200
        except:
            return {"message":"try again"} , 401


class Addcategory(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],["EDITOR"],['MASTERS'])
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        add_category_name = data.get("add_category_name")
        add_category_type = data.get("add_category_type")
        if not database:
            return {"message":"no database releated to user found"}, 401
        if add_category_name and add_category_type:
            check_category = Category.query.filter_by(database=database, name=add_category_name.upper()).first()
            if check_category:
                return {"message": "Category already exists!"}, 302
            new_category = Category(database=database, name=add_category_name.upper(), category_type=add_category_type)
            db.session.add(new_category)
            db.session.commit()
            return {"message": "new category added!"}, 200
        else:
            return {"message": "check input"}, 401
        
        
class editcategory(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],["EDITOR"],['MASTERS'])
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        edit_category_name = data.get("edit_name")
        edit_category_id = data.get("edit_id")
        edit_type = data.get("edit_type")
        if not database:
            return {"message":"no database releated to user found"}, 401
        if edit_category_id and edit_category_name and edit_type:
            try:
                category = Category.query.filter_by(database=database, id =edit_category_id).first()
                category.name=edit_category_name
                category.category_type = edit_type
                db.session.commit()
                return {"message": "edited successfully"}, 200
            except:
                return {"message": "database error"}, 401
        else:
            return {"message": "please check input"}, 401
    