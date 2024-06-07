from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask_paginate import Pagination, get_page_args
from models import User, Item, Category, ItemCategory, Labor, Data, BOM, Inventory, Unit, UnitMapping, ItemUnit, Joballot, Prodchart, Customer, Order, OrderItem, DataConfiguration, ItemCustomField, BGProcess, ItemFinance, ItemInventory, ItemBOM
from models import db
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from flask_paginate import Pagination, get_page_parameter
from sqlalchemy import and_, exists
import pandas as pd
from fuzzywuzzy import fuzz
from celery.result import AsyncResult
from sqlalchemy import func
from sqlalchemy.orm import class_mapper
import secrets
from flask_restful import Api, Resource
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
from routeimport.decorators import requires_role, get_segment, createjson

def get_conversion_factor(database, item, unit_name):
    print(database.id, item.name, unit_name)
    if item.unit == unit_name:
        return 1
    item_unit = ItemUnit.query.filter_by(database=database, item = item, unit_name = unit_name).first()
    if item_unit:
        return item_unit.conversion_factor
    return 1
    
def compare_strings(s1, s2, code=""):
    if s1 in code:
        score=100
    elif s1 in s2:
        score=100
    elif s2 in s1:
        score=100
    else:
        score= fuzz.token_sort_ratio(s1, s2)
    return score

    
#----------------------------------------------------------------
    
