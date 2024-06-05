from flask import Flask, jsonify, render_template, request,send_from_directory
from models import db, Labor, Item, BOM, Data, ProdchartItem, Inventory, WorkstationJob, WorkstationResource, BGProcess, MobileNumber
from routeimport.decorators import requires_role, get_segment, createjson
import pandas as pd
from celery.result import AsyncResult
import os 
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

table_names = {"ws_jobs":WorkstationJob, "ws_resources":WorkstationResource}


class addrecord(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        fields = data.get('fields')
        table_name = data.get("table_name")
        if current_user["data"]:
            fields['data_id'] = current_user["data"]
        else:
            return jsonify({'message':"User not logged in!"}), 404
        print(table_name)
        if table_name not in table_names.keys():
            return jsonify({'message': f'Table {table_name} not found'}), 404
        table = table_names[table_name]
        record = table(**fields)
        db.session.add(record)
        db.session.commit()
        return jsonify({'message': 'Record added successfully', "record_id":record.id}), 200
    
        
class editrecord(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        table_name = data.get("table_name")
        record_id = data.get("id")
        fields = data.get("fields")
        print(fields)
        table = table_names[table_name]
        if table is None:
            return jsonify({'message': f'Table {table_name} not found'}), 404
        record = table.query.filter_by(database=database, id = record_id).first()
        for field_name, field_value in fields.items():
            setattr(record, field_name, field_value)
        db.session.commit() 
        return jsonify({'message': 'Record updated successfully'}), 200
    

class delete_record(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        data = request.json
        table_name = data.get("table_name")
        record_id = data.get("id")
        table = table_names[table_name]
        if table is None:
            return jsonify({'message': f'Table {table_name} not found'}), 404
        record = table.query.filter_by(database=database, id = record_id).first()
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Record deleted successfully'}) , 200
        
        

class check_status(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        process_id = data.get("process_id")
        if process_id:
            status = AsyncResult(process_id)
            return {"message":f"Background Task Status: Ready-{status.ready()} Success-{status.successful()} Result-{status.result if status.ready() else None}"}, 200
        else:
            return {"message": "invalid id"} , 400
        

class downloadFile(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        format_url = request.args.get("format_url")
        format_file_name = request.args.get("format_file_name")
        if format_file_name:           
            direct = os.path.join(os.getcwd(), 'downloads')
            list_files = os.listdir(direct)
            file_name = format_file_name
            return send_from_directory(directory=direct, path=file_name)
        return "No Download Request"
        
def update_task_status(database):
    active_tasks = BGProcess.query.filter_by(database=database).all()
    for task in active_tasks:
        new_status = AsyncResult(task.process_id)
        if new_status.ready():
            task.status = "Completed"
            if type(new_status.result) == str:
                task.note = new_status.result 
            else:
                task.note = "Error in Exec." 
            if not new_status.successful():
                task.status = "Error"
        else:
            task.status = "Active"
        db.session.commit()


class get_bg_tasks(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        update_task_status(database)
        # Query the database to get the background tasks' status
        active_tasks = BGProcess.query.filter_by(status='Active', database=database).all()
        error_tasks = BGProcess.query.filter_by(status='Error', database=database).all()
        completed_tasks = BGProcess.query.filter_by(status='Completed', database=database).all()
        active_tasks.sort(key=lambda x: x.datetime if x is not None else "", reverse=True)
        error_tasks.sort(key=lambda x: x.datetime if x is not None else "", reverse=True)
        completed_tasks.sort(key=lambda x: x.datetime if x is not None else "", reverse=True)

        task_data = {
            'active_tasks': [{
                'id': task.id,'name': task.name,
                'status': task.status,'note': task.note,
                'datetime': task.datetime,'data_id': task.data_id} for task in active_tasks],
            'error_tasks': [{
                'id': task.id,'name': task.name,
                'status': task.status,'note': task.note,
                'datetime': task.datetime,'data_id': task.data_id} for task in error_tasks],
            'completed_tasks': [{
                'id': task.id,'name': task.name,
                'status': task.status,'note': task.note,
                'datetime': task.datetime,'data_id': task.data_id} for task in completed_tasks]}
        return jsonify(task_data) , 200

        
        
        
class get_max_pbsl(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data_id = current_user["data"]
        req_json= request.get_json()
        item_id = int(req_json.get('item_id', None)) 
        if item_id: 
            item = Item.query.filter_by(data_id = data_id, id=item_id).first()
            bom_items = db.session.query(
                    BOM.id,BOM.parent_item_id,BOM.child_item_id,BOM.child_item_qty,BOM.margin
                ).filter(BOM.parent_item_id == item_id,BOM.data_id == data_id).all()
            df_BOM = pd.DataFrame(bom_items, columns=['id', 'parent_item_id', 'child_item_id', 'child_item_qty','margin'])
            child_item_list = df_BOM['child_item_id'].unique().tolist()
            inventory_stock_data = db.session.query(
                    Inventory.item_id,Item.code,
                    Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity")
                ).join(Item, Inventory.item_id == Item.id)\
                .group_by(Inventory.item_id, Item.code, Item.name,Item.unit)\
                .filter(Inventory.item_id.in_(child_item_list),Inventory.data_id == data_id).all()
            df_child_inventory = pd.DataFrame(inventory_stock_data,columns=['child_item_id','child_item_code','child_item_name','child_item_unit','total_stock'])
            df_BOM_inventory = pd.merge(left=df_BOM, right=df_child_inventory, how='left', on='child_item_id')
            df_BOM_inventory.fillna(0, inplace=True)
            df_BOM_inventory['max_psbl_production'] = df_BOM_inventory['total_stock']/((1+(0.01*df_BOM_inventory['margin']))*df_BOM_inventory['child_item_qty'])
            df_BOM_inventory = df_BOM_inventory[['child_item_id','child_item_code','child_item_name','child_item_unit','total_stock','max_psbl_production']]
            df_BOM_inventory["parent_item_unit"] = item.unit
            BOM_json = df_BOM_inventory.to_json(orient='records')
            return BOM_json, 200
        return {"message":"item_id not found"}, 400       
        
        
def get_mobile_numbers(data_id):
    mobile_numbers = MobileNumber.query.filter_by(data_id = data_id).all()
    number_list = [number.mobile_number for number in mobile_numbers]
    return number_list