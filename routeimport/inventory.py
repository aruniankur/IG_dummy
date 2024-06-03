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

# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])


class inventory(Resource):
    @jwt_required
    @requires_role(["INVENTORY"], 0)
    def get(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        CATEGORIES=[]
        categories = Category.query.filter_by(database=database).all()
        for item in categories:
            CATEGORIES.append([item.id, item.name])
        segment = get_segment(request, current_user['data'])
        return {"message": "inventory/inventory.html", "segment": segment, "categories": createjson(CATEGORIES)}, 200
    
    
class bulkentryinventory(Resource):
    @jwt_required
    @requires_role(["INVENTORY"], 1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        id_list =data.get("items_ids[]",[])
        qty_list =data.get("items_qtys[]",[])
        note_list =data.get("items_notes[]",[])
        item_units =data.get("item_units[]",[])
        if id_list and qty_list and note_list and item_units:
            for i in range(len(id_list)):
                item = Item.query.filter_by(id =id_list[i], database=database).first()
                conversion_factor = get_conversion_factor(database, item, item_units[i])
                converted_qty = float(qty_list[i])/conversion_factor
                inventory = Inventory(item = item, qty = converted_qty, item_unit = item.unit, note = note_list[i], database=database)
                db.session.add(inventory)
                db.session.commit()
            numbers_list = get_mobile_numbers(current_user["data"])
            user = User.query.filter_by(id=current_user["user_id"]).first()
            for number in numbers_list:
                resp = SEND_MESSAGE(f"Inventory adjustment by {user.name}!", number)
            flash("Items Added to Inventory!", "success")
            return {"message": "Items Added to Inventory"}, 200
        return {"message": "check input"}, 401
    

class addinventoryledger(Resource):
    @jwt_required
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
#     @jwt_required
#     @requires_role(["INVENTORY"], 0)

        