from flask import Flask,current_app, render_template,current_app, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import jsonify
from models import db, Data, Category, Inventory, Item, User, BGProcess, WorkstationMapping, WSMaterialIssue, BOM, WorkstationJob, Workstation ,ItemInventory
from models import Labor,User, Item, BOM, Customer, Category, Prodchart, Joballot, Order, Data, ProdchartItem, Inventory, OrderItem
from models import Workstation, WorkstationMapping, WorkstationJob, WorkstationResource, WSMaterialIssue, WSJobsProdChartItemMapping, WorkstationPreference, ItemInventory
import random
import string
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
import datetime
import requests
import pandas as pd
import os
import pdfkit
import json
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

def get_total_jobs(workstation, date):
    database=workstation.database
    ws_mapping = WorkstationMapping.query.filter_by(parent_ws=workstation, database=database).all()
    result={}
    result[workstation.id]={}
    result[workstation.id]["workstation"] = workstation
    result[workstation.id]["totals"]={}
    result[workstation.id]["recv_totals"]={}
    result[workstation.id]["wip_totals"]={}
    result[workstation.id]["reject_totals"]={}

    result[workstation.id]["material_issues"]={}
    result[workstation.id]["material_estimates"]={}
    result[workstation.id]["material_estimate_totals"]={}
    result[workstation.id]["material_estimate_totals_from_recv"]={}
    result[workstation.id]["material_issue_totals"]={}
    result[workstation.id]["material_return_totals"]={}
    result[workstation.id]["material_reject_totals"]={}

    result[workstation.id]["job_work_totals"]=0
    result[workstation.id]["capacity_totals"]=0

    result[workstation.id]["ws_date"]=date

    jobs = WorkstationJob.query.filter_by(database=database, workstation=workstation, date_allot=date).all()
    ws_issues = WSMaterialIssue.query.filter_by(database=database, workstation=workstation, date_issue=date).all()
    ws_resources = WorkstationResource.query.filter_by(database=database, workstation=workstation, date_allot= date).all()
    result[workstation.id]["jobs"] = jobs
    result[workstation.id]["material_issues"] = ws_issues
    result[workstation.id]["resources"] = ws_resources
    result[workstation.id]["child_resources"]=ws_resources
    if not workstation.category_config:
        workstation.category_config='{}'
    result[workstation.id]["category_config"] = json.loads(workstation.category_config)

    all_jobs = []+ result[workstation.id]["jobs"]
    leaf_jobs=[]

    result[workstation.id]["childs"]={}
    for mapping in ws_mapping:
        child_ws = mapping.child_ws
        child_leaf_jobs, child_result, child_all_jobs = get_total_jobs(child_ws, date)
        result[workstation.id]["childs"][child_ws.id] = child_result[child_ws.id]
        leaf_jobs += child_leaf_jobs
        all_jobs+= child_all_jobs

    ## Adding for the jobs in parents
    for job in result[workstation.id]["jobs"]:
        print(job, job.id, job.qty_allot, job.item.rate)
        ## Jobs Aggregation
        if job.item.id not in result[workstation.id]["totals"].keys():
            result[workstation.id]["totals"][job.item.id]=0
            result[workstation.id]["recv_totals"][job.item.id]=0
            result[workstation.id]["wip_totals"][job.item.id]=0
            result[workstation.id]["reject_totals"][job.item.id]=0
        result[workstation.id]["totals"][job.item.id] += job.qty_allot
        result[workstation.id]["job_work_totals"]+= job.qty_allot*job.item.rate
        result[workstation.id]["wip_totals"][job.item.id] += job.qty_wip
        result[workstation.id]["reject_totals"][job.item.id] += job.qty_reject
        if not job.qty_recv:
            print(job.item.name, job.workstation.name)
        else:
            result[workstation.id]["recv_totals"][job.item.id] += job.qty_recv

        ## Material Aggregation    
        bom = BOM.query.filter_by(database=database, parent_item= job.item).all()
        for bom_item in bom:
            if bom_item.child_item.id not in result[workstation.id]["material_estimate_totals"].keys():
                result[workstation.id]["material_estimate_totals"][bom_item.child_item.id] = 0 
                result[workstation.id]["material_estimates"][bom_item.child_item.id] = 0
                result[workstation.id]["material_estimate_totals_from_recv"][bom_item.child_item.id] = 0 

            result[workstation.id]["material_estimate_totals"][bom_item.child_item.id] += (job.qty_allot)*(1+(0.01*bom_item.margin))*bom_item.child_item_qty
            result[workstation.id]["material_estimates"][bom_item.child_item.id] += (job.qty_allot)*(1+(0.01*bom_item.margin))*bom_item.child_item_qty
            # result[workstation.id]["material_estimate_totals_from_recv"][bom_item.child_item.id]+= (job.qty_recv)*(1+(0.01*bom_item.margin))*bom_item.child_item_qty
            result[workstation.id]["material_estimate_totals_from_recv"][bom_item.child_item.id]+= (job.qty_recv)*bom_item.child_item_qty
    wip_inventory_stock_data = db.session\
        .query(
            Inventory.item_id,
            db.func.sum(Inventory.qty).label("total_quantity")
        )\
        .join(Item, Inventory.item_id == Item.id)\
        .group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
        .filter(Inventory.data_id == database.id, Inventory.status == "WIP")\
        .having(db.func.sum(Inventory.qty) > 0)\
        .all()
    wip_inventory_stock_df = pd.DataFrame(wip_inventory_stock_data, columns=["item_id","total_stock" ])

    for issue_item in result[workstation.id]["material_issues"]:
        if issue_item.item.id not in result[workstation.id]["material_issue_totals"].keys():
            result[workstation.id]["material_issue_totals"][issue_item.item.id] = 0
            result[workstation.id]["material_return_totals"][issue_item.item.id] = 0
            result[workstation.id]["material_reject_totals"][issue_item.item.id] = 0
        result[workstation.id]["material_issue_totals"][issue_item.item.id] += issue_item.issue_qty
        result[workstation.id]["material_return_totals"][issue_item.item.id] += issue_item.return_qty
        result[workstation.id]["material_reject_totals"][issue_item.item.id] += issue_item.reject_qty
        ## handling WIP case
        if issue_item.wip_flag == "YES":
            # try:
            #     wip_stock = wip_inventory_stock_df.loc[wip_inventory_stock_df["item_id"] == issue_item.item.id]["total_stock"][0]
            # except:
            #     wip_stock = 0
            estimate = result[workstation.id]["totals"][issue_item.item.id] if issue_item.item.id in result[workstation.id]["totals"].keys() else 0
            if issue_item.item.id not in result[workstation.id]["material_estimate_totals"].keys():
                result[workstation.id]["material_estimate_totals"][issue_item.item.id] = estimate
                result[workstation.id]["material_estimates"][issue_item.item.id] = estimate
                result[workstation.id]["material_estimate_totals_from_recv"][issue_item.item.id] = estimate
    for ws_resource in result[workstation.id]["resources"]:
        result[workstation.id]["capacity_totals"]+= ws_resource.labor.salary * ws_resource.time_allot

    for child_key in result[workstation.id]["childs"].keys():
        for item_id in result[workstation.id]["childs"][child_key]["totals"]:
            if item_id not in result[workstation.id]["totals"]:
                result[workstation.id]["totals"][item_id]=0
                result[workstation.id]["wip_totals"][item_id]=0
                result[workstation.id]["recv_totals"][item_id]=0
                result[workstation.id]["reject_totals"][item_id]=0

            result[workstation.id]["totals"][item_id]+= result[workstation.id]["childs"][child_key]["totals"][item_id]
            result[workstation.id]["recv_totals"][item_id]+= result[workstation.id]["childs"][child_key]["recv_totals"][item_id]
            result[workstation.id]["wip_totals"][item_id]+= result[workstation.id]["childs"][child_key]["wip_totals"][item_id]
            result[workstation.id]["reject_totals"][item_id]+= result[workstation.id]["childs"][child_key]["reject_totals"][item_id]

        result[workstation.id]["job_work_totals"]+= result[workstation.id]["childs"][child_key]["job_work_totals"]
        result[workstation.id]["capacity_totals"]+= result[workstation.id]["childs"][child_key]["capacity_totals"]
        result[workstation.id]["child_resources"]+= result[workstation.id]["childs"][child_key]["child_resources"]
        
        for item_id in result[workstation.id]["childs"][child_key]["material_estimate_totals"].keys():
            for cat in ["material_estimate_totals", "material_estimate_totals_from_recv"]:
                if item_id not in result[workstation.id][cat].keys():
                    result[workstation.id][cat][item_id]=0
            result[workstation.id]["material_estimate_totals"][item_id] += result[workstation.id]["childs"][child_key]["material_estimate_totals"][item_id]
            result[workstation.id]["material_estimate_totals_from_recv"][item_id] += result[workstation.id]["childs"][child_key]["material_estimate_totals_from_recv"][item_id]
            # print(item_id, result[workstation.id]["material_issue_totals"][item_id])
        
        for item_id in result[workstation.id]["childs"][child_key]["material_issue_totals"].keys():
            for cat in ["material_issue_totals"]:
                if item_id not in result[workstation.id][cat].keys():
                    result[workstation.id][cat][item_id]=0
            result[workstation.id]["material_issue_totals"][item_id] += result[workstation.id]["childs"][child_key]["material_issue_totals"][item_id]
        
        for item_id in result[workstation.id]["childs"][child_key]["material_return_totals"].keys():
            for cat in [ "material_return_totals"]:
                if item_id not in result[workstation.id][cat].keys():
                    result[workstation.id][cat][item_id]=0
            result[workstation.id]["material_return_totals"][item_id] += result[workstation.id]["childs"][child_key]["material_return_totals"][item_id]
        
        for item_id in result[workstation.id]["childs"][child_key]["material_reject_totals"].keys():
            for cat in ["material_reject_totals"]:
                if item_id not in result[workstation.id][cat].keys():
                    result[workstation.id][cat][item_id]=0
            result[workstation.id]["material_reject_totals"][item_id] += result[workstation.id]["childs"][child_key]["material_reject_totals"][item_id]
    return leaf_jobs, result, all_jobs

