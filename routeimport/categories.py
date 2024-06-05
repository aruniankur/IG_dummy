from flask import request
from models import db, Data, Category
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from routeimport.decorators import requires_role, get_segment, createjson


class catogory(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def get(self):
        current_user = get_jwt_identity()
        try:
            database = Data.query.filter_by(id=current_user["data"]).first()
            CATEGORIES = Category.query.filter_by(database=database).all()
            segment = get_segment(request, current_user['data'])
            return {"categories": createjson(CATEGORIES), "segment": segment}, 200
        except:
            return {"message":"try again"} , 401


class Addcategory(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
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
    @requires_role(['MASTERS'],1)
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
    