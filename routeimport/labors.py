from flask import Flask, render_template, request, jsonify
from models import Labor, Data, BGProcess
from celery import shared_task
import pandas as pd
from flask import request
from models import db, Data, Category
import datetime
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
    
#----------------------------------------------------------------

class labors(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],["VIEWER","EDITOR"],['MASTERS'])
    def get(self):
        current_user = get_jwt_identity()
        try:
            labors = Labor.query.filter_by(data_id=current_user['data']).all()
            segment = get_segment(request, current_user['data'])
            return {"labors": createjson(labors), "segment": segment}, 200
        except:
            return {"message":"try again"}, 401

class addlabor(Resource):
    @jwt_required
    @requires_role(['MASTERS'],["EDITOR"],['MASTERS'])
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        l_name = data.get("l_name");
        l_salary = data.get("l_salary")
        l_code = data.get("l_code")
        l_type = data.get("l_type")
        if l_name and l_salary:
            database=Data.query.filter_by(id=current_user['data']).first()
            labor_check = Labor.query.filter_by(name=l_name, database=database).first()
            if not labor_check:
                l_code = l_code if l_code else "NA"
                l_type = l_type if l_type else "WORKER"
                labor1=Labor(name=l_name, salary=l_salary, database=database, code=l_code, gender = l_type)
                db.session.add(labor1)
                db.session.commit()
                return {"message": "Labor added successfully"}, 200
            else:
                return {"message": "Labor Name already exists! Try a new name"}, 401
        return {"message": "please check input"}, 401

class editlabor(Resource):
    @jwt_required
    @requires_role(['MASTERS'],["EDITOR"],['MASTERS'])
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database=Data.query.filter_by(id=current_user['data']).first()
        edit_ids=data.get("edit_ids[]",[])
        edit_names = data.get("edit_names[]",[])
        edit_salaries = data.get("edit_salaries[]",[])
        edit_codes = data.get('edit_codes[]',[])
        edit_types = data.get('edit_types[]',[])
        if len(edit_ids):
            res = []
            for i in range(len(edit_ids)):
                labor_check1 = Labor.query.filter_by(name=edit_names[i], database=database).first()
                labor_check2 = Labor.query.filter_by(id=edit_ids[i], database=database).first()
                if labor_check1 and labor_check2 and labor_check1.id != labor_check2.id:
                    res.append(f"labor Name Already Exists for {edit_names[i]}!")
                if labor_check2:
                    labor2 = Labor.query.filter_by(id=edit_ids[i]).first()
                    labor2.name=edit_names[i]
                    labor2.salary=edit_salaries[i]
                    labor2.code = edit_codes[i]
                    labor2.gender = edit_types[i]
                    db.session.commit()
                else:
                    res.append(f"labor does not Exists for name {edit_names[i]}!")
            return {"message": "labor detail edited", "result": res} ,200
        
class searchlabor(Resource):
    @jwt_required
    @requires_role(['MASTERS'],["VIEWER","EDITOR"],['MASTERS'])
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database=Data.query.filter_by(id=current_user['data']).first()
        k = int(data.get('k', 10))  # Default value is 10
        labor_name =data.get('name',None)
        labor_id = data.get('id',None)
        if labor_name:
            if k>0:
                labors = Labor.query.filter(Labor.name.ilike(f'%{labor_name}%'), Labor.data_id == current_user["data"]).limit(k).all()
            else:
                labors = Labor.query.filter(Labor.name.ilike(f'%{labor_name}%'), Labor.data_id == current_user["data"]).all()
        else:
            labors = Labor.query.filter_by(database=database).all()
        if labor_id:
            labors = Labor.query.filter_by(id =labor_id, data_id = current_user["data"]).all()
        results = []
        for labor in labors:
            results.append({'id': labor.id, 'name': labor.name, 'salary':labor.salary})
        print(results)
        return jsonify(results), 200