def updateMaterialIssue(workstation, date, data):
    database = Data.query.filter_by(id=data).first()
    # ws_parent = WorkstationMapping.query.filter_by(database=database, ws_child=)

    ws_jobs = WorkstationJob.query.filter_by(database=database, workstation=workstation, date_allot = date).all()

    wip_inventory_stock_data = db.session.query(Inventory.item_id,Item.code,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity"))\
        .join(Item, Inventory.item_id == Item.id)\
        .group_by(Inventory.item_id, Item.code, Item.name, Item.unit)\
        .filter(Inventory.data_id == data, Inventory.status == "WIP")\
        .having(db.func.sum(Inventory.qty) > 0)\
        .all()
    wip_inventory_stock_df = pd.DataFrame(wip_inventory_stock_data, columns=["item_id","item_code", "Item Name", "Item Unit","total_stock" ])
    materials={}
    for job in ws_jobs:
        boms = BOM.query.filter_by(database=database, parent_item=job.item).all()
        for bom_item in boms:
            child_id = bom_item.child_item.id
            if child_id not in materials.keys():
                materials[child_id]={}
                materials[child_id]["item"] = bom_item.child_item
                materials[child_id]["wip"] = False
        wip_stock = wip_inventory_stock_df[wip_inventory_stock_df["item_id"] == job.item.id]
        if not wip_stock.empty:
            item = Item.query.filter_by(database=database, id=job.item.id).first()
            materials[job.item.id]={}
            materials[job.item.id]["item"] = item
            materials[job.item.id]["wip"] = True
            # materials[job.item.id]["wip_stock"] = wip_stock["total_stock"]
            # materials[child_id] += (job.qty_allot)*(1+(0.01*bom_item.margin))*bom_item.child_item_qty
    for item_id in materials.keys():
        item = materials[item_id]["item"]
        issue_check = WSMaterialIssue.query.filter_by(database=database, workstation=workstation, item=item, date_issue=date).first()
        if not issue_check:
            if materials[item_id]["wip"]:
                issue_inventory = Inventory(item=item,regdate=date, qty = 0, item_unit = item.unit, database=database, note=f"WIP_MaterialIssue_{workstation.name}_{date}", status = "WIP")
                db.session.add(issue_inventory)
                db.session.commit()
                ws_issue = WSMaterialIssue(database=database, workstation=workstation, item = item, item_unit=item.unit, inventory=issue_inventory, date_issue=date, wip_flag="YES")
            else:
                issue_inventory = Inventory(item=item,regdate=date, qty = 0, item_unit = item.unit, database=database, note=f"MaterialIssue_{workstation.name}_{date}")
                db.session.add(issue_inventory)
                db.session.commit()
                ws_issue = WSMaterialIssue(database=database, workstation=workstation, item = item, item_unit=item.unit, inventory=issue_inventory, date_issue=date)
            db.session.add(ws_issue)
            db.session.commit()
    ws_issues = WSMaterialIssue.query.filter_by(database=database, workstation=workstation, date_issue = date).all()
    for issue_item in ws_issues:
        if issue_item.item.id not in materials.keys():
            if issue_item.inventory:
                db.session.delete(issue_item.inventory)
            db.session.delete(issue_item)

def autoMaterialIssue(ws_id, date, data_id):
    ## Nested Auto Material Issuer for a Workstation and all its childs
    database = Data.query.filter_by(id =data_id).first()

    workstation = Workstation.query.filter_by(database=database, id = ws_id).first()
    updateMaterialIssue(workstation, date)
    a, ws_dict, c = get_total_jobs(workstation, date)
    for item_id in ws_dict[workstation.id]["material_estimate_totals_from_recv"].keys():
        item = Item.query.filter_by(database=database, id = item_id).first()
        if not item.iteminventory:
            iteminventory = ItemInventory(database=database, item=item)
            db.session.add(iteminventory)
            db.session.commit()
        item_inventory = item.iteminventory
        if item_inventory.consumption_mode == "AUTO":
            print("database",database.id,"workstation",workstation.name, "date_issue",date, "item",item.name)
            ws_issue = WSMaterialIssue.query.filter_by(database=database,workstation=workstation, date_issue=date, item=item).first()
            ws_issue.inventory.qty = -1*float(ws_dict[workstation.id]["material_estimate_totals_from_recv"][item_id])
            db.session.commit()
    for child_ws_id in ws_dict[workstation.id]["childs"].keys():
        autoMaterialIssue(child_ws_id, date, data_id)

def checkChildJobs(data_id, workstation_id, item_id, date_allot):
    database = Data.query.filter_by(id = data_id).first()
    workstation = Workstation.query.filter_by(database = database, id = workstation_id).first()
    item = Item.query.filter_by(database=database, id = item_id).first()
    child_ws_mappings = workstation.workstation_parents
    for child_ws_mapping in child_ws_mappings:
        parent_ws = child_ws_mapping.child_ws
        if parent_ws:
            flag = True
            ws_jobs = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot=date_allot).all()
            for job in ws_jobs:
                if job.item.id == item.id:
                    return True
    return False

