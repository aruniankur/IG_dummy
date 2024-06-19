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
from routeimport.workstations import updateMaterialIssue, checkChildJobs
from routeimport.maketostock import mt_stock, max_psbl_amount
from routeimport.utility import get_mobile_numbers
from routeimport.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE
from routeimport.workstations import get_job_totals
from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from routeimport.iteminfo import searchitemouter

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



class productionchartsnew(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def get(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        CATEGORIES=[]
        categories = Category.query.filter_by(database=database).all()
        for item in categories:
            CATEGORIES.append([item.id, item.name])
            segment = get_segment(request, current_user['data'])
        orders = Order.query.filter_by(database=database, order_type=0, status="Active").all()
        DATA = Prodchart.query.filter(Prodchart.date>= date.today(), Prodchart.data_id==current_user['data']).order_by(Prodchart.date.asc()).all()
        DATA_DICT={}
        for i in DATA:
            d=date.strftime(i.date, '%d-%m-%Y')
            DATA_DICT[i.id] = {"note":i.note, "date":i.date, "chart_items":[]}
            PRODCHART_ITEM = ProdchartItem.query.filter_by(chart_id = i.id).all()
            for ik in PRODCHART_ITEM:
                l=[ik.id, ik.item.name, ik.qty_allot, ik.item_unit, i.date, ik.item.id ]
                DATA_DICT[i.id]["chart_items"].append(l)
        return jsonify(data=DATA_DICT, date=extractDatePython(), categories=CATEGORIES, segment=segment, ORDERS=orders, today=str(date.today()))

#check this
        
class productionbulkentry(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        add_items_check = data.get("add_items_check")
        prod_chart_id = data.get("chart_id")
        order_note = data.get("order_note")
        id_list = data.getlist("items_ids[]", [])
        qty_list = data.getlist("items_qtys[]",[])
        if add_items_check and prod_chart_id:
            prodchart = Prodchart.query.filter_by(id = prod_chart_id, database = database).first() 
            if order_note:
                prodchart.note = order_note
                db.session.commit()   
            if (len(id_list)  != len(id_list)) or (len(id_list) == 0) or (len(qty_list) == 0):
                return {"message": "id list and qty list not of same length or of zero length"}, 401
            #prod_chart_items = ProdchartItem.query.filter_by(prodchart = prodchart, database=database)
            qty_list = [float(qty) for qty in qty_list]
            df = pd.DataFrame({'ID': id_list, 'Qty': qty_list})
            result_df = df.groupby('ID')['Qty'].sum().reset_index()
            id_list = result_df['ID'].tolist()
            qty_list = result_df['Qty'].tolist()
            prodchart_items = ProdchartItem.query.filter_by(prodchart = prodchart, database=database).all()
            workstation = Workstation.query.filter_by(database=database, id=current_user["workstation_id"]).first()
            for item in prodchart_items:
                if str(item.item.id) not in id_list:
                    mapping = WSJobsProdChartItemMapping.query.filter_by(prodchartitem = item).first()
                    ws_job = mapping.workstationjob
                    if checkChildJobs(database.id, ws_job.workstation.id, ws_job.item.id, ws_job.date_allot):
                        flash(f"Item Present in child WS!! Failed to Delete {ws_job.item.name} in {ws_job.workstation.name}", "danger")
                        continue
                    db.session.delete(item)
                    db.session.delete(ws_job)
                    db.session.delete(mapping)
            for i in range(len(id_list)):
                item = Item.query.filter_by(id =id_list[i], database=database).first()
                prodchart_item_check = ProdchartItem.query.filter_by(database=database, prodchart=prodchart, item=item).first()
                if prodchart_item_check:
                    print(item.name, qty_list[i], "CHECKKK!")
                    print(prodchart_item_check.id, prodchart_item_check.item.name,prodchart_item_check.qty_allot)
                    prodchart_item_check.qty_allot = qty_list[i]
                    ws_job = prodchart_item_check.wsprodchartitemmappings[0].workstationjob
                    ws_totals = get_job_totals(database.id, item.id, prodchart.date, ws_job.workstation.id )
                    ws_job.qty_allot = ws_job.qty_allot + qty_list[i] - ws_totals["qty_allot"]  
                    print(item.name,prodchart_item_check.qty_allot)
                    db.session.commit()
                    print("Existing Item Found!!")
                else:
                    print("New Item Found!!")
                    job_inventory = Inventory(item=item,regdate=prodchart.date, item_unit = item.unit, qty = 0, note=f"Receipt_{workstation.name}_{prodchart.date}", database=database)
                    db.session.add(job_inventory)
                    db.session.commit()
                    prodchart_new_item = ProdchartItem(database=database, prodchart=prodchart, item=item, qty_allot = qty_list[i], item_unit=item.unit,
                        item_rate= item.rate)
                    ws_job = WorkstationJob(database=database, item=item, date_allot = prodchart.date, qty_allot = qty_list[i], workstation=workstation,
                        inventory = job_inventory)
                    db.session.add(ws_job)
                    db.session.add(prodchart_new_item)
                    db.session.commit()
                    wsjobprodchartitemmapping = WSJobsProdChartItemMapping(database=database, workstationjob = ws_job, prodchartitem = prodchart_new_item)
                    db.session.add(wsjobprodchartitemmapping)
                    db.session.commit()
            updateMaterialIssue(workstation, prodchart.date)
            numbers_list = get_mobile_numbers(current_user["data"])
            user = User.query.filter_by(id=current_user["user_id"]).first()
            result = []
            for number in numbers_list:
                resp = SEND_CUSTOM_MESSAGE(f"Items added to production chart dated {prodchart.date} by {user.name}!", number)
                result.append([f"Items added to production chart dated {prodchart.date} by {user.name}!", number])
            return {"message": result}, 200
        
        
class addprodchart(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        date2 = data.get('date2')
        note = data.get('chart_note')
        if date2:
            if not note:
                note=""
            prodchart = Prodchart(date=date2, note=note, database=database)
            db.session.add(prodchart)
            db.session.commit()
            return {"message": "Prodchart added successfully"}, 200
        

class prodchartquantity(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        chart_id = data.get('add_item_chart_id')
        prod_id1 = data.get('prod_id')
        quantity = data.get('quantity')
        if prod_id1 and quantity and chart_id:
            item = Item.query.filter_by(id=prod_id1).first()
            unit = item.unit
            prodchart1 = Prodchart.query.filter_by(id=chart_id).first() 
            prodchart_item = ProdchartItem(prodchart = prodchart1, item=item, qty_allot=quantity, item_unit=item.unit, item_rate=item.rate, database=database)
            workstation = Workstation.query.filter_by(database=database, id = current_user["workstation_id"]).first()
            ws_job = WorkstationJob(database=database, item=item, date_allot = prodchart1.date, qty_allot = quantity, workstation=workstation)
            db.session.add(ws_job)
            db.session.add(prodchart_item)
            db.session.commit()
            wsjobprodchartitemmapping = WSJobsProdChartItemMapping(database=database, workstationjob = ws_job, prodchartitem = prodchart_item)
            db.session.add(wsjobprodchartitemmapping)
            db.session.commit()
            updateMaterialIssue(workstation, prodchart1.date)
            return {"message": "quantity added successfully"}, 200
        return {"message":"missing proper input"}, 401
    
class editquantity(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        edit_form_quant = data.get("edit_quant")
        edit_form_id = data.get("edit_id")
        if edit_form_quant and edit_form_id:
            edit_form_quant=float(edit_form_quant)
            edit_form_id = int(edit_form_id)
            prodchart_item2 = ProdchartItem.query.filter_by(id =edit_form_id).first()
            prodchart_item2.qty_allot = edit_form_quant
            db.session.commit()
            mapping = WSJobsProdChartItemMapping.query.filter_by(database=database, prodchartitem = prodchart_item2).first()
            mapping.workstationjob.qty_allot = edit_form_quant
            db.session.commit()
            return {"message": "quantity edited successfully"}, 200
        return {"message":"missing proper input"}, 401
    
class deleteid(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        delete_id = data.get("delete_id")
        if delete_id:
            delete_id=int(delete_id)
            prodchart_item3 = ProdchartItem.query.filter_by(id=delete_id).first()
            mapping = WSJobsProdChartItemMapping.query.filter_by(prodchartitem = prodchart_item3).first()
            ws_job = mapping.workstationjob
            workstation = ws_job.workstation
            date3 = ws_job.date_allot
            if checkChildJobs(database.id, workstation.id, ws_job.item.id, date3):
                return {"message": f"Item Present in Child WS!! Failed to Delete {ws_job.item.name} in {workstation.name}"}, 401
            db.session.delete(prodchart_item3)
            db.session.delete(ws_job)
            db.session.delete(mapping)
            updateMaterialIssue(workstation, date3)
            return {"message":"deleted successfully"}, 200
        return {"message":"missing proper input"}, 401

class productionsummary_api(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        k = int(req_json.get('k', 10))  # Default value is 10
        finished_flag =req_json.get('is_finished',"NO")
        semi_finished_flag = req_json.get('is_semifinished',"NO")
        materials_flag = req_json.get('is_materials',"NO")
        item_filter = req_json.get('item_filter', "NO")
        order_filter = req_json.get('order_filter', "NO")
        order_id = req_json.get('order_id', None)
        print(k ,finished_flag, semi_finished_flag)
        if item_filter == "yes":
            filters = req_json["filters"]
            print(filters)
            try:
                items_dict = searchitemouter(-1, None, None,filters,current_user["data"])
                items_df = pd.DataFrame(items_dict)
            except:
                return "Connection Error" 
        inventory_stock_data = db.session\
            .query(Inventory.item_id, db.func.sum(Inventory.qty).label("total_quantity"))\
            .group_by(Inventory.item_id).filter(Inventory.data_id == session["data"], Inventory.status=="ACTIVE").all()
        wip_inventory_stock_data = db.session\
            .query(Inventory.item_id, db.func.sum(Inventory.qty).label("total_quantity"))\
            .group_by(Inventory.item_id).filter(Inventory.data_id == session["data"], Inventory.status=="WIP").all()
        total_allot = db.session\
            .query(ProdchartItem.item_id, db.func.sum(ProdchartItem.qty_allot).label("total_quantity"))\
            .join(Prodchart, ProdchartItem.chart_id == Prodchart.id)\
            .filter(Prodchart.date>date.today(), ProdchartItem.data_id==session["data"])\
            .group_by(ProdchartItem.item_id).all()
        progress = db.session\
            .query(ProdchartItem.item_id, db.func.sum(ProdchartItem.qty_allot).label("total_quantity"))\
            .join(Prodchart, ProdchartItem.chart_id == Prodchart.id)\
            .filter(Prodchart.date==date.today(), ProdchartItem.data_id==session["data"])\
            .group_by(ProdchartItem.item_id).all()

        items = db.session.query(
            Item.id,Item.name,Item.raw_flag,Item.unit,
            ).filter(Item.data_id == session["data"]).all()
        bom_items_df = pd.DataFrame(
            db.session.query(
                BOM.id,BOM.parent_item_id,BOM.child_item_id,BOM.child_item_qty,BOM.child_item_unit,BOM.margin,
                ).filter(BOM.data_id == session["data"]).all(), columns= ["bom_id", "parent_item_id", "child_item_id", "child_item_qty", 
            "child_item_unit", "margin"])
        items_df_2 = pd.DataFrame(items, columns=["item_id", "name", "raw_flag", "unit"])

        # Convert inventory_stock_data to DataFrame
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "total_quantity2"])
        inventory_stock_dict = inventory_stock_df.set_index('item_id').to_dict(orient= 'index')
        total_allot_df = pd.DataFrame(total_allot, columns=["item_id", "total_quantity3"])

        progress_df = pd.DataFrame(progress, columns=["item_id", "total_quantity4"])
        
        wip_inventory_stock_df = pd.DataFrame(wip_inventory_stock_data, columns=["item_id", "total_quantity6"])

        if item_filter == "ROUTING":
            items_df = pd.DataFrame(columns=['item_id', 'raw_flag'])
            item_id = req_json.get("item_id", None)
            if item_id:
                item= Item.query.filter_by(database=database, id = item_id).first()
                search_df = pd.DataFrame({"item_id":[item.id], "raw_flag":[item.raw_flag]})
                while len(search_df["item_id"]):
                    print("search_df: \n", search_df)
                    items_df = pd.concat([items_df, search_df], ignore_index=True)
                    search_df = search_df[search_df["raw_flag"] == "NO"]
                    search_df_merged = pd.merge(search_df, bom_items_df, left_on="item_id", right_on="parent_item_id", how="inner")
                    search_df_merged = search_df_merged[["child_item_id"]].rename(columns={"child_item_id":"item_id_2"})
                    search_df = pd.merge(search_df_merged, items_df_2, left_on="item_id_2", right_on="item_id", how="inner")[["item_id", "raw_flag"]]
            items_df = pd.merge(items_df, items_df_2, on="item_id", how="inner")
            items_df = items_df.rename(columns={"item_id": "id"})    
            item_boms_df = pd.DataFrame(
                db.session.query(
                    ItemBOM.item_id,ItemBOM.bom_name
                    ).filter(ItemBOM.data_id == session["data"], ItemBOM.item_id.in_(items_df["id"])).all(),
                columns=["item_id", "bom_name"]
                )
            items_df = pd.merge(items_df, item_boms_df, left_on="id", right_on="item_id", how="left")
            items_df["bom_name"] = items_df["bom_name"].fillna(items_df["name"])
            print("ROUTE ITEMS:", items_df)
        ## Querying for Summary   
        to_allot_dict={}
        SUMMARY=[]

        ## Retriving Database Objects
        if order_filter == "yes" and order_id:
            active_orders_aggregate_data = db.session\
                .query(OrderItem.item_id, db.func.sum(OrderItem.order_qty).label("total_quantity"))\
                .join(Order, OrderItem.order_id == Order.id)\
                .filter(OrderItem.data_id==session["data"], Order.id == order_id)\
                .group_by(OrderItem.item_id).all()
            delivery_batch_query = db.session.query(
                    DeliveryBatch.id,
                ).join(
                    Order, DeliveryBatch.order_id == Order.id 
                ).filter(
                    Order.id == order_id, DeliveryBatch.data_id==session["data"],
                    DeliveryBatch.status == 'DISPATCHED'
                ).all()
        elif item_filter=="yes":
            active_orders_aggregate_data = db.session\
                .query(OrderItem.item_id, db.func.sum(OrderItem.order_qty).label("total_quantity"))\
                .join(Order, OrderItem.order_id == Order.id)\
                .filter(Order.status == "Active", OrderItem.data_id==session["data"], Order.order_type==0)\
                .group_by(OrderItem.item_id).all()
            delivery_batch_query = db.session.query(
                    DeliveryBatch.id,
                ).join(
                    Order, DeliveryBatch.order_id == Order.id 
                ).filter(
                    Order.status == "Active", DeliveryBatch.data_id==session["data"], Order.order_type==0,
                    DeliveryBatch.status == 'DISPATCHED'
                ).all()
        else:
            active_orders_aggregate_data = db.session\
                .query(OrderItem.item_id, db.func.sum(OrderItem.order_qty).label("total_quantity"))\
                .join(Order, OrderItem.order_id == Order.id)\
                .filter(Order.status == "Active", OrderItem.data_id==session["data"], Order.order_type==0)\
                .group_by(OrderItem.item_id).all()
            delivery_batch_query = db.session.query(
                    DeliveryBatch.id,
                ).join(
                    Order, DeliveryBatch.order_id == Order.id 
                ).filter(
                    Order.status == "Active", DeliveryBatch.data_id==session["data"], Order.order_type==0,
                    DeliveryBatch.status == 'DISPATCHED'
                ).all()
        active_orders_df = pd.DataFrame(active_orders_aggregate_data, columns=["item_id", "total_quantity1"])

        active_delivery_batches_df = pd.DataFrame(delivery_batch_query,
            columns = ["delivery_batch_id"]
            )
        order_item_dispatch_df = pd.DataFrame(
            db.session.query(
                    OrderItem.item_id,
                    db.func.sum(OrderItemDispatch.dispatch_qty).label("total_dispatch_quantity")
                ).join(
                    OrderItem, OrderItemDispatch.order_item_id == OrderItem.id
                ).filter(
                    OrderItemDispatch.data_id == session['data'], 
                    OrderItemDispatch.delivery_batch_id.in_(active_delivery_batches_df["delivery_batch_id"].tolist()),
                ).group_by(
                    OrderItem.item_id
                ).all(),
            columns=['item_id','total_dispatch_quantity']
            )
        active_orders_df = pd.merge(order_item_dispatch_df, active_orders_df, on="item_id", how='right')
        # print(active_orders_df)
        active_orders_df = active_orders_df.fillna(0)
        active_orders_df["total_quantity1"] = active_orders_df["total_quantity1"] - active_orders_df["total_dispatch_quantity"] 
        active_orders_df = active_orders_df[["item_id", "total_quantity1"]]
        active_orders_df = active_orders_df[active_orders_df["total_quantity1"] > 0]
        ## Calculating for Semi Finished
        if semi_finished_flag == "YES" or materials_flag == 'YES':
            result_demand = demand_calculation_function(active_orders_df, inventory_stock_df, items_df_2, bom_items_df, materials_flag, semi_finished_flag)
            inventory_demand = demand_calculation_function_inventory(result_demand["item_id"].tolist()+active_orders_df["item_id"].tolist(), inventory_stock_df, items_df_2, bom_items_df, materials_flag, semi_finished_flag )
            print("result_demand:\n", result_demand)
            print("inventory_demand:\n", inventory_demand)
            semi_finished_demand = pd.merge(result_demand.rename(columns={"demand_qty":"order_demand"}), inventory_demand.rename(columns={"demand_qty":"inventory_demand"}), on="item_id", how='left')
            semi_finished_demand["demand_qty"] = semi_finished_demand["order_demand"]-semi_finished_demand["inventory_demand"]
            semi_finished_demand = semi_finished_demand[semi_finished_demand['demand_qty']>0]
            semi_finished_dataframe = semi_finished_demand[["item_id", "demand_qty"]].rename(columns={'demand_qty':'total_quantity1'})
            if finished_flag == "NO":
                active_orders_df = semi_finished_dataframe
            if finished_flag == "YES":
                active_orders_df = pd.concat([active_orders_df, semi_finished_dataframe], axis=0).groupby('item_id')['total_quantity1'].sum().reset_index()
                
            # print(active_orders_df)

        if item_filter == "yes":
            if len(filters["filters_array"]) == 0:
                print("check54")
                active_orders_df = active_orders_df
            elif len(items_df.index) == 0:
                print("check55")
                active_orders_df = active_orders_df[0:0]
            else:
                print("check56")
                active_orders_df = active_orders_df[active_orders_df['item_id'].isin(items_df['id'])]
            # print(active_orders_df)
        if item_filter == "ROUTING":
            if len(items_df.index) == 0:
                print("check55")
                active_orders_df = active_orders_df[0:0]
            else:
                print("check56")
                active_orders_df = active_orders_df[active_orders_df['item_id'].isin(items_df['id'])]
        merged_df = pd.merge(active_orders_df, inventory_stock_df, on="item_id", how="left")
        merged_df = pd.merge(merged_df, total_allot_df, on="item_id", how="left")
        merged_df = pd.merge(merged_df, progress_df, on="item_id", how="left")
        merged_df = pd.merge(merged_df, wip_inventory_stock_df, on="item_id", how="left")

        # Fill NaN values with zero
        merged_df = merged_df.fillna(0)

        # Relabel the columns
        merged_df.columns = ["Item ID", "Order_Quantity", "Stock_Quantity",
                            "Alloted_Quantity", "Progress_Quantity", "WIP_Quantity"]
        

        psbl_dictionary = max_psbl_amount(database.id, merged_df["Item ID"])
        if item_filter == 'ROUTING':
            merged_df = pd.merge_ordered(items_df,merged_df,  how="inner", right_on="Item ID", left_on='id').rename(columns={"bom_name":"Item Name", "unit":"Item Unit"})
            print("merged_df  sdcd:", merged_df)
        else:
            merged_df = pd.merge(merged_df, items_df_2, how="left", left_on="Item ID", right_on='item_id').rename(columns={"name":"Item Name", "unit":"Item Unit"})
        # merged_df["Item Name"] = merged_df["Item ID"].map(item_mapping)
        # merged_df["Item Unit"] = merged_df["Item ID"].map(unit_mapping)
        merged_df["Max Possible"] = merged_df["Item ID"].map(psbl_dictionary)
        merged_df.fillna(0, inplace=True)
        # merged_df["To Allot"] = merged_df["Order_Quantity"] - merged_df["Stock_Quantity"]-merged_df["Alloted_Quantity"]-merged_df["Progress_Quantity"]
        merged_df["To Allot"] = merged_df["Order_Quantity"] - merged_df["Stock_Quantity"]-merged_df["Alloted_Quantity"]

        merged_df = merged_df.round(2)
        merged_dict = merged_df.to_dict(orient="records")

        return jsonify(merged_dict)
    
    
class maketostock_api(Resource):
    @jwt_required()
    @requires_role(["PRODUCTION"],0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        k = int(req_json.get('k', 10))  # Default value is 10
        finished_flag =req_json.get('is_finished',"NO")
        semi_finished_flag = req_json.get('is_semifinished',"NO")
        materials_flag = req_json.get('is_materials',"NO")
        item_filter = req_json.get('item_filter', "NO")
        order_filter = req_json.get('order_filter', "NO")
        order_id = req_json.get('order_id', None)
        print(k ,finished_flag, semi_finished_flag)
        if item_filter == "yes":
            filters = req_json["filters"]
            print(filters)
            try:
                items_dict = searchitemouter(-1, None, None,filters,current_user["data"])
                items_df = pd.DataFrame(items_dict)
            except:
                return "Connection Error" 
        to_allot_dict={}
        SUMMARY=[]
        active_orders_df = mt_stock(session["data"])
        if item_filter == "yes":
            if len(filters["filters_array"]) == 0:
                print("check54")
                active_orders_df = active_orders_df
            elif len(items_df.index) == 0:
                print("check55")
                active_orders_df = active_orders_df[0:0]
            else:
                print("check56")
                active_orders_df = active_orders_df[active_orders_df['item_id'].isin(items_df['id'])]
        merged_df = active_orders_df
        merged_df = merged_df.fillna(0)
        psbl_dictionary = max_psbl_amount(database.id, merged_df["item_id"])
        merged_df["Max Possible"] = merged_df["item_id"].map(psbl_dictionary)
        merged_df.fillna(0, inplace=True)
        if finished_flag == "YES" and materials_flag=="NO":
            merged_df = merged_df[merged_df["raw_flag"] == "NO"]
        elif materials_flag == "YES" and finished_flag=="NO":
            merged_df = merged_df[merged_df["raw_flag"] == "YES"]

        total_allot = db.session\
            .query(ProdchartItem.item_id, db.func.sum(ProdchartItem.qty_allot).label("total_quantity"))\
            .join(Prodchart, ProdchartItem.chart_id == Prodchart.id)\
            .filter(Prodchart.date>date.today(), ProdchartItem.data_id==session["data"])\
            .group_by(ProdchartItem.item_id).all()
        progress = db.session\
            .query(ProdchartItem.item_id, db.func.sum(ProdchartItem.qty_allot).label("total_quantity"))\
            .join(Prodchart, ProdchartItem.chart_id == Prodchart.id)\
            .filter(Prodchart.date==date.today(), ProdchartItem.data_id==session["data"])\
            .group_by(ProdchartItem.item_id).all()
        # Convert total_allot to DataFrame
        total_allot_df = pd.DataFrame(total_allot, columns=["item_id", "total_quantity3"])
        # Convert progress to DataFrame
        progress_df = pd.DataFrame(progress, columns=["item_id", "total_quantity4"])
        # Convert the merged DataFrame to a dictionary
        merged_df = pd.merge(merged_df, total_allot_df, on="item_id", how="left")
        merged_df = pd.merge(merged_df, progress_df, on="item_id", how="left")

        merged_df = merged_df.round(2)
        merged_df = merged_df[['code','demand','item_id', 'max_level', 'min_level','name','stock','unit','wip_stock','Max Possible', 'total_quantity3','total_quantity4']]
        merged_df.rename(columns = {'item_id':"Item ID",'name':'Item Name','unit':'Item Unit', 'stock':'Stock_Quantity', 'total_quantity3':'Alloted_Quantity','total_quantity4':'Progress_Quantity'}, inplace = True) 
        
        merged_df.fillna(0, inplace=True)
        merged_df['demand'] = merged_df['demand']-merged_df['Alloted_Quantity']-merged_df['Progress_Quantity']
        merged_dict = merged_df.to_dict(orient="records")
        print(merged_df)
        return jsonify(merged_dict)
        