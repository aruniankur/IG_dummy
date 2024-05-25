from functools import wraps
from models import User, UserDataMapping
import json
from flask_jwt_extended import get_jwt_identity


#need to change this, only acces_role and level should be there

def requires_role(access_roles, level, page):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            current_user = get_jwt_identity()
            user = User.query.filter_by(id=current_user["user_id"]).first()
            if "KING" in access_roles and user.email in ['vedant@intaligen.com', 'vivek@intaligen.com']:
                return f(*args, **kwargs)
            user_data_mapping = UserDataMapping.query.filter_by(data_id=current_user["data"], user=user).first()
            if not user_data_mapping:
                return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"}, 300
            if user_data_mapping.access_role == 'ADMIN':
                return f(*args, **kwargs)
            operation_map = json.loads(user_data_mapping.operation_role)
            for p in page:
                if operation_map['access'].get(p) in level:
                    return f(*args, **kwargs)
            return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"}, 300
        return decorated_function
    return decorator

#level can be any of the ["NONE", "VIEWER", "EDITOR"]
#page can be any of the ["INVENTORY", "PRODUCTION", "WORKSTATION", "ORDERS", "PURCHASE", "MRP", "MASTERS"]