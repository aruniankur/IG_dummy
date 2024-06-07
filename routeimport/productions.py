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

def demand_calculation_function(active_orders_df, inventory_stock_df, items_df, boms_df, raw_flag='NO', semi_flag='YES'):
    demand_df = pd.merge(active_orders_df, inventory_stock_df, on='item_id', how='left')
    demand_df["demand_qty"] = demand_df["total_quantity1"]
    demand_df["parent_item_id"] = demand_df["item_id"]
    demand_df = pd.merge(demand_df, items_df, left_on="parent_item_id", right_on='item_id', how='left')
    demand_df = demand_df[demand_df["raw_flag"] == 'NO']
    demand_df_merged = pd.merge(demand_df, boms_df, left_on='parent_item_id', right_on='parent_item_id', how='left')
    demand_df_merged.dropna(subset=['bom_id'],inplace=True)
    demand_df_merged["demand_qty"] = demand_df_merged["demand_qty"]*demand_df_merged["child_item_qty"]
    demand_df_merged["parent_item_id"] = demand_df_merged["child_item_id"]
    demand_df = demand_df_merged[["parent_item_id", "demand_qty"]]
    result_demand = pd.DataFrame(columns=["item_id", "demand_qty"])
    while len(demand_df["parent_item_id"]):
        demand_df = pd.merge(demand_df, items_df, left_on="parent_item_id", right_on='item_id', how='left')
        if semi_flag == 'YES' and raw_flag=='NO':
            demand_to_apppend = demand_df[demand_df["raw_flag"] == 'NO']
        elif raw_flag == "YES" and semi_flag=='NO':
            demand_to_apppend = demand_df[demand_df["raw_flag"] == 'YES']
        else:
            demand_to_apppend = demand_df
        demand_to_apppend = demand_to_apppend[["parent_item_id", "demand_qty"]].rename(columns={'parent_item_id':'item_id'})
        result_demand = pd.concat([result_demand, demand_to_apppend], ignore_index=True)
        demand_df = demand_df[demand_df["raw_flag"] == 'NO']
        demand_df_merged = pd.merge(demand_df, boms_df, left_on='parent_item_id', right_on='parent_item_id', how='left')
        demand_df_merged.dropna(subset=['bom_id'],inplace=True)
        demand_df_merged["demand_qty"] = demand_df_merged["demand_qty"]*demand_df_merged["child_item_qty"]
        demand_df_merged["parent_item_id"] = demand_df_merged["child_item_id"]
        demand_df = demand_df_merged[["parent_item_id", "demand_qty"]]
    result_demand = result_demand.groupby('item_id')['demand_qty'].sum().reset_index()
    return result_demand

def demand_calculation_function_inventory(active_orders_df_items_list, inventory_stock_df, items_df, boms_df, raw_flag='NO', semi_flag='YES'):
    demand_df = inventory_stock_df[inventory_stock_df["item_id"].isin(active_orders_df_items_list)]
    demand_df["demand_qty"] = demand_df["total_quantity2"]
    demand_df["parent_item_id"] = demand_df["item_id"]
    demand_df = pd.merge(demand_df, items_df, left_on="parent_item_id", right_on='item_id', how='left')
    demand_df = demand_df[demand_df["raw_flag"] == 'NO']
    demand_df_merged = pd.merge(demand_df, boms_df, left_on='parent_item_id', right_on='parent_item_id', how='left')
    demand_df_merged.dropna(subset=['bom_id'],inplace=True)
    demand_df_merged["demand_qty"] = demand_df_merged["demand_qty"]*demand_df_merged["child_item_qty"]
    demand_df_merged["parent_item_id"] = demand_df_merged["child_item_id"]
    demand_df = demand_df_merged[["parent_item_id", "demand_qty"]]
    result_demand = pd.DataFrame(columns=["item_id", "demand_qty"])
    while len(demand_df["parent_item_id"]):
        demand_df = pd.merge(demand_df, items_df, left_on="parent_item_id", right_on='item_id', how='left')
        if semi_flag == 'YES' and raw_flag=='NO':
            demand_to_apppend = demand_df[demand_df["raw_flag"] == 'NO']
        elif raw_flag == "YES" and semi_flag=='NO':
            demand_to_apppend = demand_df[demand_df["raw_flag"] == 'YES']
        else:
            demand_to_apppend = demand_df
        demand_to_apppend = demand_to_apppend[["parent_item_id", "demand_qty"]].rename(columns={'parent_item_id':'item_id'})
        result_demand = pd.concat([result_demand, demand_to_apppend], ignore_index=True)
        demand_df = demand_df[demand_df["raw_flag"] == 'NO']
        demand_df_merged = pd.merge(demand_df, boms_df, left_on='parent_item_id', right_on='parent_item_id', how='left')
        demand_df_merged.dropna(subset=['bom_id'],inplace=True)
        demand_df_merged["demand_qty"] = demand_df_merged["demand_qty"]
        demand_df_merged["demand_qty"] = (demand_df_merged["demand_qty"]*demand_df_merged["child_item_qty"]) 
        demand_df_merged["parent_item_id"] = demand_df_merged["child_item_id"]
        demand_df = demand_df_merged[["parent_item_id", "demand_qty"]]
    result_demand = result_demand.groupby('item_id')['demand_qty'].sum().reset_index()
    return result_demand



