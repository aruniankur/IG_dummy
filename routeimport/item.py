from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask_paginate import Pagination, get_page_args
from models import User, Item, Category, ItemCategory, Labor, Data, BOM, Inventory, Unit, UnitMapping, ItemUnit, Joballot, Prodchart, Customer, Order, OrderItem, DataConfiguration, ItemCustomField, BGProcess, ItemFinance, ItemInventory, ItemBOM
#from decorators import requires_role, get_segment, get_conversion_factor 
from models import db
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from sqlalchemy import and_, exists
import pandas as pd
#from Production.background_tasks.background_tasks import my_background_task, itemMasterUpload
from celery.result import AsyncResult
from celery import Celery
from celery import shared_task
import requests
from sqlalchemy import func
import datetime
from sqlalchemy.orm import class_mapper
import secrets
from flask_restful import Api, Resource, reqparse
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import smtplib
from bgtasks import long_running_task, long_running_task2, update_category_linking, update_bom_linking
from routeimport.decorators import requires_role, get_segment, createjson
import os
    
#----------------------------------------------------------------

class list_items(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        filters_list = data.get("filters", [])  # Correctly access the filters list
        filter_type = data.get('filter_type')
        FILTER_CATEGORY_PAIRS = []
        for cat_id in filters_list:
            category = Category.query.filter_by(database=database, id=cat_id).first()
            FILTER_CATEGORY_PAIRS.append((int(cat_id), category.name))
        items = Item.query.filter_by(data_id=current_user['data']).all()
        categories = Category.query.filter_by(database=database).all()
        CATEGORIES = [[item.id, item.name] for item in categories]
        page, per_page, offset = get_page_args(page_parameter='page', per_page_parameter='per_page')
        per_page = 50
        if filters_list and filter_type:
            per_page = 200
        pagination = Pagination(page=page, per_page=per_page, total=len(items), css_framework='bootstrap5')
        start = (page - 1) * per_page
        end = start + per_page
        items = items[start:end]
        units = Unit.query.filter_by(database=database).all()
        segment = get_segment(request,current_user["data"])
        response = {'items':createjson(items), 'categories':CATEGORIES, 'filter_category_pairs':FILTER_CATEGORY_PAIRS, 
                    'filter_type':filter_type, 'pagination':createjson(pagination), 'units':createjson(units), 'segment':segment}
        return response , 200

class add_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        p_code = data.get("p_code")
        p_name = data.get("p_name")
        p_rate = data.get("p_rate")
        p_unit = data.get("p_unit")
        p_flag = data.get("p_flag")
        pf_cost_price = data.get("pf_cost_price")
        pf_sale_price = data.get("pf_sale_price")
        pf_tax = data.get("pf_tax")
        pf_hsn = data.get("pf_hsn")
        if p_name and p_unit and p_flag:
            p_check1 = Item.query.filter_by(name=p_name, database=database).first()
            if not p_check1:
                pf_cost_price = pf_cost_price or 0
                pf_sale_price = pf_sale_price or 0
                pf_tax = pf_tax or 0
                p_rate = p_rate or 0
                prod_code = p_code or "NA"
                pf_hsn = pf_hsn or ""
                item1 = Item(name=p_name, rate=p_rate, unit=p_unit, database=database, code=prod_code, raw_flag=p_flag)
                db.session.add(item1)
                db.session.commit()
                item_finance = ItemFinance(database=database, item=item1, cost_price=pf_cost_price, sale_price=pf_sale_price, tax=pf_tax, hsn_code=pf_hsn)
                db.session.add(item_finance)
                db.session.commit()
                if p_flag == "NO":
                    return {'message': "iteminfo", 'itemid':item1.id}, 200
                return {'message': "new item added"}, 302
            else:
                return {'message':'item already exists'}, 401
        return {'message':'check input'}, 401
    
class edit_items(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        edit_ids = data.get("edit_ids[]", [])        
        edit_codes = data.get("edit_codes[]", [])
        edit_names = data.get("edit_names[]", [])
        edit_rates = data.get("edit_rates[]", [])
        edit_units = data.get("edit_units[]", [])
        edit_hsn_codes = data.get("edit_hsn_codes[]", [])
        edit_cost_prices = data.get("edit_cost_prices[]", [])
        edit_sale_prices = data.get("edit_sale_prices[]", [])
        edit_taxes = data.get("edit_taxes[]", [])
        edit_bom_flags = data.get("edit_bom_flags[]", [])
        edit_min_levels = data.get("edit_min_levels[]", [])
        edit_max_levels = data.get("edit_max_levels[]", [])
        if edit_ids:
            res = ""
            for i in range(len(edit_ids)):
                edit_id = edit_ids[i]
                edit_code = edit_codes[i]
                edit_name = edit_names[i]
                edit_rate = edit_rates[i]
                edit_unit = edit_units[i]
                edit_hsn_code = edit_hsn_codes[i] if edit_hsn_codes else "NA"
                edit_cost_price = edit_cost_prices[i] if edit_cost_prices else 0
                edit_sale_price = edit_sale_prices[i] if edit_sale_prices else 0
                edit_bom_flag = edit_bom_flags[i] if edit_bom_flags else None
                edit_tax = edit_taxes[i] if edit_taxes else 0
                edit_min_level = edit_min_levels[i] if edit_min_levels else 0
                edit_max_level = edit_max_levels[i] if edit_max_levels else 1000000

                if edit_name and edit_rate and edit_id and edit_unit and edit_code:
                    p_check1 = Item.query.filter_by(name=edit_name, database=database).first()
                    p_check2 = Item.query.filter_by(id=edit_id, database=database).first()

                    if p_check1 and p_check2.id != p_check1.id:
                        res += f"Item Name Already Exists for {edit_name}!"
                        continue

                    if p_check2:
                        item2 = Item.query.filter_by(id=edit_id).first()
                        item2.name = edit_name
                        item2.rate = edit_rate
                        item2.unit = edit_unit
                        item2.code = edit_code
                        if edit_bom_flag:
                            item2.raw_flag = edit_bom_flag

                        if not item2.itemfinance:
                            item_finance = ItemFinance(database=database, item=item2)
                            db.session.add(item_finance)
                            db.session.commit()
                            item2.itemfinance = item_finance

                        if edit_cost_prices:
                            item2.itemfinance.hsn_code = edit_hsn_code
                            item2.itemfinance.cost_price = edit_cost_price
                            item2.itemfinance.sale_price = edit_sale_price
                            item2.itemfinance.tax = edit_tax

                        if not item2.iteminventory:
                            item_inventory = ItemInventory(database=database, item=item2)
                            db.session.add(item_inventory)
                            db.session.commit()
                            item2.iteminventory = item_inventory
                        if edit_min_levels:
                            item2.iteminventory.min_level = edit_min_level
                            item2.iteminventory.max_level = edit_max_level
                        db.session.commit()
                        res += f"Item {edit_name} Changed!"
                    else:
                        res += f"Item {edit_name} Doesn't Exist!"
            return {"message": res}, 302
        return {'message': 'no id found'}, 302
    
#see this
class search_items(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        search_string = data.get("search_string")
        filters_list = data.get("filters[]", [])
        filter_type = data.get('filter_type')
        if filters_list and filter_type:
            try:
                url = "/production/items/search"
                headers = {'Content-Type': 'application/json'}
                body = {
                    "k": -1,
                    "filters": {"filter_type": filter_type, "filters_array": filters_list}
                }
                body["session_data"] = session.get('BAD_SECRET_KEY')
                try:
                    process_data_response = requests.post(f'{current_app.config["API_BASE_URL_LOCAL"]}/{url}', json=body, cookies=request.cookies)
                except:
                    process_data_response = requests.post(f'{current_app.config["API_BASE_URL"]}/{url}', json=body, cookies=request.cookies)
                response_json = process_data_response.json()
                items_dict = response_json
            except requests.ConnectionError:
                return "Connection Error"
            items = items_dict
        elif search_string:
            try:
                url = "/production/items/search"
                headers = {'Content-Type': 'application/json'}
                body = {
                    "k": 200,
                    "name": search_string
                }
                body["session_data"] = session.get('BAD_SECRET_KEY')
                try:
                    process_data_response = requests.post(f'{current_app.config["API_BASE_URL_LOCAL"]}/{url}', json=body, cookies=request.cookies)
                except:
                    process_data_response = requests.post(f'{current_app.config["API_BASE_URL"]}/{url}', json=body, cookies=request.cookies)
                response_json = process_data_response.json()
                items_dict = response_json
            except requests.ConnectionError:
                return "Connection Error"
            items = items_dict
        else:
            items = Item.query.filter_by(data_id=current_user['data']).all()

        return render_template("items/items_list.html", items=items)
    
#----------------------------------------------------------------


class ItemListResource(Resource):
    def get(self):
        print("Getting ready")
        result = long_running_task.delay(10)
        resul2 = long_running_task2.delay(3)
        return {"message": "this is the lis", "result": result.id, "result1":resul2.id}, 200
    
#----------------------------------------------------------------

class TaskStatusResource(Resource):
    def get(self, task_id):
        task_result = AsyncResult(task_id)
        if task_result.state == 'PENDING':
            response = {
                'state': task_result.state,
                'status': 'Pending...'
            }
        elif task_result.state != 'FAILURE':
            response = {
                'state': task_result.state,
                'result': task_result.result
            }
        else:
            response = {
                'state': task_result.state,
                'status': str(task_result.info),  # This is the exception raised
            }
        return jsonify(response), 200
    
#----------------------------------------------------------------
def category_excel_new(data_id):
    print("creating excel file!!!")
    database = Data.query.filter_by(id = data_id).first()
    categories = Category.query.filter_by(database=database).all()
    result = db.session.query(Item.id.label('item_id'),Item.name.label('item_name'), Category.id.label('category_id'), Category.name.label('category_name'))\
        .join(ItemCategory, Item.id == ItemCategory.item_id)\
        .join(Category, ItemCategory.category_id == Category.id)\
        .filter(Item.data_id == data_id, Category.data_id == data_id)\
        .all()
    if result:
        print("Non-empty result")
        df = pd.DataFrame(result)[['item_name', 'category_name']]
        pivot_table = df.pivot_table(index='item_name', columns='category_name', aggfunc=lambda x: 1, fill_value=0)
        categories_name = [category.name for category in categories]
        print(set(categories_name))
        print(set(pivot_table.columns))
        missing_categories = set(categories_name) - set(pivot_table.columns)
        print(missing_categories)
        for category in missing_categories:
            pivot_table[category] = 0
        pivot_table = pivot_table.reset_index()
        print(pivot_table)
        items=db.session.query(Item.id.label('item_id'),Item.name.label('item_name'), Item.code.label('item_code'))\
        .filter(Item.data_id == data_id)\
        .all()
        items_df = pd.DataFrame(items)
        pivot_table = pd.merge(pivot_table, items_df, left_on ='item_name', right_on='item_name', how='right')
        pivot_table.fillna(0, inplace=True)
    else:
        result=db.session.query(Item.id.label('item_id'),Item.name.label('item_name'), Item.code.label('item_code'))\
        .filter(Item.data_id == data_id)\
        .all()
        print("Empty result")
        pivot_table = pd.DataFrame(result)[['item_name', 'item_code']]
        missing_categories = set(categories)
        for category in missing_categories:
            pivot_table[category.name] = 0
    pivot_table = pivot_table.rename(columns={'item_name': "Item Name"})
    excel_filename = f"item_category_map_{database.key}.csv"
    excel_path = f'downloads/{excel_filename}'
    pivot_table.to_csv(excel_path, index=False)
    return excel_filename
    
    
class ItemCategoriesExcelResource(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        parser = reqparse.RequestParser()
        parser.add_argument('generate_file', type=str, required=True, help='Flag for generating file')
        args = parser.parse_args()
        generate_file_flag = args['generate_file']
        if generate_file_flag == "YES":
            file_name = category_excel_new(current_user["data"])
            return jsonify({"status": "OK", "filename": file_name}), 200
        direct = os.path.join(os.getcwd(), 'uploads')
        f = request.files.get("file")
        if f:
            file_path = os.path.join(direct, f.filename)
            f.save(file_path)
            flash("File Uploaded to Server! Updating Item Category Mapping in Background.", "success")
            result = update_category_linking.delay(file_path, current_user['data'])
            bg_process = BGProcess(process_id=result.id, name="Item Category Linking Through CSV", database=database)
            db.session.add(bg_process)
            db.session.commit()
            return {"message":"File Uploaded to Server! Updating Item Category Mapping in Background.", "resultid": result.id}, 200
        return {"message":"check file"}, 401


#----------------------------------------------------------------

class BOMItemsExcelResource(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        parser = reqparse.RequestParser()
        parser.add_argument('file', type='file', location='files')
        args = parser.parse_args()
        f = args['file']
        direct = os.path.join(os.getcwd(), 'uploads')
        file_path = os.path.join(direct, f.filename)
        f.save(file_path)
        database = Data.query.filter_by(id=current_user["data"]).first()
        result = update_bom_linking.delay(file_path, current_user['data'])
        bg_process = BGProcess(process_id=result.id, name="BOM Relation Upload Through CSV", database=database)
        db.session.add(bg_process)
        db.session.commit()
        return {"message": "File uploaded successfully. Item category mapping is being updated in the background.", "result_id":result.id}, 200
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def get(self):
        download_stat = request.args.get("download")
        if download_stat == "YES":
            direct = os.path.join(os.getcwd(), 'downloads')
            list_files = os.listdir(direct)
            file_name = "bom_format.csv" 
            return {"message": "Download the CSV file"}, 200
        else:
            return {"message": "Invalid request. Please provide 'download=YES' parameter."}, 400


