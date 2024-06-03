from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import current_app
from models import db, Labor,User, Item, BOM, Customer, Category, Prodchart, Joballot, Order, Data, ProdchartItem, Inventory, OrderItem, Workstation, WorkstationMapping, WorkstationJob, WorkstationResource, WSJobsProdChartItemMapping, ItemBOM, OrderItemDispatch, DeliveryBatch
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
from datetime import datetime, date
from collections import OrderedDict
from operator import itemgetter
import pandas as pd
import requests
import json
from iteminfo import search_item
from routeimport.workstations import updateMaterialIssue, checkChildJobs
from routeimport.maketostock import mt_stock, max_psbl_amount
from routeimport.utility import get_mobile_numbers
from routeimport.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE
from routeimport.workstations import get_job_totals
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

def extractDatePython():
    today = datetime.now()
    return today.strftime("%Y-%m-%d")

def extractDateSQL(date_text):
    ## format "YYYY-MM-DD time"
    date = date_text[0:10]
    time = date_text[11:]
    date2 = date[8:10]+"/"+date[5:7]+"/"+date[0:4]
    return date2

def ExtractDateForSQL(date_text):
    date = date_text[6:10]+"-"+date_text[3:5]+"-"+date_text[0:2]
    return date

# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])