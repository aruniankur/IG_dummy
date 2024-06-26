from flask import Flask, request, jsonify, make_response, request, render_template, url_for, Blueprint
from flask_restful import Api, Resource
from models import User, Data, Workstation, ZohoInfo, UserDataMapping, Subscription, SubDataMapping, Company, DataConfiguration
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity,set_access_cookies, unset_jwt_cookies
from models import db
from functools import wraps
from routeimport.decorators import requires_role

def outerdecorator(arg1, arg2):
    def my_decorator(f):
        @wraps(f)  # Preserve metadata from the original function
        def wrapper(*args, **kwargs):
            current_user = get_jwt_identity()
            print(current_user, arg1, arg2)
            print("Before calling the function")
            kwargs['arg1'] = arg1
            result = f(*args, **kwargs)
            print("After calling the function")
            return result
        return wrapper
    return my_decorator


class Login(Resource):
        def post(self):
            data = request.get_json()
            from_page = data.get("referer", None)
            email = data.get('email')
            password = data.get('password')
            if email and password:
                user = User.query.filter_by(email=email).first()
                if not user:
                    return {'message': 'Invalid username or password'}, 401
                if not (check_password_hash(user.password, password) or check_password_hash(user.password, password+user.email.lower()) or password==user.password):
                    return {'message': 'Invalid username-password 2'}, 401
                if user.token and (len(user.token) == 32 or user.access_role == 'PENDING'):
                    return {'message':'User found, email not verified',
                            'name': user.name,
                            'email': user.email }, 401
                ta_info = {
                    'user_id': user.id,
                    'name': user.name.upper(),
                    'email': user.email,
                    'data': user.data_id,
                    'role': user.access_role.upper()
                }
                print(user.database)
                workstation = Workstation.query.filter_by(database=user.database, name=user.name+"_primary_ws").first()
                if not workstation:
                    workstation = Workstation(primary_flag="YES", name=user.name+"_primary_ws", database=user.database)
                    db.session.add(workstation)
                    db.session.commit()
                ta_info['workstation_id'] = workstation.id
                access_token = create_access_token(identity=ta_info)
                user.token = access_token
                db.session.commit()
                response = make_response(jsonify({'login': True, 'token': access_token}), 200)
                set_access_cookies(response, access_token)
                return response
            return {'message': 'Missing email or password'}, 400
        
        
# class Protected(Resource):
#     @jwt_required()
#     @outerdecorator('aruni','ankur')
#     def get(self , arg1):
#         current_user = get_jwt_identity()
#         #print(current_user)
#         print(f'arg1 passed to get: {arg1}')
#         return {'logged_in_as': current_user}, 200
    

#["VIEWER", "EDITOR"]
#["INVENTORY", "PRODUCTION", "WORKSTATION", "ORDERS", "PURCHASE", "MRP", "MASTERS"]

class Protected(Resource):
    @jwt_required()
    @requires_role(['MASTERS'],0)
    def get(self):
        current_user = get_jwt_identity()
        #print(current_user)
        return {'logged_in_as': current_user}, 200

class checkAuthentication(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        try:
            if current_user:
                user = User.query.filter_by(email=current_user['email']).first()
                if user.token:
                    return {"status" : "pass"}, 200
                else:
                    return {"status": "fail"}, 200
            else:
                return {"status": "fail"}, 200
        except:
            return {"status": "fail internally"}, 200
        
        
class Logout(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        if current_user:
            user = User.query.filter_by(email=current_user['email']).first()
            user.token = None
            db.session.commit()
            response = make_response(jsonify({"msg": "logout successful"}),200)
            unset_jwt_cookies(response)
            return response
        response = make_response(jsonify({"msg": "unauthorised access"}),400)
        unset_jwt_cookies(response)
        return response
    
    
class VerifyEmail(Resource):
    def get(self, token1):
        print(token1)
        user = User.query.filter_by(token=token1).first()
        if user:
            user.access_role = 'BASIC'
            user.token = None  # Remove the token after verification
            db.session.commit()
            return {'message': 'Email verified successfully. Login again to continue.'}, 200
        else:
            return {'message': 'Invalid verification token.'}, 400

