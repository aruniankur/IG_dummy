from flask import Flask, request, jsonify, make_response, request, render_template, url_for, Blueprint
import random
import string
import secrets
from flask_restful import Api, Resource
from datetime import datetime, timedelta
from models import User, Data, Workstation, ZohoInfo, UserDataMapping, Subscription, SubDataMapping, Company, DataConfiguration
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity,set_access_cookies, unset_jwt_cookies
from flask_mail import Mail, Message
import uuid
import smtplib
from routeimport import dashboard
from routeimport import settingsuri
from routeimport import authorise
from routeimport import item
from routeimport import iteminfo

def register_routes(app,db):
    app.config['JWT_SECRET_KEY'] = 'YL8ck4TG1@cJvGfY#e5USH93@xCGu9'
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
    app.config['MAIL_SERVER']='smtp.gmail.com'
    app.config['MAIL_PORT'] = 465
    app.config['MAIL_USERNAME'] = 'admin@Intaligen.com'
    app.config['MAIL_PASSWORD'] = '*****'
    app.config['MAIL_USE_TLS'] = False
    app.config['MAIL_USE_SSL'] = True
    mail = Mail(app)
    api = Api(app)
    jwt = JWTManager(app)
    class Index(Resource):
        def get(self):
            return {'test': 'Subject'}
    
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
        
    class Signup(Resource):
        def post(self):
            data = request.get_json()
            name=data.get("name")
            email=data.get("email")
            password1=data.get("password1")
            password2=data.get("password2")
            status = data.get("status")
            if name and email and password1 and password2 and status:
                email_check = User.query.filter_by(email=email).first()
                if email_check:
                    return {'message': 'Email already exists. Try logging in.'}, 401
                if password1 != password2:
                    return {'message': 'PASSWORDS MISMATCH'}, 401
                elif status == "new":
                        res = str(uuid.uuid4())[:12]
                        verification_token = secrets.token_hex(32)
                        print(verification_token)
                        # with app.test_request_context():
                        #     verification_url = url_for("app.VerifyEmail", token=verification_token, _external=True)
                        #     print(f'Generated verification URL: {verification_url}')
                        verification_url = 'https://ig-dummy.onrender.com'+'/verify_email/' + verification_token
                        email_body = f"Click the link below to verify your email:\n{verification_url}"
                        #print(email_body)
                        hashed_password = generate_password_hash(password1+email.lower(), method='pbkdf2:sha256')
                        #print(hashed_password)
                        #return {'message': 'User registered successfully. Check your email for verification'}, 200
                        if sendmail(email, email_body):
                            user = User(name=name ,email=email, password=hashed_password, access_role="PENDING",token=verification_token, operation_role="ADMIN")
                            db.session.add(user)
                            db.session.commit()
                            return {'message': 'User registered successfully. Check your email for verification'}, 200
                        else:
                            return {'message': 'try again, Error occured'}, 401
    
    class createCompany(Resource):
        @jwt_required()
        def post(self):
            current_user = get_jwt_identity()
            try:
                user_id = current_user['user_id']
                user_name = current_user['name']
            except:
                return jsonify({'message': 'error in token Login.'}), 400
            user1 = User.query.filter_by(id = user_id).first()
            if not user1:
                return jsonify({'message': 'Please Login.'}), 400
            data = request.get_json()
            subscription_id = data.get("subscription_id")
            company_name = data.get("company_name")
            if subscription_id and company_name:
                subscription = Subscription.query.filter_by(id = subscription_id, user = user1).first()
                if subscription:
                    res = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))
                    print(res)
                    flag = True
                    while flag:
                        db_check = Data.query.filter_by(key = res).first()
                    if db_check:
                        res = ''.join(random.choices(string.ascii_uppercase + string.digits, k = 10))
                    else:
                        flag = False
                    print('level 2 done')
                    data1 = Data(name = company_name+"_"+res, key=res)
                    db.session.add(data1)
                    db.session.commit()
                    workstation = Workstation(primary_flag="YES",name = data1.name+"_primary_ws", database=data1)
                    db.session.add(workstation)
                    db.session.commit()
                    company = Company(database=data1, name=company_name)
                    db.session.add(company)
                    db.session.commit()
                    user1.access_role="ADMIN"
                    userdatamap = UserDataMapping(user = user1, database=data1, access_role="ADMIN", operation_role="ADMIN")
                    db.session.add(userdatamap)
                    db.session.commit()
            return jsonify({'message': 'Company Created Sucessfully'}), 302
    
    
    # class UserDashboard(Resource):
    #     @jwt_required()
    #     def get(self):
    #     # Implement logic to fetch user dashboard data
    #     def post(self):
            
    api.add_resource(Index, '/')
    api.add_resource(authorise.Login, '/login')
    api.add_resource(authorise.Protected, '/protected')
    api.add_resource(authorise.Logout, '/logout')
    api.add_resource(Signup, '/signup')
    api.add_resource(authorise.VerifyEmail, '/verify_email/<token1>')
    api.add_resource(authorise.checkAuthentication, '/checkAuthentication')
    api.add_resource(createCompany, '/createCompany')
    api.add_resource(dashboard.userdashboard, '/userdashboard')
    api.add_resource(dashboard.reverification, '/reverification')
    api.add_resource(dashboard.datakey, '/datakey')
    api.add_resource(dashboard.change_password, '/change_password')
    api.add_resource(dashboard.switchdataflag, '/switchdataflag')
    api.add_resource(dashboard.configurations, '/configurations')
    api.add_resource(settingsuri.Settings, '/Settings')
    api.add_resource(settingsuri.generatekey, '/generatekey')
    api.add_resource(settingsuri.DeleteUser, '/DeleteUser')
    api.add_resource(settingsuri.Updatememberaccess, '/Updatememberaccess')
    #----------------------------------------------------------------
    api.add_resource(item.list_items, '/ListItems')
    api.add_resource(item.add_item, '/AddItem')
    api.add_resource(item.edit_items, '/edit_items')
    api.add_resource(item.search_items, '/search_items')
    #----------------------------------------------------------------
    api.add_resource(iteminfo.itemsinfo, '/ItemsInfo')
    api.add_resource(iteminfo.add_bom_item, '/add_bom_item')
    api.add_resource(iteminfo.edit_bom_item, '/edit_bom_item')
    api.add_resource(iteminfo.delete_bom_item, '/delete_bom_item')
    api.add_resource(iteminfo.add_category_to_item, '/add_category_to_item')
    api.add_resource(iteminfo.delete_category_from_item, '/delete_category_from_item')
    api.add_resource(iteminfo.edit_additional_fields,'/edit_additional_fields')
    api.add_resource(iteminfo.edit_inventory_levels,'/edit_inventory_levels')
    api.add_resource(iteminfo.edit_finance_info,'/edit_finance_info')
    api.add_resource(iteminfo.add_bom_items,'/add_bom_items')
    api.add_resource(iteminfo.delete_units,'/delete_units')