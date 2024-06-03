from flask import Flask, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import current_app
from sqlalchemy import desc

from models import db, Labor, Item, BOM, Customer, Category, Prodchart, Joballot, Order, Data, ProdchartItem, Inventory, OrderItem, Workstation, WorkstationMapping, WorkstationJob, WorkstationResource, BGProcess, MobileNumber
from decorators import requires_role, get_segment, createjson
from datetime import datetime, date
from collections import OrderedDict
from operator import itemgetter
import pandas as pd
import requests
import json
from iteminfo import search_item
from celery.result import AsyncResult
import os 
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

table_names = {"ws_jobs":WorkstationJob, "ws_resources":WorkstationResource}

# class addrecord(Resource):
#     @jwt_required
#     @requires_role(['MASTERS'],1)
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()

# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#         fields = data.get('fields')
#     table_name = data.get("table_name")
        