def get_job_totals(data_id, item_id, date_allot, ws_id):
    database = Data.query.filter_by(id = data_id).first()
    workstation = Workstation.query.filter_by(database = database, id = ws_id).first()
    item = Item.query.filter_by(database=database, id = item_id).first() 
    ws_job = WorkstationJob.query.filter_by(database=database, workstation_id=workstation.id, date_allot=date_allot, item_id=item.id).first()
    # print("WSJOBBBB", ws_job, database.id, workstation.id, item.id, date_allot)
    ws_child_maps = workstation.workstation_parents
    if ws_job:
        qty_allot_totals = ws_job.qty_allot
    else:
        # print(date_allot, item.name, item.id)
        # print("noJobWS", workstation.name, workstation.id)
        return {"qty_allot": 0}
    if not len(ws_child_maps):
        return {"qty_allot": ws_job.qty_allot}
    for child_map in ws_child_maps:
        child_ws = child_map.child_ws
        if child_ws:
            child_res = get_job_totals(data_id, item_id, date_allot, child_ws.id)
            # print("child_res", child_ws.name, child_res)
            qty_allot_totals+=child_res["qty_allot"]
    return {"qty_allot":qty_allot_totals}

def checkParentJobs(data_id, workstation_id, item_id, date_allot):
    database = Data.query.filter_by(id = data_id).first()
    workstation = Workstation.query.filter_by(database = database, id = workstation_id).first()
    item = Item.query.filter_by(database=database, id = item_id).first()
    parent_ws_mappings = workstation.workstation_childs
    for parent_ws_mapping in parent_ws_mappings:
        parent_ws = parent_ws_mapping.parent_ws
        if parent_ws:
            flag = True
            ws_jobs = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot=date_allot).all()
            for job in ws_jobs:
                if job.item.id == item.id:
                    return False
    return True

def updateParentJobs(data_id, workstation_id, item_id, date_allot):
    database = Data.query.filter_by(id = data_id).first()
    workstation = Workstation.query.filter_by(database = database, id = workstation_id).first()
    item = Item.query.filter_by(database=database, id = item_id).first()
    parent_ws_mappings = workstation.workstation_childs
    if len(parent_ws_mappings):
        parent_ws = parent_ws_mappings[0].parent_ws
        if parent_ws:
            if checkParentJobs(data_id, workstation_id, item_id, date_allot):
                ws_job = WorkstationJob(database= database, workstation=parent_ws, date_allot=date_allot, item=item, qty_allot=0)
                db.session.add(ws_job)
                db.session.commit()
                updateMaterialIssue(workstation, date_allot)
            updateParentJobs(database.id, parent_ws.id, item.id, date_allot)
    else:

        ws_totals = get_job_totals(data_id, item_id, date_allot,workstation_id )
        print("ws_totals",ws_totals)
        prod_charts = Prodchart.query.filter_by(database=database, date=date_allot).all()
        if not len(prod_charts):
            prodchart = Prodchart(date=date_allot, note="autoChartCreation", database=database)
            db.session.add(prodchart)
            db.session.commit()
            prod_charts = Prodchart.query.filter_by(database=database, date=date_allot).all()
        prodchartitems=[]
        for prod_chart in prod_charts:
            prodchartitems += ProdchartItem.query.filter_by(prodchart=prod_chart, database=database, item=item).all()
        if not len(prodchartitems):
            pc_item = ProdchartItem(prodchart = prod_charts[0], item=item, database=database, qty_allot=ws_totals["qty_allot"], item_unit=item.unit ,item_rate=item.rate)
            db.session.add(pc_item)
            db.session.commit()
            ws_job = WorkstationJob.query.filter_by(database=database, workstation=workstation, date_allot=date_allot, item=item).first()
            wsjobprodchartitemmapping = WSJobsProdChartItemMapping(database=database, workstationjob = ws_job, prodchartitem = pc_item)
            db.session.add(wsjobprodchartitemmapping)
            db.session.commit()
        pc_qty_sum=0
        for pcitem in prodchartitems:
            pc_qty_sum += pcitem.qty_allot
        if len(prodchartitems):
            print(pc_qty_sum)
            prodchartitems[0].qty_allot += (ws_totals["qty_allot"] - pc_qty_sum)
            db.session.commit()
           
def DFSloadWorkstationPreferences(database, date, preference_dict):
    for ws_key in preference_dict.keys():
        child_ws = Workstation.query.filter_by(id=ws_key, database=database).first()
        for resource in preference_dict[ws_key]["resources"]:
            ws_resource = WorkstationResource(workstation = child_ws,date_allot = date, resource_id = resource["resource_id"] ,
                time_allot = resource["time_allot"], database=database, contract_mode = resource['contract_mode'])
            db.session.add(ws_resource)
            db.session.commit()
            # print(f"/n/n{ws_job.labor.name}")
        DFSloadWorkstationPreferences(database, date, preference_dict[ws_key]["childs"])
        
def loadWorkstationPreferences(data_id, to_load_date):
    database = Data.query.filter_by(id = data_id).first()
    workstation_preference = WorkstationPreference.query.filter_by(database=database).first()
    primary_ws = Workstation.query.filter_by(name = database.name+"_primary_ws").first()
    if workstation_preference:
        preference_dict = json.loads(workstation_preference.workstation_config)
    else:
        return
    print(preference_dict)
    print(type(preference_dict))
    DFSloadWorkstationPreferences(database, to_load_date, preference_dict) 

