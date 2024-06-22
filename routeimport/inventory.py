from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
from flask import Flask,current_app, render_template,current_app, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import jsonify
from models import Data, Category, Inventory, Item, User, BGProcess, db
import random
import string
from datetime import datetime, date
import requests
import pandas as pd
import os
import pdfkit
from celery import shared_task
from routeimport.utility import get_mobile_numbers
from routeimport.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE
from sqlalchemy import or_
from bgtasks import addStockList
from routeimport.iteminfo import searchitemouter
# class addrecord(Resource):
#     @jwt_required()
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])


class Inventory1(Resource):
    @jwt_required()
    @requires_role(["INVENTORY"], 0)
    def get(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        CATEGORIES=[]
        categories = Category.query.filter_by(database=database).all()
        for item in categories:
            CATEGORIES.append([item.id, item.name])
        segment = get_segment(request, current_user['data'])
        return {"message": "inventory/inventory.html", "segment": segment, "categories": CATEGORIES}, 200
    
    
class bulkentryinventory(Resource):
    @jwt_required()
    @requires_role(["INVENTORY"], 1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        id_list =data.get("items_ids[]",[])
        qty_list =data.get("items_qtys[]",[])
        note_list =data.get("items_notes[]",[])
        item_units =data.get("item_units[]",[])
        res = []
        if id_list and qty_list and note_list and item_units:
            for i in range(len(id_list)):
                try:
                    item = Item.query.filter_by(id =id_list[i], database=database).first()
                    conversion_factor = get_conversion_factor(database, item, item_units[i])
                    converted_qty = float(qty_list[i])/conversion_factor
                    inventory = Inventory(item = item, qty = converted_qty, item_unit = item.unit, note = note_list[i], database=database)
                    db.session.add(inventory)
                    db.session.commit()
                except:
                    res.append(f"item  not found for item id {id_list[i]}")
            numbers_list = get_mobile_numbers(current_user["data"])
            user = User.query.filter_by(id=current_user["user_id"]).first()
            for number in numbers_list:
                resp = SEND_MESSAGE(f"Inventory adjustment by {user.name}!", number)
            return {"message": "Items Added to Inventory", "result":res}, 200
        return {"message": "check input"}, 401
    

class addinventoryledger(Resource):
    @jwt_required()
    @requires_role(["INVENTORY"], 1)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        direct = os.path.join(os.getcwd(), 'uploads')
        #list_files = os.listdir(direct)
        f=request.files["file"]
        if ".csv" not in f.filename:
            return {"message": "Invalid file"} , 401
        try:
            file_path=os.path.join(direct, f.filename)
            f.save(file_path)
            result = addStockList.delay(database.id, file_path)
            bg_process = BGProcess(process_id=result.id, name="Item Master Upload", database=database)
            db.session.add(bg_process)
            db.session.commit()
            return {"Message": "File Uploaded to Server! Adding Items in Background", "result_id":result.id}, 200
        except Exception as e:
            return {"Message": "error occured!!" , "Error": e} , 401
        

# class addinventoryledger(Resource):
#     @jwt_required()
#     @requires_role(["INVENTORY"], 0)

        
class inventoryledger(Resource):
    @jwt_required()
    @requires_role(["INVENTORY"], 0)
    def post(self):
        current_user = get_jwt_identity()
        req_json = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        k = int(req_json.get('k', 25 ))  # Default value is 10
        item_id = req_json.get('item_id', None)
        item_filter = req_json.get('item_filter', "no")
        data_type = req_json.get('data_type', "ACTIVE")
        filters = req_json.get("filters", None)
        if item_filter == "yes":
            items_dict = searchitemouter(k, None, None,filters,current_user["data"])
            items_df = pd.DataFrame(items_dict)
        epsilon = 1e-2
        if item_id:
            inventories = db.session.query(Inventory.item_id, Item.name, Inventory.qty, Inventory.item_unit, Inventory.note, Inventory.regdate
                ).filter(Inventory.data_id == current_user["data"], Inventory.status==data_type, Inventory.item_id == item_id).join(Item, Inventory.item_id == Item.id).order_by(Inventory.regdate.desc()).all()
        elif k>=0:
            inventories = db.session.query(Inventory.item_id, Item.name, Inventory.qty, Inventory.item_unit, Inventory.note, Inventory.regdate
                ).filter(Inventory.data_id == current_user["data"], or_(Inventory.qty > epsilon, Inventory.qty < -epsilon) ).join(Item, Inventory.item_id == Item.id).order_by(Inventory.regdate.desc()).limit(k).all()
        else:
            inventories = db.session.query(Inventory.item_id, Item.name, Inventory.qty, Inventory.item_unit, Inventory.note, Inventory.regdate
                ).filter(Inventory.data_id == current_user["data"], or_(Inventory.qty > epsilon, Inventory.qty < -epsilon) ).join(Item, Inventory.item_id == Item.id).order_by(Inventory.regdate.desc()).all()
        inventories_df = pd.DataFrame(inventories, 
            columns=["item_id", "name", "qty", "item_unit", "note", "regdate"]
            )
        if item_filter == "yes":
            if k<=0:
                start_date = req_json.get("startDate", None)
                end_date = req_json.get("endDate", None)
                print(start_date, end_date)
                if start_date and end_date:
                    inventories_df = inventories_df[(inventories_df['regdate'] >= start_date) & (inventories_df['regdate'] <= end_date)]
            try:
                inventories_df = pd.merge(inventories_df, items_df, left_on="item_id", right_on="id", how="inner", suffixes=('', '_items'))
            except:
                print(items_df)
        inventories_df['regdate'] = inventories_df['regdate'].dt.strftime('%d-%m-%Y')
        return inventories_df.to_dict(orient="records"), 200
    

class inventoryLookup(Resource):
    @jwt_required()
    @requires_role(["INVENTORY"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        req_json= request.get_json()
        k = int(req_json.get('k', None))  # Default value is 10
        item_id = req_json.get("item_id", None)
        item_string = req_json.get('item_search_string', None)
        item_filter = req_json.get('item_filter', "no")
        stock_list = req_json.get('stock_list', "no")
        filters = req_json.get('filters', None)
        data_type = req_json.get('data_type', "ACTIVE")
        print("filters:", filters)
        if item_filter == "yes" and filters:
            try:
                items_dict = searchitemouter(-1, None, None, filters, current_user['data'])
                items_df_filters = pd.DataFrame(items_dict)
                print(items_df_filters)
            except requests.ConnectionError:
                print("this is the error points 1")
        if item_string:
            print("item_stirng:", item_string)
            try:
                items_dict = searchitemouter(200, item_string, None, None, current_user['data'])
                items_df_search = pd.DataFrame(items_dict)
                print(items_df_search)
            except requests.ConnectionError:
                print("this is the error points 2")
        items_data = db.session.query(Item.id,Item.code,Item.name,Item.unit,).filter(Item.data_id == current_user["data"]).all()
        items_df = pd.DataFrame(items_data, columns=["item_id", "item_code", "Item Name", "Item Unit",])
        inventory_stock_data = db.session.query(Inventory.item_id,db.func.sum(Inventory.qty).label("total_quantity"))\
            .join(Item, Inventory.item_id == Item.id)\
            .group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
            .filter(Inventory.data_id == current_user["data"], Inventory.status == "ACTIVE").all()
        wip_inventory_stock_data = db.session\
            .query(Inventory.item_id,db.func.sum(Inventory.qty).label("total_quantity"))\
            .join(Item, Inventory.item_id == Item.id)\
            .group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
            .filter(Inventory.data_id == current_user["data"], Inventory.status == "WIP").all()
        reject_inventory_stock_data = db.session\
            .query(Inventory.item_id,db.func.sum(Inventory.qty).label("total_quantity"))\
            .join(Item, Inventory.item_id == Item.id)\
            .group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
            .filter(Inventory.data_id == current_user["data"], Inventory.status == "REJECT").all()
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id","total_stock" ])
        wip_inventory_stock_df = pd.DataFrame(wip_inventory_stock_data, columns=["item_id","total_wip_stock" ])
        reject_inventory_stock_df = pd.DataFrame(reject_inventory_stock_data, columns=["item_id","total_reject_stock" ])
        inventory_stock_df = pd.merge(inventory_stock_df, items_df, left_on="item_id", right_on="item_id", how='right')
        inventory_stock_df = pd.merge(inventory_stock_df,wip_inventory_stock_df, left_on='item_id', right_on='item_id', how="left")
        inventory_stock_df = pd.merge(inventory_stock_df,reject_inventory_stock_df, left_on='item_id', right_on='item_id', how="left")
        inventory_stock_df.fillna(0, inplace=True)
        if item_filter == "yes":
            if len(filters["filters_array"]) == 0:
                inventory_stock_df = inventory_stock_df
            elif len(items_df_filters.index) == 0:
                inventory_stock_df = inventory_stock_df[0:0]
            else:
                print(inventory_stock_df.columns)
                inventory_stock_df.drop(["item_code", "Item Name", "Item Unit"] ,inplace=True, axis=1)
                inventory_stock_df = pd.merge(items_df_filters,inventory_stock_df, left_on="id", right_on="item_id", how="left")
                inventory_stock_df["total_stock"].fillna(0, inplace=True)
                inventory_stock_df["total_wip_stock"].fillna(0, inplace=True)
                inventory_stock_df["total_reject_stock"].fillna(0, inplace=True)
                inventory_stock_df["item_id"] = inventory_stock_df["id"]
                inventory_stock_df.rename(columns = {"code":"item_code", "name":"Item Name", "unit":"Item Unit"}, inplace = True)
                print(inventory_stock_df.columns)
        if item_string:
            inventory_stock_df = pd.merge(inventory_stock_df, items_df_search, left_on="item_id", right_on="id", how="inner")
        if item_id:
            print("REACHED")
            inventory_stock_df = inventory_stock_df[inventory_stock_df['item_id'] == int(item_id)]
            if data_type == "WIP":
                inventory_stock_df['total_stock'] = inventory_stock_df['total_wip_stock']
            elif data_type == "REJECT":
                inventory_stock_df['total_stock'] = inventory_stock_df['total_reject_stock']
        if stock_list == "excel":
            inventory_stock_df = inventory_stock_df[["item_code", "Item Name", "Item Unit", "total_stock"]]
            inventory_stock_df["new_stock"]=''
            inventory_stock_df["note"]=''
            file_name = f"{database.id}_stock_list.csv"
            direct = os.path.join(os.getcwd(), 'downloads')
            os.makedirs(direct, exist_ok=True)
            file_path = os.path.join(direct, file_name)
            inventory_stock_df.to_csv(file_path, index=False)
            return send_from_directory(directory=direct, filename=file_name, as_attachment=True)
        if stock_list == "pdf":
            html_template = render_template("inventory/stock_list_template.html", inventory_dict =inventory_stock_df.to_dict(orient="records"))
            file_name = f"{database.id}_stock_list.pdf"
            direct = os.path.join(os.getcwd(), 'downloads')
            file_path = os.path.join(direct, file_name)
            path = '/usr/bin/wkhtmltopdf'
            config = pdfkit.configuration(wkhtmltopdf=path)
            pdfkit.from_string(html_template, file_path, configuration=config)
            return send_from_directory(directory=direct, filename=file_name, as_attachment=True)
        return jsonify(inventory_stock_df.to_dict(orient="records"))

    
    
class stock_reconcilation(Resource):
    @jwt_required()
    @requires_role(['INVENTORY'], 0)
    def get(post):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        inventory_stock_data = db.session.query(Inventory.item_id,Item.code,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity"))\
            .join(Item, Inventory.item_id == Item.id).group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
            .filter(Inventory.data_id == current_user["data"], Inventory.status=='ACTIVE').all()
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id","item_code", "Item Name", "Item Unit","total_stock" ])
        return {"Data":inventory_stock_df.to_dict(orient="records")}, 200
    
    @jwt_required()
    @requires_role(["INVENTORY"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        req_json= request.get_json()
        filter_type=req_json.get("filter_type")
        filters_array = req_json.get("filters[]",[])
        reconcile_flag = req_json.get("reconcile_flag", "NO")
        item_ids = req_json.get("item_ids[]", [])
        physical_stocks = req_json.get("physical_stocks[]", [])
        notes = req_json.get("notes[]", [])
        units = req_json.get("units[]", [])
        if len(filters_array):
            try:
                body = {"k": -1,"filters":{"filters_array":filters_array, "filter_type":filter_type}}
                items_dict = searchitemouter(-1, None, None,body["filters"],current_user['data'] )
                items_df_filters = pd.DataFrame(items_dict)
                print(items_df_filters)
            except:
                print("this is the error point")
        inventory_stock_data = db.session.query(Inventory.item_id,Item.code,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity"))\
            .join(Item, Inventory.item_id == Item.id).group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
            .filter(Inventory.data_id == current_user["data"], Inventory.status=='ACTIVE').all()
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id","item_code", "Item Name", "Item Unit","total_stock" ])
        if len(filters_array) == 0:
            inventory_stock_df = inventory_stock_df
        elif len(items_df_filters.index) == 0:
            inventory_stock_df = inventory_stock_df[0:0]
        else:
            inventory_stock_df.drop(["item_code", "Item Name", "Item Unit"] ,inplace=True, axis=1)
            inventory_stock_df = pd.merge(items_df_filters,inventory_stock_df, left_on="id", right_on="item_id", how="left")
            inventory_stock_df["total_stock"].fillna(0, inplace=True)
            inventory_stock_df["item_id"].fillna("", inplace=True)
            inventory_stock_df.rename(columns = {"code":"item_code", "name":"Item Name", "unit":"Item Unit"}, inplace = True)
            print(inventory_stock_df.columns)
        result = []
        if reconcile_flag == "YES":
            if not item_ids and not physical_stocks and not notes and not units:
                return {"message":"reconcile Flag is Yes but no suiatable input found."}, 401
            if len(item_ids) != len(physical_stocks) and len(item_ids) != len(notes) and len(item_ids) != len(units):
                return {"message":"reconcile Flag is Yes but input length uneven."}, 401
            for i in range(len(item_ids)):
                item = Item.query.filter_by(database=database, id=int(item_ids[i])).first()
                if item:
                    try:
                        system_stock = inventory_stock_df.loc[inventory_stock_df['item_id'] == item.id, 'total_stock'].values[0]
                    except:
                        system_stock = 0
                    print("system_stocks:",system_stock)
                    conv = get_conversion_factor(database, item, units[i])
                    qty_adjust = (float(physical_stocks[i])/conv) - system_stock
                    inventory = Inventory(item=item, database=database, qty = qty_adjust, note = notes[i]+f"_reconcilation_[{system_stock} to {float(physical_stocks[i])/conv} {item.unit}]", item_unit = item.unit)
                    db.session.add(inventory)
                    db.session.commit()
            numbers_list = get_mobile_numbers(current_user["data"])
            user = User.query.filter_by(id=current_user["user_id"]).first()
            for number in numbers_list:
                resp = SEND_MESSAGE(f"Stock reconcilation completed by {user.name}!", number)
                result.append(f"Stock reconcilation completed by {user.name}!, message send to number : {number}")
        return  {"DATA":inventory_stock_df.to_dict(orient="records"), "Reconcilation_result": result}, 200
    