class itemsinfo(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = data.get("item_id")
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

            # items = Item.query.filter_by(data_id=current_user["data"]).all()
            # ITEMS = [[item.id, item.name, item.unit, item.rate] for item in items if item not in item_parent_tree]

            categories = Category.query.filter_by(data_id=current_user["data"]).all()
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
            print(ITEM.boms)
            response = {'ITEM':createjson(ITEM),'itemfinance':createjson(ITEM.itemfinance), 'categories':CATEGORIES, 'BOM_DATA':createjson(BOM_DATA),
                                'CHART_BOM_DATA':CHART_BOM_DATA, 'raw_bool':raw_bool, 'anti_raw_bool':anti_raw_bool, 'itemboms':createjson(ITEM.boms),
                                'item_categories':createjson(ITEM_CATEGORIES), 'units':createjson(ITEM_UNITS), 
                                'item_master_config':json.loads(data_config.item_master_config),
                                'additional_fields_dict':additional_fields_dict, 'segment':segment}
        return response, 200
#----------------------------------------------------------------

class add_bom_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            parent_item_id = data.get("parent_item_id")
            child_item_id = data.get("child_item_id")
            child_item_qty1 = data.get("child_item_qty")
            margin = data.get("add_bom_margin")

            if parent_item_id and child_item_id and child_item_qty1 and margin:
                try:
                    child_item = Item.query.filter_by(id=child_item_id).first()
                    parent_item = Item.query.filter_by(id=parent_item_id).first()
                    bom_data = BOM(parent_item=parent_item, child_item=child_item, child_item_qty=float(child_item_qty1),
                                child_item_unit=child_item.unit, database=database, margin=margin)
                    db.session.add(bom_data)
                    db.session.commit()
                    return {'message':'bom added successfully', 'item_id': parent_item_id}, 200
                except:
                    return {'message':'check input'}, 401
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------      

class edit_bom_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            edit_bom_id = data.get("edit_bom_id")
            edit_bom_qty = data.get("edit_bom_quant")
            edit_bom_margin = data.get("edit_bom_margin")

            if edit_bom_qty and edit_bom_id and edit_bom_margin:
                try:
                    edit_bom = BOM.query.filter_by(id=edit_bom_id).first()
                    edit_bom.child_item_qty = float(edit_bom_qty)
                    edit_bom.margin = float(edit_bom_margin)
                    db.session.commit()
                    return {'message':'bom edited successfully', 'item_id':edit_bom.parent_item_id}, 200
                except:
                    return {'message':'check input'}, 401
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class delete_bom_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            delete_bom_id = data.get("bom_delete_id")
            if delete_bom_id:
                try:
                    delete_bom = BOM.query.filter_by(id=delete_bom_id).first()
                    db.session.delete(delete_bom)
                    db.session.commit()
                    return {'message':'bom deleted successfully', 'item_id':delete_bom.parent_item_id}, 200
                except:
                    return {'message':'check input'}, 401
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class add_category_to_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            add_category_item_id = data.get("add_category_item_id")
            add_category_id_list = data.get("add_category_id_list",[])

            if add_category_id_list and add_category_item_id:
                res = []
                for add_category_id in add_category_id_list:
                    try:
                        item = Item.query.filter_by(database=database, id=add_category_item_id).first()
                        category = Category.query.filter_by(database=database, id=add_category_id).first()
                        item_cat = ItemCategory.query.filter_by(database=database, item=item, category=category).first()
                        if item_cat:
                            res.append(f"Category already present in the item. item_id={item.id}")
                            continue
                        item_category = ItemCategory(database=database, item=item, category=category)
                        db.session.add(item_category)
                        db.session.commit()
                        res.append(f"Category added successfully. item_id={item.id}")
                    except:
                        res.append(f"error occured in adding Category to item. item_id={item.id}")
                return {'message': 'Categories added successfully' , 'result':res}, 200
            return {'message':'check input'}, 401

        
#----------------------------------------------------------------

class delete_category_from_item(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            delete_category_item_id = data.get("delete_category_item_id")
            delete_category_id = data.get("delete_category_id")

            if delete_category_id and delete_category_item_id:
                category = Category.query.filter_by(database=database, id=delete_category_id).first()
                item = Item.query.filter_by(database=database, id=delete_category_item_id).first()
                item_category = ItemCategory.query.filter_by(database=database, item=item, category=category).first()
                db.session.delete(item_category)
                db.session.commit()
                return {'message': 'Category deleted successfully' , 'item_id':item.id}, 200
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class edit_inventory_levels(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = data.get("item_id")
            mode = data.get("consumption_mode")
            min_level = data.get("edit_inventory_level_min")
            max_level = data.get("edit_inventory_level_max")

            if mode and min_level and max_level:
                try:
                    item = Item.query.filter_by(database=database, id=item_id).first()
                    item_inv = item.iteminventory
                    if item_inv:
                        item_inv.consumption_mode = mode
                        item_inv.min_level = min_level
                        item_inv.max_level = max_level
                        db.session.commit()
                    return {'message': 'inventory edited successfully'}, 200
                except:
                    return {'message':'check input'}, 401
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class edit_finance_info(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = data.get("item_id")
            hsn_code = data.get("hsn_code")
            cost_price = data.get("cost_price")
            sale_price = data.get("sale_price")
            tax = data.get("tax")

            if hsn_code and cost_price and sale_price and tax:
                item = Item.query.filter_by(database=database, id=item_id).first()
                item_fin = item.itemfinance
                if item_fin:
                    item_fin.hsn_code = hsn_code
                    item_fin.cost_price = cost_price
                    item_fin.sale_price = sale_price
                    item_fin.tax = tax
                    db.session.commit()
                return {'message': 'finance edited successfully'}, 200
            return {'message':'check input'}, 401
        
#-------------------------------------------------------------

class edit_additional_fields(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            item_id = data.get("item_id")
            additional_fields_flag = data.get("additional_fields_flag")

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
                    additional_field_edit_value = data.get(f"{field_name}_edit")
                    if additional_field_edit_value:
                        item_custom_field = ItemCustomField.query.filter_by(database=database, item=item, field_name=field_name).first()
                        if not item_custom_field:
                            item_custom_field = ItemCustomField(field_name=field_name, field_value=additional_field_edit_value, item=item, database=database)
                            db.session.add(item_custom_field)
                        else:
                            item_custom_field.field_value = additional_field_edit_value
                        db.session.commit()
                return {'message': 'additional edited successfully'}, 200
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class add_bom_items(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
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
                if (3 * len(id_list)) == (len(qty_list) + len(unit_list) + len(margin_list)):
                    for bom_item in bom_items:
                        db.session.delete(bom_item)
                    for i in range(len(id_list)):
                        child_item = Item.query.filter_by(database=database, id=id_list[i]).first()
                        if child_item in item_parent_tree:
                            print(f"Cannot add {child_item.name}. It exists in the BOM chain!")
                            continue
                        unit = unit_list[i]
                        print(unit, "23444")
                        conversion_factor = get_conversion_factor(database, child_item, unit)
                        qty = float(qty_list[i]) / conversion_factor
                        margin = margin_list[i]
                        bom_map = BOM(database=database, parent_item=parent_item, child_item=child_item, child_item_qty=qty, margin=margin)
                        db.session.add(bom_map)
                        db.session.commit()
                    return {'message': 'Successfully Added BOM!'}, 200
                else:
                    return {'message': 'Invalid Request FOR BOM!'}, 401
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

class delete_unit(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        if current_user["role"] == 'gjfkADMIN':
            return {'message':'method not allowed'} , 401
        else:
            database = Data.query.filter_by(id=current_user["data"]).first()
            delete_unit_id = data.get("delete_unit_id")
            if delete_unit_id:
                unit_mapping = ItemUnit.query.filter_by(database=database, id=delete_unit_id).first()
                db.session.delete(unit_mapping)
                db.session.commit()
                flash("Deleted Unit!", "success")
                return {'message': 'unit deleted'}, 200
            return {'message':'check input'}, 401
        
#----------------------------------------------------------------

def searchitemouter(k, item_name, item_id, filters, data):
    items = []
    if filters:
        try:
            filters_list = filters["filters_array"]
            filter_type = filters["filter_type"]
            if filter_type == "inclusive":
                items = db.session.query(Item).join(ItemCategory).filter(
                        ItemCategory.category_id.in_(filters_list), Item.data_id == data).all()
            else:
                cat_count = len(filters_list)
                items_filter = db.session.query(
                    Item.id, db.func.count(ItemCategory.id).label("category_count")).join(
                    Item, ItemCategory.item_id == Item.id).filter(
                    Item.data_id == data, ItemCategory.category_id.in_(filters_list)).group_by(Item.id).all()
                filter_df =pd.DataFrame(items_filter, columns=["id", "cat_count"])
                filter_df = filter_df[filter_df["cat_count"] == cat_count]
                items = db.session.query(Item).filter(Item.id.in_(filter_df["id"]), Item.data_id == data).all()
        except:
            print("Filters invalid")
    if item_name:
        if not filters:
            items = (Item.query.filter(Item.data_id == data).all())
        item_scores = [(item, compare_strings(item_name.lower(), item.name.lower(), item.code.lower())) for item in items]
        item_scores.sort(key=lambda x: x[1], reverse=True)
        if k>0:
            top_k_matches = item_scores[:k]
        else:
            top_k_matches = item_scores
        items = [match[0] for match in top_k_matches]
    if item_id:
        items = Item.query.filter_by(id =item_id, data_id = data).all()
    results = [{'id': item.id,'name': item.name,'unit': item.unit,'rate': item.rate,'code': item.code,'raw_flag': item.raw_flag,'regdate':str(item.regdate),
                'itemfinance': {'cost_price': item.itemfinance.cost_price,'sale_price': item.itemfinance.sale_price,'tax': item.itemfinance.tax,'hsn_code': item.itemfinance.hsn_code
                } if item.itemfinance else None} for item in items]
    return results


class search_item(Resource):
    @jwt_required()
    @requires_role(['BASIC'],0)
    def post(self):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        print("item search request recvd ")
        req_json= request.get_json()
        k = int(req_json.get('k', 10))  # Default value is 10
        item_name =req_json.get('name',None)
        item_id = req_json.get('id',None)
        filters = req_json.get('filters', None)
        results = searchitemouter(k, item_name, item_id, filters, current_user['data'])
        return results, 200
        
        
#----------------------------------------------------------------

class getunits(Resource):
    @jwt_required()
    @requires_role(['BASIC'],0)
    def get(self):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        units = Unit.query.filter_by(database=database).all()
        relations = UnitMapping.query.filter_by(database=database).all()
        return {"units":createjson(units) ,"relations":createjson(relations)}, 200
    
class createunit(Resource):
    @jwt_required()
    @requires_role(['BASIC'],1)
    def post(self):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        data = request.get_json()
        unitName = data.get("unitName")
        unitId = data.get("unitId")
        if unitName:
            unitName = unitName.upper()
            unit_check = Unit.query.filter_by(database=database, name = unitName).first()
            if unit_check:
                return {"message": "Unit already exists"}, 302
            if unitId:
                unit_edit = Unit.query.filter_by(database=database, id = unitId).first()
                unit_edit.name = unitName
                db.session.commit()
                return {"message": "Unit edited successfully"}, 302
            new_unit = Unit(name=unitName, database=database)
            db.session.add(new_unit)
            db.session.commit()
            return {"message": "Unit added successfully"}, 302
        return {"message":"check input"}, 402
        
        
class createconversion(Resource):
    @jwt_required()
    @requires_role(['BASIC'],1)
    def post(self):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        data = request.get_json()
        item_id = data.get('itemId')
        to_unit_name = data.get('toUnit')
        conversion_factor = data.get('conversionFactor')
        to_unit_type = data.get('toUnitType')
        if item_id and to_unit_name and conversion_factor and to_unit_type:
            item = Item.query.filter_by(database=database, id= item_id).first()
            item_unit = ItemUnit(database=database,item=item, unit_name = to_unit_name, conversion_factor=conversion_factor, unit_type = to_unit_type)
            db.session.add(item_unit)
            db.session.commit()
            return {"message": "Unit relation modified successfully"}, 302
        return {"message": "check input"}, 401


class units_relation_api(Resource):
    @jwt_required()
    @requires_role(['BASIC'],1)
    def post(self):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        data = request.get_json()
        item_ids = data.get('item_ids[]',[])
        response_data = {}
        for item_id in item_ids:
            item = Item.query.filter_by(database=database, id=item_id).first()
            item_units = ItemUnit.query.filter_by(database=database, item=item).all()
            response_data[item_id] = {}
            for item_unit in item_units:
                response_data[item_id][item_unit.unit_name] = item_unit.conversion_factor
            response_data[item_id][item.unit] = 1
        return jsonify(response_data), 200
    
#----------------------------------------------------------------