def DFSWorkstationPreferences(database, workstation, date):
    preference_dict_now={"resources":[]}
    workstation_resources = WorkstationResource.query.filter_by(database=database, workstation = workstation, date_allot=date).all()
    for ws_resource in workstation_resources:
        preference_dict_now["resources"].append({"resource_id": ws_resource.resource_id, "time_allot":ws_resource.time_allot,
         "contract_mode":ws_resource.contract_mode})
    workstation_maps = WorkstationMapping.query.filter_by(database=database, parent_ws = workstation).all()
    preference_dict_now["childs"]={}
    for workstation_map in workstation_maps:
        ws_child = workstation_map.child_ws
        preference_dict_child = DFSWorkstationPreferences(database, ws_child, date)
        preference_dict_now["childs"][ws_child.id] = preference_dict_child
    return preference_dict_now

def UpdateWorkstationPreferences(data_id, date_allot):
    database = Data.query.filter_by(id=data_id).first()
    workstation = Workstation.query.filter_by(database=database, name = database.name+"_primary_ws").first()
    new_preference_dict = DFSWorkstationPreferences(database ,workstation, date_allot)
    preference_dict = {workstation.id:new_preference_dict}
    print(preference_dict)
    workstation_preference = WorkstationPreference.query.filter_by(database=database).first()
    if not workstation_preference:
        workstation_preference = WorkstationPreference(database=database)
        db.session.add(workstation_preference)
        db.session.commit()
    workstation_preference.workstation_config = json.dumps(preference_dict)
    db.session.commit()

#----------------------------------------------------------------

#api.add_resource(workstation, '/workstation', '/workstation/<int:workstation_id>', '/workstation/<int:workstation_id>/<string:date>')


