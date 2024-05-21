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

class edit_inventory_levels(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = data.get("item_id")
            mode = data.get("consumption_mode")
            min_level = data.get("edit_inventory_level_min")
            max_level = data.get("edit_inventory_level_max")

            if mode and min_level and max_level:
                item = Item.query.filter_by(database=database, id=item_id).first()
                item_inv = item.iteminventory
                if item_inv:
                    item_inv.consumption_mode = mode
                    item_inv.min_level = min_level
                    item_inv.max_level = max_level
                    db.session.commit()
                return redirect(request.headers.get('Referer', '/'))
            return redirect(request.headers.get('Referer', '/'))
        
#----------------------------------------------------------------

class edit_finance_info(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = request.form.get("item_id")
            hsn_code = request.form.get("hsn_code")
            cost_price = request.form.get("cost_price")
            sale_price = request.form.get("sale_price")
            tax = request.form.get("tax")

            if hsn_code and cost_price and sale_price and tax:
                item = Item.query.filter_by(database=database, id=item_id).first()
                item_fin = item.itemfinance
                if item_fin:
                    item_fin.hsn_code = hsn_code
                    item_fin.cost_price = cost_price
                    item_fin.sale_price = sale_price
                    item_fin.tax = tax
                    db.session.commit()
                return redirect(request.headers.get('Referer', '/'))
            return redirect(request.headers.get('Referer', '/'))
        
#-------------------------------------------------------------

class edit_additional_fields(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=session["data"]).first()
            item_id = request.form.get("item_id")
            additional_fields_flag = request.form.get("additional_fields_flag")

            if additional_fields_flag:
                item = Item.query.filter_by(database=database, id=item_id).first()
                data_config = DataConfiguration.query.filter_by(database=database).first()
                if not data_config:
                    config_dict = {'ADDITIONAL_FIELDS': [], 'SEARCH_FIELDS': []}
                    new_data_config = DataConfiguration(database=database, item_master_config=json.dumps(config_dict))
                    db.session.add(new_data_config)
                    db.session.commit()
                    data_config = new_data_config

                for field in json.loads(data_config.item_master_config)["ADDITIONAL_FIELDS"]:
                    field_name = field["name"]
                    additional_field_edit_value = request.form.get(f"{field_name}_edit")
                    if additional_field_edit_value:
                        item_custom_field = ItemCustomField.query.filter_by(database=database, item=item, field_name=field_name).first()
                        if not item_custom_field:
                            item_custom_field = ItemCustomField(field_name=field_name, field_value=additional_field_edit_value, item=item, database=database)
                            db.session.add(item_custom_field)
                        else:
                            item_custom_field.field_value = additional_field_edit_value
                        db.session.commit()
                return redirect(request.headers.get('Referer', '/'))
            return redirect(request.headers.get('Referer', '/'))
        
#----------------------------------------------------------------

class add_bom_items(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            parent_item_id = data.get("chart_id")
            add_items_check = data.get("add_items_check")

            if add_items_check and parent_item_id:
                parent_item = Item.query.filter_by(id=parent_item_id, database=database).first()
                bom_name = data.get("bom_name")
                if bom_name:
                    item_boms = parent_item.boms
                    if not len(item_boms):
                        item_bom = ItemBOM(database=database, item=parent_item, bom_name=bom_name)
                        db.session.add(item_bom)
                    else:
                        item_boms[0].bom_name = bom_name
                    db.session.commit()

                item_parent_tree = [parent_item]
                search_space = [parent_item]
                while search_space:
                    item = search_space.pop(0)
                    parent_items_bom = BOM.query.filter_by(database=database, child_item=item).all()
                    for parent_item_bom in parent_items_bom:
                        if parent_item_bom.parent_item.id == parent_item.id:
                            db.session.delete(parent_item_bom)
                        item_parent_tree.append(parent_item_bom.parent_item)
                        search_space.append(parent_item_bom.parent_item)

                bom_items = parent_item.parent_boms
                id_list = data.get("items_ids[]",[])
                qty_list = data.get("items_qtys[]",[])
                unit_list = data.get("item_units[]",[])
                margin_list = data.get("item_margins[]",[])

                if len(id_list) == len(qty_list) == len(unit_list) == len(margin_list):
                    for bom_item in bom_items:
                        db.session.delete(bom_item)

                    for i in range(len(id_list)):
                        child_item = Item.query.filter_by(database=database, id=id_list[i]).first()
                        if child_item in item_parent_tree:
                            flash(f"Cannot add {child_item.name}. It exists in the BOM chain!", "danger")
                            continue
                        unit = unit_list[i]
                        conversion_factor = get_conversion_factor(database, child_item, unit)
                        qty = float(qty_list[i]) / conversion_factor
                        margin = margin_list[i]
                        bom_map = BOM(database=database, parent_item=parent_item, child_item=child_item, child_item_qty=qty, margin=margin)
                        db.session.add(bom_map)
                    db.session.commit()
                    flash("Successfully Added BOM!", "success")
                else:
                    flash("Invalid Request FOR BOM!", "danger")
                return redirect(request.headers.get('Referer', '/'))
            return redirect(request.headers.get('Referer', '/'))
        
#----------------------------------------------------------------

class delete_unit(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user = User.query.filter_by(id=current_user['userid']).first()
        if user.role != 'MASTERS':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            delete_unit_id = data.get("delete_unit_id")
            if delete_unit_id:
                unit_mapping = ItemUnit.query.filter_by(database=database, id=delete_unit_id).first()
                db.session.delete(unit_mapping)
                db.session.commit()
                flash("Deleted Unit!", "success")
                return redirect(request.headers.get('Referer', '/'))
            return redirect(request.headers.get('Referer', '/'))
        
#----------------------------------------------------------------

