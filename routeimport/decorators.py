from functools import wraps
from flask import session, redirect, request, flash
from models import User, ItemUnit, Item, Data, UserDataMapping
import json
from flask_jwt_extended import get_jwt_identity

def requires_role(access_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = get_jwt_identity()
            if not current_user:
                return {"message": "token not found"} , 401
            user = User.query.filter_by(id=current_user["user_id"]).first()
            if "KING" in access_roles:
                if(user.email in ['vedant@intaligen.com', 'vivek@intaligen.com']):
                    return f(*args, **kwargs)
            user_data_mapping = UserDataMapping.query.filter_by(data_id = current_user["data"], user=user).first()
            if not user_data_mapping:
                return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"} , 300
            if user_data_mapping.access_role != 'ADMIN' and 'BASIC' not in access_roles:
                if 'ADMIN' in access_roles:
                    return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"} , 300
                operation_map = json.loads(user_data_mapping.operation_role)
                for page in access_roles:
                    if operation_map['access'][page] in ["VIEWER", "EDITOR"]:
                        return f(*args, **kwargs)
                return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"} , 300
            return f(*args, **kwargs)
        return decorated_function
    return decorator