class workstation(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"],0)
    def get(self, workstation_id=None, date=None):
        current_user = get_jwt_identity()
        database= Data.query.filter_by(id = current_user["data"]).first()
        primary_workstation = Workstation.query.filter_by(database=database, id = current_user["workstation_id"]).first()
        if workstation_id:
            workstation = Workstation.query.filter_by(database=database, id = workstation_id).first()
            if workstation.id == primary_workstation.id:
                primary_ws_flag = True
        else:
            primary_ws_flag = True
            workstation = primary_workstation
        ws_date = datetime.date.today()
        if date:
            ws_date = date
        WORKSTATION_PATH=[]
        path_flag = True
        curr_ws = workstation
        while path_flag:
            WORKSTATION_PATH.append([curr_ws.id, curr_ws.name])
            try:
                curr_ws = curr_ws.workstation_childs[0].parent_ws
            except:
                path_flag = False
        WORKSTATION_PATH.reverse()
        WORKSTATION_PATH[0][1] = "PRIMARY WORKSTATION"
        updateMaterialIssue(workstation, ws_date, current_user['data'])
        ws_config_flag = WorkstationResource.query.filter_by(database=database, date_allot=ws_date).first()
        if not ws_config_flag:
            loadWorkstationPreferences(database.id, ws_date)
        child_workstations = WorkstationMapping.query.filter_by(database=database, parent_ws = workstation).all()
        workstation_jobs = WorkstationJob.query.filter_by(database=database, workstation=workstation, date_allot=ws_date).all()
        workstation_resources = WorkstationResource.query.filter_by(database=database, workstation= workstation, date_allot=ws_date).all()
        leaf_jobs, jobs_breakup, all_jobs = get_total_jobs(workstation, ws_date)
        DATA = {}
        for child_ws_map in child_workstations:
            child_jobs = WorkstationJob.query.filter_by(database=database, workstation=child_ws_map.child_ws, date_allot=ws_date).all()
            child_resources = WorkstationResource.query.filter_by(database=database, workstation=child_ws_map.child_ws, date_allot=ws_date).all()
            DATA[child_ws_map.child_ws.id] = {"date": ws_date, "note":child_ws_map.child_ws.name, "chart_items":[]}
            DATA[child_ws_map.child_ws.id]["ws_jobs"]=child_jobs
            for child_job in child_jobs:
                DATA[child_ws_map.child_ws.id]["chart_items"].append([child_job.id, child_job.item.name, 
                    jobs_breakup[workstation.id]["childs"][child_job.workstation.id]["totals"][child_job.item.id], child_job.item.unit, 0, child_job.item.id])
            DATA[child_ws_map.child_ws.id]["chart_resources"] = child_resources
        leaf_data={}
        leaf_data["jobs"]={}
        for job in leaf_jobs:
            if job.item.id not in leaf_data["jobs"].keys():
                leaf_data["jobs"][job.item.id] = {}
                leaf_data["jobs"][job.item.id]["qty_allot"] = 0
                leaf_data["jobs"][job.item.id]["item"] = job.item
                leaf_data["jobs"][job.item.id]["qty_recv"] = 0
                leaf_data["jobs"][job.item.id]["workstations"]=[]
            leaf_data["jobs"][job.item.id]["qty_allot"] += job.qty_allot
            leaf_data["jobs"][job.item.id]["workstations"].append(job.workstation)
        leaf_data["materials"]={}
        for item_id in leaf_data["jobs"].keys():
            item = Item.query.filter_by(database=database, id = item_id).first()
            item_mappings = BOM.query.filter_by(database=database, parent_item = item).all()
            for mapping in item_mappings:
                child_id = mapping.child_item.id
                if child_id not in leaf_data["materials"].keys():
                    leaf_data["materials"][child_id] = {}
                    leaf_data["materials"][child_id]["item"] = mapping.child_item
                    leaf_data["materials"][child_id]["estimate"] = 0
                    leaf_data["materials"][child_id]["workstations"]=leaf_data["jobs"][item_id]["workstations"]
                leaf_data["materials"][child_id]["estimate"] += (mapping.child_item_qty)*(1+mapping.margin/100)*leaf_data["jobs"][item_id]["qty_allot"]
        item_categories = Category.query.filter_by(database=database).all()
        CATEGORIES=[]
        CATEGORIES_MAP={}
        for item in item_categories:
            CATEGORIES.append([item.id, item.name])
            CATEGORIES_MAP[f"{item.id}"] = item.name
        jobs_breakup[workstation.id] = createjson(workstation)
        return jsonify(child_workstations = createjson(child_workstations), workstation_jobs = createjson(workstation_jobs),
     workstation_resources= createjson(workstation_resources), workstation=createjson(workstation), data = DATA, WS_DATE=ws_date, leaf_data=leaf_data, jobs_breakup=jobs_breakup ,
     primary_ws_flag = primary_ws_flag, WORKSTATION_PATH = WORKSTATION_PATH, segment=["workstations"], categories = CATEGORIES, CATEGORIES_MAP=CATEGORIES_MAP)
    
class addworkstation(Resource):
    @jwt_required()
    @requires_role(['WORKSTATION'], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        parent_ws_id = data.get("parent_ws_id")
        name = data.get('chart_note')
        if name and parent_ws_id:
            database= Data.query.filter_by(id = current_user["data"]).first()
            parent_ws = Workstation.query.filter_by(database=database, id = parent_ws_id).first()
            new_workstation = Workstation(name = name, database=database)
            db.session.add(new_workstation)
            db.session.commit()
            ws_mapping = WorkstationMapping(parent_ws = parent_ws, child_ws = new_workstation, database=database)
            db.session.add(ws_mapping)
            db.session.commit()
            return {"Message":"Workstation Added" ,"workstation":new_workstation.id}, 200
        return {"Message":"Workstation cannot added. check input"}, 401
            
class addjobtoworkstation(Resource):
    @jwt_required()
    @requires_role(['WORKSTATION'], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        ws_id = data.get("workstation_id")
        item_id= data.get("item_id")
        qty_allot= data.get("qty_allot")
        date_allot= data.get("date_allot")
        if ws_id and item_id and qty_allot and date_allot:
            qty_allot=float(qty_allot)
            database= Data.query.filter_by(id = current_user["data"]).first()
            item = Item.query.filter_by(database=database, id = item_id).first()
            if item is None:
                return {"message": "item not found in database"}, 401
            workstation = Workstation.query.filter_by(database=database, id = ws_id).first()
            job_inventory = Inventory(item=item, item_unit = item.unit, qty = 0, note=f"Receipt_{workstation.name}_{date_allot}", database=database, regdate=date_allot)
            db.session.add(job_inventory)
            db.session.commit()
            ws_job = WorkstationJob(database=database, workstation=workstation, qty_allot = qty_allot, date_allot=date_allot, item=item, inventory=job_inventory)
            db.session.add(ws_job)
            db.session.commit()
            updateParentJobs(database.id, workstation.id, item.id, date_allot)
            parent_ws = WorkstationMapping.query.filter_by(database=database, child_ws=workstation).first().parent_ws
            parent_job = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot = date_allot, item=item).first()
            if parent_job:
                parent_job.qty_allot = max(0, parent_job.qty_allot-qty_allot)
            else:
                parent_job = WorkstationJob(database=database, item=item, date_allot=date_allot, workstation=parent_ws, qty_allot=0)
                db.session.add(parent_job)
                db.session.commit()
                updateMaterialIssue(parent_job.workstation, date_allot, current_user['data'])
            db.session.commit()
            updateMaterialIssue(workstation, date_allot, current_user['data'])
            return {"Message":"Item added successfully"}, 200
        return {"Message":"check input"}, 401

class editjobtoworkstation(Resource):
    @jwt_required()
    @requires_role(['WORKSTATION'], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        ws_job_edit_id = data.get("ws_job_edit_id")
        edit_qty_allot = data.get("qty_allot")
        if ws_job_edit_id and edit_qty_allot:
            database= Data.query.filter_by(id = current_user["data"]).first()
            edit_qty_allot = float(edit_qty_allot)
            ws_job = WorkstationJob.query.filter_by(database=database, id = ws_job_edit_id).first()
            ws_job.qty_allot += edit_qty_allot
            db.session.commit()
            parent_ws = WorkstationMapping.query.filter_by(database=database, child_ws=ws_job.workstation).first().parent_ws
            parent_job = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot = ws_job.date_allot, item=ws_job.item).first()
            if parent_job:
                parent_job.qty_allot =max(0, parent_job.qty_allot-edit_qty_allot)
                db.session.commit()
                updateParentJobs(database.id, ws_job.workstation.id, ws_job.item.id, ws_job.date_allot)
            return {'message': 'Record Edited successfully', "record_id":-1, "workstation_id": ws_job.workstation.id, "date_allot":ws_job.date_allot}, 200
        return {"Message":"check input"}, 401
    
class deletejobtoworkstation(Resource):
    @jwt_required()
    @requires_role(['WORKSTATION'], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        ws_job_delete_id = data.get("ws_job_delete_id")
        if ws_job_delete_id:
            database= Data.query.filter_by(id = current_user["data"]).first()
            ws_job = WorkstationJob.query.filter_by(database=database, id = ws_job_delete_id).first()
            ws_id, date_allot = ws_job.workstation.id, ws_job.date_allot
            if checkChildJobs(database.id, ws_job.workstation.id, ws_job.item.id, ws_job.date_allot):
                return {'message': f"Item Present in Child WS!! Failed to delete {ws_job.item.name} in {ws_job.workstation.name}", "record_id":-1, "workstation_id": ws_id, "date_allot":date_allot}, 200
            parent_ws = WorkstationMapping.query.filter_by(database=database, child_ws=ws_job.workstation).first().parent_ws
            parent_job = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot = ws_job.date_allot, item=ws_job.item).first()
            if parent_job:
                parent_job.qty_allot +=ws_job.qty_allot
                db.session.commit()
            if ws_job.wipinventory:
                db.session.delete(ws_job.wipinventory)
            db.session.delete(ws_job.inventory)
            db.session.delete(ws_job)
            updateMaterialIssue(workstation, date_allot, current_user['data'])
            return {'message': 'Record Deleted successfully', "record_id":-1, "workstation_id": ws_id, "date_allot":date_allot}, 200
        return {"Message": "Check Input"}, 401


class workstation_chart_api(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id = current_user["data"]).first()
        req_json = request.get_json()
        ws_id = req_json.get("ws_id", None)
        ws_date = req_json.get("ws_date", None)
        print(ws_id, ws_date)
        if ws_id and ws_date:
            DATA={}
            workstation = Workstation.query.filter_by(database=database, id =ws_id).first()
            if workstation:
                parent_ws = workstation.workstation_childs[0].parent_ws
                a, ws_dict_parent, c = get_total_jobs(parent_ws, ws_date)
                keys_to_keep=['totals', 'recv_totals']
                jobs_breakup = {parent_ws.id: {key: ws_dict_parent[parent_ws.id][key] for key in keys_to_keep if key in ws_dict_parent[parent_ws.id]}}

                ws_dict = ws_dict_parent[parent_ws.id]["childs"]
                child_jobs = WorkstationJob.query.filter_by(database=database, workstation=workstation, date_allot=ws_date).all()
                child_resources = WorkstationResource.query.filter_by(database=database, workstation=workstation, date_allot=ws_date).all()
                DATA[workstation.id] = {"date": ws_date, "note":workstation.name, "chart_items":[], "job_work_totals":ws_dict[workstation.id]["job_work_totals"],
                "capacity_totals":ws_dict[workstation.id]["capacity_totals"], "parent_job_items":[]}
                # DATA[workstation.id]["ws_jobs"]=child_jobs
                for child_job in child_jobs:
                    DATA[workstation.id]["chart_items"].append([child_job.id, child_job.item.name, 
                        ws_dict[workstation.id]["totals"][child_job.item.id], child_job.item.unit, 0, child_job.item.id])
                DATA[workstation.id]["chart_resources"] = []
                for child_res in child_resources:
                    DATA[workstation.id]["chart_resources"].append([child_res.id, child_res.labor.name, 
                        child_res.time_allot,child_res.contract_mode, 0, child_res.labor.id])
                parent_jobs = WorkstationJob.query.filter_by(database=database, date_allot=ws_date, workstation = parent_ws).all()
                for parent_job in parent_jobs:
                    DATA[workstation.id]["parent_job_items"].append([parent_job.id, parent_job.item.name, parent_job.qty_allot,
                        ws_dict_parent[parent_ws.id]["totals"][parent_job.item.id], parent_job.item.unit, ws_dict_parent[parent_ws.id]["recv_totals"][parent_job.item.id], parent_job.item.id])
                return jsonify(DATA)
        return {"Message":"Error!"}, 401

class workstation_chart_edits(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"],0)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        ws_id = req_json.get("workstation_id", None)
        item_id= req_json.get("item_id", None)
        qty_allot= req_json.get("qty_allot", None)
        date_allot= req_json.get("date_allot", None)
        if ws_id and item_id and qty_allot and date_allot:
            database = Data.query.filter_by(id = current_user["data"]).first()
            qty_allot=float(qty_allot)
            ## Getting required masters
            item = Item.query.filter_by(database=database, id = item_id).first()
            workstation = Workstation.query.filter_by(database=database, id = ws_id).first()
            job_inventory = Inventory(item=item, item_unit = item.unit, qty = 0, note=f"Receipt_{workstation.name}_{date_allot}", database=database, regdate=date_allot)
            db.session.add(job_inventory)
            db.session.commit()
            ## Adding Workstation Job
            ws_job = WorkstationJob(database=database, workstation=workstation, qty_allot = qty_allot, date_allot=date_allot, item=item, inventory=job_inventory)
            db.session.add(ws_job)
            db.session.commit()
            updateParentJobs(database.id, workstation.id, item.id, date_allot)
            ## Getting the parent ws_job
            parent_ws = WorkstationMapping.query.filter_by(database=database, child_ws=workstation).first().parent_ws
            parent_job = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot = date_allot, item=item).first()
            if parent_job:
                parent_job.qty_allot = max(0, parent_job.qty_allot-qty_allot)
            db.session.commit()
            updateMaterialIssue(workstation, date_allot)
            return jsonify({'message': 'Record added successfully', "record_id":ws_job.id})
        return {"Message":"error in input"}, 401
    
class set_ws_item_category(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        filter_type = data.get("filter_type")
        filters = data.get("filters[]",[])
        ws_id = request.args.get("ws_id")
        if len(filters) and filter_type and ws_id:
            workstation = Workstation.query.filter_by(database=database, id=ws_id).first()
            category_config_dict = json.loads(workstation.category_config)
            if not category_config_dict.keys():
                category_config_dict["item_categories"] = {}
            category_config_dict["item_categories"] = {"filter_type": filter_type, "filters_array": filters}
            workstation.category_config = json.dumps(category_config_dict)
            return {"message":"Successfully updated categories!"}, 200
        else:
            return {"message":"Invalid request! check input"}, 401
    
class workstationsBulkEntry(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        add_items_check = data.get("add_items_check")
        workstation_id = data.get("chart_id")
        workstation_date = data.get("chart_date")
        date_allot = workstation_date
        if add_items_check and workstation_id and workstation_date:
            res = []
            workstation = Workstation.query.filter_by(id = workstation_id, database = database).first()    
            workstation_jobs = WorkstationJob.query.filter_by(workstation = workstation, database=database, date_allot = workstation_date).all()
            id_list = data.getlist("items_ids[]")
            qty_list = data.getlist("items_qtys[]")
            qty_list = [float(qty) for qty in qty_list]
            df = pd.DataFrame({'ID': id_list, 'Qty': qty_list})
            result_df = df.groupby('ID')['Qty'].sum().reset_index()
            id_list = result_df['ID'].tolist()
            qty_list = result_df['Qty'].tolist()
            parent_ws = WorkstationMapping.query.filter_by(database=database, child_ws=workstation).first().parent_ws
            a, ws_dict_parent, c = get_total_jobs(parent_ws, workstation_date)
            ws_dict = ws_dict_parent[parent_ws.id]["childs"]
            for ws_job_item in workstation_jobs:
                if str(ws_job_item.item.id) not in id_list:
                    if checkChildJobs(database.id, workstation.id, ws_job_item.item.id, workstation_date):
                        res.append(f"Item Present in Child WS!! Failed to Delete {ws_job_item.item.name} in {workstation.name}")
                        continue
                    if ws_job_item.wipinventory:
                        db.session.delete(ws_job_item.wipinventory)
                    db.session.delete(ws_job_item.inventory)
                    db.session.delete(ws_job_item)
            for i in range(len(id_list)):
                item = Item.query.filter_by(id =id_list[i], database=database).first()
                ws_job_check = WorkstationJob.query.filter_by(database=database, workstation=workstation, item=item, date_allot = workstation_date).first()
                parent_job = WorkstationJob.query.filter_by(database=database, workstation=parent_ws, date_allot = workstation_date, item=item).first()
                if ws_job_check:
                    prev_qty = ws_job_check.qty_allot
                    diff = float(qty_list[i]) -  ws_dict[workstation.id]["totals"][ws_job_check.item.id]
                    ws_job_check.qty_allot += diff
                    db.session.commit()
                    print("Existing Item Found!!")
                    if parent_job:
                        parent_job.qty_allot = max(0, parent_job.qty_allot-diff)
                    else:
                        parent_job = WorkstationJob(database=database, item=item, date_allot=workstation_date, workstation=parent_ws, qty_allot=0)
                        db.session.add(parent_job)
                        db.session.commit()
                        updateMaterialIssue(parent_job.workstation, date_allot)
                else:
                    print("New Item Found!!")
                    job_inventory = Inventory(item=item,regdate=workstation_date, item_unit = item.unit, qty = 0, note=f"Receipt_{workstation.name}_{workstation_date}", database=database)
                    db.session.add(job_inventory)
                    db.session.commit()
                    ws_job = WorkstationJob(database=database, item=item, date_allot =workstation_date, qty_allot = float(qty_list[i]), workstation=workstation,
                        inventory = job_inventory)
                    db.session.add(ws_job)
                    db.session.commit()
                    updateParentJobs(database.id, workstation.id, item.id, date_allot)
                    if parent_job:
                        parent_job.qty_allot = max(0, parent_job.qty_allot-qty_list[i]) 
                    else:
                        parent_job = WorkstationJob(database=database, item=item, date_allot=workstation_date, workstation=parent_ws, qty_allot=0)
                        db.session.add(parent_job)
                        db.session.commit()
                        updateMaterialIssue(parent_job.workstation, date_allot)
                db.session.commit()
            updateMaterialIssue(workstation, date_allot)
            return {"Message":"Success", "flash_message":res}, 200
        return {"Message":"Check Input"}, 401


class workstationReceive(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        ws_recv_flag = data.get("ws_receive_flag")
        ws_id = data.get("ws_id")
        ws_date = data.get("ws_date")
        if ws_recv_flag and ws_id and ws_date:
            ws_job_ids = data.get("job_ids[]",[])
            ws_recv_qtys = data.get("recv_qtys[]",[])
            ws_wip_qtys = data.get("wip_qtys[]",[])
            ws_reject_qtys = data.get("reject_qtys[]",[])
            if len(ws_job_ids)*3 == len(ws_recv_qtys)+ len(ws_wip_qtys) + len(ws_reject_qtys):
                for i in range(len(ws_job_ids)):
                    ws_job = WorkstationJob.query.filter_by(database=database, id=ws_job_ids[i]).first()
                    ws_job.qty_recv = ws_recv_qtys[i]
                    ws_job.qty_wip = ws_wip_qtys[i]
                    ws_job.qty_reject = ws_reject_qtys[i]
                    if ws_job.inventory:
                        ws_job.inventory.qty = ws_recv_qtys[i]
                    else:
                        new_inventory = Inventory(database=database, item=ws_job.item, item_unit=ws_job.item.unit, qty=ws_recv_qtys[i], note=f"Receipt_{ws_job.workstation.name}_{ws_job.date_allot}", regdate=ws_job.date_allot)
                        db.session.add(new_inventory)
                        db.session.commit()
                        ws_job.inventory = new_inventory
                    if ws_job.wipinventory:
                        ws_job.wipinventory.qty= ws_wip_qtys[i]
                    else:
                        new_wip_inventory = Inventory(database=database, item=ws_job.item, item_unit=ws_job.item.unit, qty=ws_wip_qtys[i], note=f"WIP_Receipt_{ws_job.workstation.name}_{ws_job.date_allot}",
                        regdate=ws_job.date_allot, status = "WIP")
                        db.session.add(new_wip_inventory)
                        db.session.commit()
                        ws_job.wipinventory = new_wip_inventory
                    if ws_job.rejectinventory:
                        ws_job.rejectinventory.qty= ws_reject_qtys[i]
                    else:
                        new_reject_inventory = Inventory(database=database, item=ws_job.item, item_unit=ws_job.item.unit, qty=ws_reject_qtys[i], note=f"REJECT_Receipt_{ws_job.workstation.name}_{ws_job.date_allot}",
                        regdate=ws_job.date_allot, status = "REJECT")
                        db.session.add(new_reject_inventory)
                        db.session.commit()
                        ws_job.rejectinventory = new_reject_inventory
                    db.session.commit()
            ## Update Material Issues for Auto Consumption Items
            autoMaterialIssue(ws_id, ws_date, database.id)
            workstation = Workstation.query.filter_by(database=database, id = ws_id).first()
            primary_workstation = Workstation.query.filter_by(database=database, id = current_user["workstation_id"]).first()
            numbers_list = get_mobile_numbers(current_user["data"])
            user = User.query.filter_by(id=current_user["user_id"]).first()
            for number in numbers_list:
                if workstation.id != primary_workstation.id:
                    resp = SEND_CUSTOM_MESSAGE(f"Production Received for {workstation.name} by {user.name}!", number)
                else:
                    resp = SEND_CUSTOM_MESSAGE(f"Production Received for PRIMARY WORKSTATION by {user.name}!", number)
            return redirect(request.headers.get('Referer', '/')) 
        ws_material_receive_flag = data.get("ws_material_receive_flag")
        print(ws_material_receive_flag)
        if ws_material_receive_flag:
            issue_job_ids = data.get("issue_job_ids[]",[])
            issue_qtys = data.get("issue_qtys[]",[])
            return_qtys = data.get("return_qtys[]",[])
            reject_qtys = data.get("reject_qtys[]",[])
            issue_units = data.get("issue_units[]",[])
            print(issue_job_ids, issue_qtys, return_qtys, reject_qtys, issue_units)
            if len(issue_job_ids)+ len(issue_qtys) +len(return_qtys) + len(reject_qtys) + len(issue_units) == 5*len(issue_job_ids):
                for i in range(len(issue_job_ids)):
                    ws_issue = WSMaterialIssue.query.filter_by(database=database, id=issue_job_ids[i]).first()
                    conv_factor = get_conversion_factor(database, ws_issue.item, issue_units[i])
                    try:
                        ws_issue.issue_qty = float(issue_qtys[i])/conv_factor
                    except:
                        flash(f"Problem in issue qty for {ws_issue.item.name}, passed value {issue_qtys[i]}", "danger")
                    try:
                        ws_issue.return_qty =float(return_qtys[i])/conv_factor
                    except:
                        flash(f"Problem in issue qty for {ws_issue.item.name}, passed value {return_qtys[i]}", "danger")
                    try:
                        ws_issue.reject_qty =float(reject_qtys[i])/conv_factor
                    except:
                        flash(f"Problem in issue qty for {ws_issue.item.name}, passed value {reject_qtys[i]}", "danger")
                    db.session.commit()
                    if ws_issue.item.iteminventory:
                        if ws_issue.item.iteminventory.consumption_mode == "MANUAL":
                            ws_issue.inventory.qty = (-1*( float(ws_issue.issue_qty) - float(ws_issue.return_qty) ))
                    if ws_issue.rejectinventory:
                        ws_issue.rejectinventory.qty= float(reject_qtys[i])/conv_factor
                    else:
                        new_reject_inventory = Inventory(database=database, item=ws_issue.item, item_unit=ws_issue.item.unit, qty=float(reject_qtys[i])/conv_factor, note=f"REJECT_Receipt_{ws_issue.workstation.name}_{ws_issue.date_issue}",
                        regdate=ws_issue.date_issue, status = "REJECT")
                        db.session.add(new_reject_inventory)
                        db.session.commit()
                        ws_issue.rejectinventory = new_reject_inventory
                    db.session.commit()

                numbers_list = get_mobile_numbers(current_user["data"])
                user = User.query.filter_by(id=current_user["user_id"]).first()
                for number in numbers_list:
                    resp = SEND_CUSTOM_MESSAGE(f"Material Quantities Issued in workstation by {user.name}!", number)
                flash("Material Issue Quantities Changed and Inventory Updated..", "success")
            return redirect(request.headers.get('Referer', '/'))        
        return redirect(request.headers.get('Referer', '/'))


class generate_slips(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        slip_type = Data.get("slip_type")
        ws_date = Data.get("ws_date")
        ws_id = Data.get("ws_id")
        if slip_type and ws_date and ws_id:
            workstation = Workstation.query.filter_by(database=database, id = ws_id).first()
            ws_resources = workstation.workstationresources
            ws_resource_string = " ".join([ws_resource.labor.name for ws_resource in ws_resources])
            if slip_type == "products":
                ws_jobs = WorkstationJob.query.filter_by(database=database,workstation=workstation, date_allot = ws_date).all()

                return render_template("workstations/product_receive_slip.html", WS_JOBS = ws_jobs, WS_RESOURCE_STRING={workstation.id:ws_resource_string})
            if slip_type == "materials":
                ws_issues = WSMaterialIssue.query.filter_by(database=database, workstation=workstation, date_issue = ws_date).all()
                return render_template("workstations/material_issue_slip.html", WS_ISSUES = ws_issues, WS_RESOURCE_STRING={workstation.id:ws_resource_string}, list_size = len(ws_issues))
            if slip_type == "products_child":
                child_maps = WorkstationMapping.query.filter_by(database=database, parent_ws = workstation).all()
                # print(childs)
                ws_jobs=[]
                ws_resource_string={}
                for child_map in child_maps:
                    ws_jobs += WorkstationJob.query.filter_by(database=database,workstation=child_map.child_ws, date_allot = ws_date).all()
                    child_ws_resources = WorkstationResource.query.filter_by(database=database, workstation=child_map.child_ws, date_allot = ws_date).all()
                    ws_resource_string[child_map.child_ws.id] = ",".join([ws_resource.labor.name for ws_resource in child_ws_resources])
                print(ws_resource_string)
                return render_template("workstations/product_receive_slip.html", WS_JOBS = ws_jobs, WS_RESOURCE_STRING=ws_resource_string)
            if slip_type == "materials_child":
                
                child_maps = WorkstationMapping.query.filter_by(database=database, parent_ws = workstation).all()
                # print(childs)
                ws_issues=[]
                ws_resource_string={}
                for child_map in child_maps:
                    ws_issues += WSMaterialIssue.query.filter_by(database=database, workstation=child_map.child_ws, date_issue = ws_date).all()
                    child_ws_resources = WorkstationResource.query.filter_by(database=database, workstation=child_map.child_ws, date_allot = ws_date).all()
                    ws_resource_string[child_map.child_ws.id] = ",".join([ws_resource.labor.name for ws_resource in child_ws_resources])
                    print(ws_resource_string)
                return render_template("workstations/material_issue_slip.html", WS_ISSUES = ws_issues, WS_RESOURCE_STRING=ws_resource_string, list_size = len(ws_issues))


class workstationConfig(Resource):
    @jwt_required()
    @requires_role(["WORKSTATION"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        data = request.get_json()
        date = data.get("date")
        UpdateWorkstationPreferences(database.id, date)
        return redirect(f"/workstations?date={date}")

class fg_btp_recv(Resource):
    @jwt_required()
    @requires_role(["BASIC"],0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        data = request.get_json()
        ws_ids = request.form.getlist("ws_ids[]")
        items_ids = request.form.getlist("items_ids[]")
        items_units = request.form.getlist("items_units[]")
        items_qtys = request.form.getlist("items_qtys[]")
        date_allot = request.form.get("chart_date")
        if (3*len(ws_ids) == len(items_ids)+ len(items_units)+ len(items_qtys)) and date_allot:
            ws_to_update= []
            print("Reacghededs")
            for i in range(len(ws_ids)):
                ws_id = ws_ids[i]
                item_id = items_ids[i]
                item_qty = items_qtys[i]
                item_unit = items_units[i]
                item = Item.query.filter_by(database=database, id=item_id).first()
                workstation = Workstation.query.filter_by(database=database, id=ws_id).first()
                if workstation and item:
                    if workstation not in ws_to_update:
                        ws_to_update.append(workstation)
                    try:
                        conv_factor = get_conversion_factor(database, item, item_unit)
                        item_qty = float(item_qty)/conv_factor
                    except:
                        item_qty = float(item_qty)
                    job_inventory = Inventory(item=item,regdate=date_allot, item_unit = item.unit, qty = item_qty, note=f"Receipt_{workstation.name}_{date_allot}", database=database)
                    db.session.add(job_inventory)
                    db.session.commit()
                    ws_job = WorkstationJob(item=item, qty_allot=0, qty_recv=item_qty, inventory=job_inventory,database=database, workstation=workstation, date_allot=date_allot)
                    db.session.add(ws_job)
                    db.session.commit()
                    updateParentJobs(database.id, ws_id, item_id, date_allot)
            for workstation in ws_to_update:
                # updateMaterialIssue(workstation, date_allot)
                autoMaterialIssue(workstation.id, date_allot, database.id)
        return redirect(request.headers.get('Referer', '/'))

class workstationsearch(Resource):
    @jwt_required()
    @requires_role(["BASIC"],0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        req_json= request.get_json()
        k = int(req_json.get('k', 10)) 
        date =req_json.get('date', None)
        item_name =req_json.get('name',None)
        item_id = req_json.get('id',None)
        filters = req_json.get('filters', None)
        items=[]
        if item_name and date:
            print("item_name", item_name)
            workstations_df = pd.DataFrame(
                db.session.query(Workstation.id,Workstation.name).filter(
                    Workstation.data_id == database.id).all(),columns=[ "workstation_id", "workstation_name"])
            workstation_res_df = pd.DataFrame(
                db.session.query(WorkstationResource.id,WorkstationResource.workstation_id,WorkstationResource.resource_id,
                    ).filter(
                    WorkstationResource.data_id == database.id, WorkstationResource.date_allot == date).all(),
                columns=["ws_resource_id", "workstation_id" ,"resource_id"]
                )
            print("DEBUGG")
            resources_df = pd.DataFrame(
                db.session.query(Labor.id,Labor.name,Labor.code).filter(Labor.data_id == database.id).all(),
                columns=["resource_id", "resource_name" ,"resource_code"]
                )
            workstation_res_df = pd.merge(workstation_res_df, workstations_df, on='workstation_id', how='right')

            item_name = item_name.upper()
            search_df = pd.merge(workstation_res_df, resources_df, on='resource_id', how="left").fillna("")
            search_df["workstation_score"] = search_df["workstation_name"].map(lambda x: compare_strings(item_name, x.upper()))
            search_df["resource_name_score"] = search_df["resource_name"].map(lambda x: compare_strings(item_name, x.upper()))
            search_df["resource_code_score"] = search_df["resource_code"].map(lambda x: compare_strings(item_name, x.upper()))
            search_df["max_score"] = search_df[["workstation_score", "resource_name_score", "resource_code_score"]].max(axis=1)
            # search_df = search_df.sort_values(by=['max_score'], ascending = False)
            print(search_df[["workstation_name", "resource_name" ,"max_score"]])
            search_df["resource_name"] = search_df["resource_name"]+":"+ search_df["resource_code"]
            resource_df = search_df.groupby(['workstation_id', 'workstation_name'])['resource_name'].agg(lambda x: ' '.join(x)).reset_index()
            # Grouping by workstation_id and workstation_name, then finding the max score
            max_score_df = search_df.groupby(['workstation_id', 'workstation_name'])['max_score'].max().reset_index()
            print("resource_df\n" ,resource_df)
            print("max_score_df\n" ,max_score_df)
            result_df = pd.merge(resource_df, max_score_df, on=['workstation_id', 'workstation_name'], how='inner')
            result_df = result_df.sort_values(by=['max_score'], ascending=False)
            if k>0:
                result_df = result_df.head(k)
            print(result_df[["workstation_id", "workstation_name", "resource_name"]])
            result_df["resource_name_2"] = result_df["resource_name"] 
            results = result_df.rename(columns={"workstation_id":"id", "workstation_name":"name", "resource_name":"code", "resource_name_2":"unit"}).to_dict(orient='records')
            return jsonify(results)
        return jsonify([])
        

# class addrecord(Resource):

#     @jwt_required()
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])