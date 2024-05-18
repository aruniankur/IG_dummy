from flask import Flask, request, jsonify, make_response, request, render_template, url_for, Blueprint
import secrets
from flask_restful import Api, Resource
from models import User, Data, Workstation, ZohoInfo, UserDataMapping, Subscription, SubDataMapping, Company, DataConfiguration
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import smtplib
from models import db

#----------------------------------------------------------------
def sendmail(mail, text):
    subject = "Email Verification - Intaligen" # Combine the subject and body with a blank line
    email_message = f"Subject: {subject}\n\n{text}" # Set up the SMTP server
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls() # Login to your email account
    server.login("nakaajaaaaddkc@gmail.com", "Ymygmnacfzmgqcia") # Send the email
    try:
        server.sendmail("nakaajaaaaddkc@gmail.com", mail , email_message)
        server.quit()
        print("Email sent successfully.")
        return True
    except:
        server.quit()
        print("Email cannot be successful.")
        return False
#----------------------------------------------------------------
class userdashboard(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id = user_id).first()
        if not user:
            return {'error':'no user found, please login'}, 400
        else:
            return jsonify(user.to_dict()), 200
#----------------------------------------------------------------
class reverification(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        re_verification_email = data['re_verification_email']
        user = User.query.filter_by(email = re_verification_email).first()
        if user:
            verification_token = secrets.token_hex(32)
            user.token = verification_token
            db.session.commit()
            verification_url = 'https://ig-dummy.onrender.com'+'/verify_email/' + verification_token
            email_body = f"Click the link below to verify your email:\n{verification_url}"
            if sendmail(re_verification_email, email_body):
                return {'message': 'Re-verification mail send successfully. Check your email for verification'}, 200  
            else:
                return {'message': 'try again, Error occured'}, 401
        else:
            return {'error':'no user found, please check email'}, 401
        return True
#----------------------------------------------------------------
class datakey(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        data_key = data["database_key"]
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if data_key and user:
            data = Data.query.filter_by(key=data_key).first()
            if data:
                user.database=data
                db.session.commit()
                user_data_map = UserDataMapping(user = user, database = data, access_role="BASIC", operation_role=user.operation_role)
                db.session.add(user_data_map)
                db.session.commit()
                return {'message': 'Successfully added/updated datakey'}, 200
            else:
                return {'message': 'incorrect datakey'}, 401
        else:
            return {'message': 'user not found, please login'}, 401
 #----------------------------------------------------------------   
class change_password(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        old_pass = data["old_pass"]
        new_pass = data["new_pass"]
        new_pass_2 = data["new_pass_2"]
        if old_pass and new_pass and new_pass_2:
            if old_pass == new_pass:
                return {'message': 'same new password'}, 401
            if new_pass != new_pass_2:
                return {'message': 'check new password, password not same'}, 401
            current_user = get_jwt_identity()
            user_id = current_user['user_id']
            user = User.query.filter_by(id=user_id).first()
            if user:
                if check_password_hash(user.password, old_pass+user.email.lower()):
                    hashed_password = generate_password_hash(new_pass+user.email.lower(), method='pbkdf2:sha256')
                    user.password = hashed_password
                    db.session.commit()
                    return {'message': 'Successfully updated password'}, 200
                else:
                    return {'message': 'incorrect old password'}, 401
            else:
                return {'message': 'user not found, please login again '}, 401
        return {'message': 'incorrect method called'}, 401
#----------------------------------------------------------------
class switchdataflag(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        switch_data_flag = data["switch_data_flag"]
        database_name = data["database_name"]
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if database_name and switch_data_flag and user:
            database = Data.query.filter_by(name=database_name).first()
            user.data_id = database.id
            user_data_map = UserDataMapping(user = user, database = user.database, access_role=user.access_role, operation_role=user.operation_role)
            db.session.add(user_data_map)
            db.session.commit()
            user_data_maps = user.userdatamappings
            for member in user_data_maps:
                if member.operation_role not in ["ADMIN", "BASIC"]:
                    access_dict = json.loads(member.operation_role)
                    print(type(access_dict))
                else:
                    access_dict = {"pages":["INVENTORY", "PRODUCTION", "WORKSTATION", "ORDERS", "PURCHASE", "MRP", "MASTERS"],
                                    "access":{"INVENTORY":"VIEWER",
                                    "PRODUCTION":"VIEWER", "WORKSTATION":"VIEWER", "ORDERS":"VIEWER",
                                    "PURCHASE":"VIEWER", "MRP":"VIEWER", "MASTERS":"VIEWER"}}
                    dict_string = json.dumps(access_dict)
                    member.operation_role = dict_string
                    db.session.commit()
            return {'message':'Data Flag changed successfully'} , 200
        else:
            return {'message':'error occurred'} , 401
        
#----------------------------------------------------------------------------
        
class configurations(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if user['operation_role'] == 'ADMIN':
            database = Data.query.filter_by(id = user['data_id']).first()
            data_config = DataConfiguration.query.filter_by(database=database).first()
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
            item_master_dict = json.loads(data_config.item_master_config)
            field_to_add = request.form.get("item_master_additional_field")
            if field_to_add:
                item_master_dict["ADDITIONAL_FIELDS"].append({"name":field_to_add})
                data_config.item_master_config = json.dumps(item_master_dict)
                db.session.commit()
                return {'message':'redirect to setting'} , 302
        else:
            return {'message':'operation not allowed'} , 200