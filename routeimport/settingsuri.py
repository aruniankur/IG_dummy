from flask import Flask, request,redirect, jsonify
import random
import string
from flask_restful import Api, Resource
from models import User, Data, Workstation, ZohoInfo, UserDataMapping, Subscription, SubDataMapping, Company, DataConfiguration
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity,set_access_cookies, unset_jwt_cookies
import json
from models import db
import datetime
from sqlalchemy.orm import class_mapper
    
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

class Settings(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        members = User.query.filter_by(data_id=user.data_id).all()
        database=Data.query.filter_by(id = user.data_id).first()
        zoho_info = ZohoInfo.query.filter_by(database=database).first()
        data_config = DataConfiguration.query.filter_by(database=database).first()
        if not database.company:
            company = Company(database=database, name=database.name)
            db.session.add(company)
            db.session.commit()
        if not data_config:
            config_dict = {'ADDITIONAL_FIELDS':[], 'SEARCH_FIELDS':[]}
            invoice_config_dict = {"proforma-invoice":{"invoice-class":"proforma-invoice", "invoice-file": "invoices/proforma_invoice.html"},
            "sales-invoice":{"invoice-class":"sales-invoice", "invoice-file": "invoices/sales_invoice.html"},
            "delivery-slip":{"invoice-class":"delivery-slip", "invoice-file": "invoices/delivery_slip.html"},
            "purchase-invoice":{"invoice-class":"purchase-invoice", "invoice-file": "invoices/purchase_invoice.html"},
            "purchase-order":{"invoice-class":"purchase-order", "invoice-file": "invoices/purchase_order.html"},
            "receive-slip":{"invoice-class":"receive-slip", "invoice-file": "invoices/receive_slip.html"}}
            new_data_config = DataConfiguration(database = database, item_master_config=json.dumps(config_dict), invoice_config = json.dumps(invoice_config_dict))
            db.session.add(new_data_config)
            db.session.commit()
            data_config= new_data_config
        member_access={}
        for member in database.userdatamappings:
            if member.operation_role not in ["ADMIN", "BASIC"]:
                access_dict = json.loads(member.operation_role)
                #print(type(access_dict))
            else:
                access_dict = {"pages":["INVENTORY", "PRODUCTION", "WORKSTATION", "ORDERS", "PURCHASE", "MRP", "MASTERS"],
                                "access":{"INVENTORY":"VIEWER",
                                "PRODUCTION":"VIEWER", "WORKSTATION":"VIEWER", "ORDERS":"VIEWER",
                                "PURCHASE":"VIEWER", "MRP":"VIEWER", "MASTERS":"VIEWER"}}
                dict_string = json.dumps(access_dict)
                member.operation_role = dict_string
                db.session.commit()
            member_access[member.id] = access_dict
        ROLES = ["BASIC", "ADMIN"]
        #print(createjson(database))
        response = {'user': createjson(user), 'members': createjson(members),'roles':ROLES,'zoho_info':createjson(zoho_info),'member_access':member_access, 'item_master_fields':json.loads(data_config.item_master_config),'segment':["settings"],  'database':createjson(database)}
        return response, 200
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if user and user['operation_role'] == 'ADMIN':
            database=Data.query.filter_by(id = user.data_id).first()
            data = request.get_json()
            p_name = data["p_name"]
            p_billing_address = data["p_billing_address"]
            p_shipping_address = data["p_shipping_address"]
            p_gst = data["p_gst"]
            p_phone = data["p_phone"]
            p_email = data["p_email"]
            if p_name:
                p_billing_address = "" if not p_billing_address else p_billing_address
                p_shipping_address = "" if not p_shipping_address else p_shipping_address
                p_gst = "" if not p_gst else p_gst
                p_phone = "" if not p_phone else p_phone
                p_email = "" if not p_email else p_email
                company = database.company
                company.name = p_name
                company.billing_address = p_billing_address
                company.shipping_address = p_shipping_address
                company.gst = p_gst
                company.phone = p_phone
                company.email = p_email
                db.session.commit()
                return {'message':'redirect to setting'}, 200
            return {'message':'please enter name'}, 401
        return {'message':'NOT ALLOWED'}, 401
            
class generatekey(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        data = request.get_json()
        genkey = data['gen_key']
        if user and user['operation_role'] == 'ADMIN' and genkey == '1':
            data=Data.query.filter_by(id = user.data_id).first()
            new_key=''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))
            data.key=new_key
            db.session.commit()
            return {'message':'success', 'new_key':new_key} , 200
        return {'message':'NOT ALLOWED'}, 401
        
            
class DeleteUser(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if user and user.operation_role == 'ADMIN':
            data = request.get_json()
            delete_id = data.get('delete_id')
            if delete_id:
                user_to_delete = User.query.filter_by(id=delete_id).first()
                if user_to_delete and user_to_delete.id == user_id:
                    db.session.delete(user_to_delete)
                    db.session.commit()
                    return {'message': 'User deleted successfully, redirect to logout'}, 200
                else:
                    return {'message': 'User not found'}, 401
            else:
                return {'message': 'Invalid request, delete_id is required'}, 400
        else:
            return {'message': 'Unauthorized access'}, 403

class Updatememberaccess(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if user and user.operation_role == 'ADMIN':
            data = request.get_json()
            member_id = data["member_id"]
            page_names = data["page_names[]"]
            page_access_levels = data["page_access_levels[]"]
            if member_id and page_names and page_access_levels:
                member = UserDataMapping.query.filter_by(id=member_id).first()
                member_dict = json.loads(member.operation_role)
                for i in range(len(page_names)):
                    page_name = page_names[i]
                    access_level = page_access_levels[i]
                    member_dict["access"][page_name] = access_level
                member.operation_role = json.dumps(member_dict)
                db.session.commit()
                return {'message': 'member update successful'}, 200
            else:
                {'message': 'Invalid request, check input'}, 400
        else:
            return {'message': 'Unauthorized access'}, 403
        
        
        
        
