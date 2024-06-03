from flask import Flask,current_app, render_template,current_app, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import jsonify
from models import db, Data, Category, Inventory, Item, User, BGProcess
import random
import string
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
from datetime import datetime, date
import requests
import pandas as pd
import os
import pdfkit
from celery import shared_task
from routeimport.utility import get_mobile_numbers
from routeimport.bot_utility import SEND_MESSAGE
from sqlalchemy import or_
from flask_restful import Api, Resource
from fuzzywuzzy import fuzz
from routeimport.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE
from flask_jwt_extended import jwt_required, get_jwt_identity

def compare_strings(s1, s2):
    if s1 in s2:
        score=100
    else:
        score= fuzz.token_sort_ratio(s1, s2)
    return score


# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])