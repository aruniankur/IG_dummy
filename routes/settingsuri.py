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
import json
import smtplib
from models import db

class Settings(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        user_id = current_user['user_id']
        user = User.query.filter_by(id=user_id).first()
        if user['operation_role'] == 'ADMIN':
            return True
        return False
            
class deleteid(Resource):
    @jwt_required()
    def delete(self):
        return True
    
    