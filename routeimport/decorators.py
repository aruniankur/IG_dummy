from functools import wraps
from models import User, UserDataMapping, Data
import json
from flask_jwt_extended import get_jwt_identity
import datetime

#need to change this, only acces_role and level should be there

def requires_role(access_roles, level):
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
            for p in access_roles:
                access_level = operation_map['access'].get(p)
                if level and access_level == "EDITOR":
                    return f(*args, **kwargs)
                elif not level and access_level in ["VIEWER", "EDITOR"]:
                    return f(*args, **kwargs)
            return {'redirect': "redirect to user dashboard", "flash": "ACCESS RESTRICTED!"}, 300
        return decorated_function
    return decorator


# level 1 -> editor, level 0 -> both
#level can be any of the ["NONE", "VIEWER", "EDITOR"]
#page can be any of the ["INVENTORY", "PRODUCTION", "WORKSTATION", "ORDERS", "PURCHASE", "MRP", "MASTERS"]


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