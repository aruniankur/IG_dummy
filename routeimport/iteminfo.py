from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask_paginate import Pagination, get_page_args
from models import User, Item, Category, ItemCategory, Labor, Data, BOM, Inventory, Unit, UnitMapping, ItemUnit, Joballot, Prodchart, Customer, Order, OrderItem, DataConfiguration, ItemCustomField, BGProcess, ItemFinance, ItemInventory, ItemBOM
#from decorators import requires_role, get_segment, get_conversion_factor 
from models import db
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from flask_paginate import Pagination, get_page_parameter
from sqlalchemy import and_, exists
import pandas as pd
from fuzzywuzzy import fuzz
#from Production.background_tasks.background_tasks import my_background_task, itemMasterUpload
from celery.result import AsyncResult
from celery import Celery
from celery import shared_task
import requests
from sqlalchemy import func
import datetime
from sqlalchemy.orm import class_mapper
import secrets
from flask_restful import Api, Resource
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import smtplib

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
    
class itemsinfo(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = request.args.get("item_id")
            ITEM = Item.query.filter_by(id=item_id, database=database).first()
            if not ITEM.iteminventory:
                item_inv = ItemInventory(database=database, item=ITEM)
                db.session.add(item_inv)
                db.session.commit()
            raw_bool = ITEM.raw_flag == "YES"
            anti_raw_bool = not raw_bool
            item_parent_tree = [ITEM]
            search_space = [ITEM]
            while search_space:
                item = search_space.pop(0)
                parent_items_bom = BOM.query.filter_by(database=database, child_item=item).all()
                for parent_item_bom in parent_items_bom:
                    if parent_item_bom.parent_item.id == ITEM.id:
                        db.session.delete(parent_item_bom)
                    item_parent_tree.append(parent_item_bom.parent_item)
                    search_space.append(parent_item_bom.parent_item)
            if not ITEM.boms:
                item_bom = ItemBOM(database=database, item=ITEM, bom_name=ITEM.name[:63])
                db.session.add(item_bom)
                db.session.commit()
            BOM_DATA = BOM.query.filter_by(database=database, parent_item=ITEM).all()
            CHART_BOM_DATA = []
            for bom_item in BOM_DATA:
                if not bom_item.child_item.itemfinance:
                    it_f = ItemFinance(item=bom_item.child_item)
                    db.session.add(it_f)
                    db.session.commit()
                CHART_BOM_DATA.append([bom_item.id, bom_item.child_item.name, bom_item.child_item_qty, bom_item.child_item.unit, bom_item.margin, bom_item.child_item.id, bom_item.child_item.code])
            ITEM_CATEGORIES = ItemCategory.query.filter_by(database=database, item=ITEM).all()
            ITEM_UNITS = ItemUnit.query.filter_by(database=database, item=ITEM).all()

            items = Item.query.filter_by(data_id=session["data"]).all()
            ITEMS = [[item.id, item.name, item.unit, item.rate] for item in items if item not in item_parent_tree]

            categories = Category.query.filter_by(data_id=session["data"]).all()
            CATEGORIES = [[item.id, item.name] for item in categories]

            data_config = DataConfiguration.query.filter_by(database=database).first()
            if not data_config:
                config_dict = {'ADDITIONAL_FIELDS': [], 'SEARCH_FIELDS': []}
                new_data_config = DataConfiguration(database=database, item_master_config=json.dumps(config_dict))
                db.session.add(new_data_config)
                db.session.commit()
                data_config = new_data_config

            additional_fields = ItemCustomField.query.filter_by(database=database, item=ITEM).all()
            additional_fields_dict = {field.field_name: field.field_value for field in additional_fields}

            segment = get_segment(request,current_user["data"])
            return render_template("items/item_info_new.html", ITEM=ITEM, categories=CATEGORIES, items=ITEMS, BOM_DATA=BOM_DATA,
                                CHART_BOM_DATA=CHART_BOM_DATA, raw_bool=raw_bool, anti_raw_bool=anti_raw_bool,
                                item_categories=ITEM_CATEGORIES, units=ITEM_UNITS, item_master_config=json.loads(data_config.item_master_config),
                                additional_fields_dict=additional_fields_dict, segment=segment)           

#----------------------------------------------------------------

class add_bom_item(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            parent_item_id = data.get("parent_item_id")
            child_item_id = data.get("child_item_id")
            child_item_qty1 = data.get("child_item_qty")
            margin = data.get("add_bom_margin")

            if parent_item_id and child_item_id and child_item_qty1 and margin:
                child_item = Item.query.filter_by(id=child_item_id).first()
                parent_item = Item.query.filter_by(id=parent_item_id).first()
                bom_data = BOM(parent_item=parent_item, child_item=child_item, child_item_qty=float(child_item_qty1),
                            child_item_unit=child_item.unit, database=database, margin=margin)
                db.session.add(bom_data)
                db.session.commit()
                return redirect(f"/itemsinfo?item_id={parent_item_id}", code=302)
            return redirect(request.headers.get("Referer"))
        
#----------------------------------------------------------------      

class edit_bom_item(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            edit_bom_id = data.get("edit_bom_id")
            edit_bom_qty = data.get("edit_bom_quant")
            edit_bom_margin = data.get("edit_bom_margin")

            if edit_bom_qty and edit_bom_id and edit_bom_margin:
                edit_bom = BOM.query.filter_by(id=edit_bom_id).first()
                edit_bom.child_item_qty = float(edit_bom_qty)
                edit_bom.margin = float(edit_bom_margin)
                db.session.commit()
                return redirect(f"/itemsinfo?item_id={edit_bom.parent_item_id}", code=302)
            return redirect(request.headers.get("Referer"))
        
#----------------------------------------------------------------

class delete_bom_item(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            delete_bom_id = data.get("bom_delete_id")
            if delete_bom_id:
                delete_bom = BOM.query.filter_by(id=delete_bom_id).first()
                db.session.delete(delete_bom)
                db.session.commit()
                return redirect(f"/itemsinfo?item_id={delete_bom.parent_item_id}", code=302)
            return redirect(request.headers.get("Referer"))
        
#----------------------------------------------------------------

class add_category_to_item(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            add_category_item_id = data.get("add_category_item_id")
            add_category_id = data.get("add_category_id")

            if add_category_id and add_category_item_id:
                item = Item.query.filter_by(database=database, id=add_category_item_id).first()
                category = Category.query.filter_by(database=database, id=add_category_id).first()
                item_cat = ItemCategory.query.filter_by(database=database, item=item, category=category).first()
                if item_cat:
                    flash("Category already present in the item", "danger")
                    return redirect(f"/itemsinfo?item_id={item.id}", code=302)
                item_category = ItemCategory(database=database, item=item, category=category)
                db.session.add(item_category)
                db.session.commit()
                flash("Added Category!", "success")
                return redirect(f"/itemsinfo?item_id={item.id}", code=302)
            return redirect(request.headers.get("Referer"))
        
#----------------------------------------------------------------

class delete_category_from_item(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            delete_category_item_id = request.form.get("delete_category_item_id")
            delete_category_id = request.form.get("delete_category_id")

            if delete_category_id and delete_category_item_id:
                category = Category.query.filter_by(database=database, id=delete_category_id).first()
                item = Item.query.filter_by(database=database, id=delete_category_item_id).first()
                item_category = ItemCategory.query.filter_by(database=database, item=item, category=category).first()
                db.session.delete(item_category)
                db.session.commit()
                flash("Category Removed", "danger")
                return redirect(f"/itemsinfo?item_id={item.id}", code=302)
            return redirect(request.headers.get("Referer"))
        
#----------------------------------------------------------------

