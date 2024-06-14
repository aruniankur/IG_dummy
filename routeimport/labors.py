from flask import request, jsonify, send_from_directory
from models import Labor, Data, BGProcess
from celery import shared_task
import pandas as pd
from flask import request
from models import db, Data, Category
import datetime
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from routeimport.decorators import requires_role, get_segment, createjson
import os
from bgtasks import resourceMasterUpload
import xlsxwriter


class labors(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def get(self):
        current_user = get_jwt_identity()
        try:
            labors = Labor.query.filter_by(data_id=current_user['data']).all()
            segment = get_segment(request, current_user['data'])
            return {"labors": createjson(labors), "segment": segment}, 200
        except:
            return {"message":"try again"}, 401

class addlabor(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        l_name = data.get("l_name")
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
    @jwt_required()
    @requires_role(['MASTERS'],1)
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
    @jwt_required()
    @requires_role(['MASTERS'],0)
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
        return jsonify(results)
    
class NewLaborResource(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def get(self):
        #/newlabor?download=YES
        download_stat = request.args.get("download")
        if download_stat == "YES":
            direct = os.path.join(os.getcwd(), 'downloads')
            list_files = os.listdir(direct)
            for file in list_files:
                path1 = os.path.join(direct, file)
                os.remove(path1)
            file_name = "labor_format" + ".xlsx"
            direct2 = os.path.join(direct, file_name)
            workbook = xlsxwriter.Workbook(direct2)
            worksheet = workbook.add_worksheet()
            worksheet.write(0, 0, "NAME")
            worksheet.write(0, 1, "SALARY")
            workbook.close()
            return send_from_directory(directory=direct, path=file_name)

        return {"message": "Invalid GET request"}, 400
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        if 'file' not in request.files:
            return {"message": "No file part in the request"}, 400
        f = request.files['file']
        if f.filename == '':
            return {"message": "No selected file"}, 400
        try:
            direct = os.path.join(os.getcwd(), 'uploads')
            list_files = os.listdir(direct)
            for file in list_files:
                path1 = os.path.join(direct, file)
                os.remove(path1)
            file_path = os.path.join(direct, f.filename)
            f.save(file_path)
        except Exception as e:
            return {"message": f"File upload file. An error occurred: {e}"}, 500
        try:
            result = resourceMasterUpload.delay(current_user['data'], file_path)
        except:
            return {"message": "background task failed"}, 400
        database = Data.query.filter_by(id=current_user['data']).first()
        bg_process = BGProcess(process_id=result.id, name="Resource Master Upload", database=database)
        db.session.add(bg_process)
        db.session.commit()

        return {"message": "File uploaded and background processing started", "bgtaskid": result.id}, 201