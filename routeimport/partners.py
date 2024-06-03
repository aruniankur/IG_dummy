from flask_restful import Api, Resource
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
from flask_jwt_extended import jwt_required, get_jwt_identity

# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])