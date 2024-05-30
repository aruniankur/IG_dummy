from models import db, Data, Order,User, Item, Customer, OrderItem, Inventory, BOM, Invoice, OrderItemFinance, ItemFinance, Category, DataConfiguration, OrderItemDispatch, DeliveryBatch
import pandas as pd
import json
from flask_restful import Api, Resource
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import smtplib
import requests
import datetime
from routeimport.decorators import requires_role
from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
import datetime




class order_info(Resource):
    @jwt_required
    #@requires_role()
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        DATA={}
        DATA["order_info"]=None
        DATA["order_items"]=None        
        TODAY = datetime.date.today()
        req_json= request.get_json()
        order_id = req_json.get("order_id", None)
        if order_id:
            order = Order.query.filter_by(database=database, id=order_id).first()
            delivery_batches = order.deliverybatches
            delivery_batch_ids = []
            for delivery_batch in delivery_batches:
                if delivery_batch.status == 'DISPATCHED':
                    delivery_batch_ids.append(delivery_batch.id)
            ORDERS_DATA={}
            ORDERS_DATA[order.id]={}
            ORDERS_DATA[order.id]["order"]=order
            customer=Customer.query.filter_by(id=order.customer_id, database=database).first()
            ORDERS_DATA[order.id]["customer"]=customer
            ORDERS_DATA[order.id]["items"]=[]
            ORDERS_DATA[order.id]["chart_items"]=[]
            ORDERS_DATA[order.id]["orderitemdispatch"]=[]

            order_items_df = pd.DataFrame(db.session.query(
                        OrderItem.id,
                        OrderItem.item_id,
                        OrderItem.item_unit,
                        OrderItem.order_qty,
                        ).filter(OrderItem.data_id == database.id, OrderItem.order_id == order_id).all(),
                        columns=['order_item_id', 'item_id', 'item_unit','order_qty']
                    )
            items_df = pd.DataFrame(db.session.query(
                        Item.id,
                        Item.name,
                        Item.unit
                        ).filter(Item.data_id == database.id,
                            Item.id.in_(order_items_df['item_id'].tolist())
                        ).all(),
                        columns=['id', 'item_name', 'unit']
                    )
            order_item_dispatch_df = pd.DataFrame(
                db.session.query(
                        OrderItemDispatch.id,
                        OrderItemDispatch.dispatch_qty,
                        OrderItemDispatch.delivery_batch_id,
                        OrderItemDispatch.order_item_id,
                    ).filter(OrderItemDispatch.data_id == session['data'], OrderItemDispatch.delivery_batch_id.in_(delivery_batch_ids)).all(),
                columns=['order_item_dispatch_id', 'dispatch_qty', 'delivery_batch_id', 'order_item_id']
                )
            order_item_dispatch_df.dropna(inplace = True)
            print(order_items_df, order_item_dispatch_df)
            order_data_df = pd.merge(order_items_df, order_item_dispatch_df, how='left', on='order_item_id')
            order_data_df =order_data_df.groupby('order_item_id').agg({'dispatch_qty':'sum', 'item_id':'first', 'order_qty':'first',
                'delivery_batch_id':'first', 'item_unit':'first', 'order_item_id':'first'
                })

            order_data_df = pd.merge(order_data_df, items_df, left_on='item_id', right_on='id', how='left')
            order_data_df["balance_qty"] = order_data_df["order_qty"]-order_data_df["dispatch_qty"]
            order_items = OrderItem.query.filter_by(order_id=order.id, database=database).all()
            for _,order_item in order_data_df.iterrows():
                print(order_item)
                total_desp_qty = order_item.dispatch_qty
                ORDERS_DATA[order.id]["items"].append(order_item)
                ORDERS_DATA[order.id]["chart_items"].append([order_item.order_item_id, order_item.item_name,order_item.order_qty, order_item.item_unit, total_desp_qty, order_item.item_id])

            DATA["order_info"]=order
            DATA["order_items"]=order_items
            inventory_stock_data = db.session.query(
                Inventory.item_id,
                Item.name,
                Item.unit,
                db.func.sum(Inventory.qty).label("total_quantity")
            ).join(
            Item, Inventory.item_id == Item.id).group_by(
            Inventory.item_id, Item.name, Item.unit).filter(
            Inventory.data_id == session["data"], Inventory.status == "ACTIVE").all()
            inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit","total_stock" ])
            inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
            return jsonify({"html": render_template("orders/order_info_component.html", orders_data=ORDERS_DATA, DATA = DATA,TODAY=TODAY, INVENTORY_DATA=inventory_dict)})
        return "NO ORDER ID"
    
    

class order_sheet(Resource):
    @jwt_required
    #@requires_role()
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        DATA={}
        DATA["order_info"]=None
        DATA["order_items"]=None        
        TODAY = datetime.date.today()
        req_json= request.get_json()
        order_id = req_json.get("order_id", None)
        if order_id:
            order = Order.query.filter_by(database=database, id=order_id).first()
            delivery_batches = order.deliverybatches
            delivery_batch_ids = []
            for delivery_batch in delivery_batches:
                if delivery_batch.status == 'DISPATCHED':
                    delivery_batch_ids.append(delivery_batch.id)
            order_items_df = pd.DataFrame(db.session.query(
                        OrderItem.id,
                        OrderItem.item_id,
                        OrderItem.item_unit,
                        OrderItem.order_qty,
                        ).filter(OrderItem.data_id == database.id, OrderItem.order_id == order_id).all(),
                        columns=['order_item_id', 'item_id', 'item_unit','order_qty']
                    )
            items_df = pd.DataFrame(db.session.query(
                        Item.id,
                        Item.name,
                        Item.unit,
                        Item.code
                        ).filter(Item.data_id == database.id,
                            Item.id.in_(order_items_df['item_id'].tolist())
                        ).all(),
                        columns=['id', 'item_name', 'unit', "item_code"]
                    )
            order_item_dispatch_df = pd.DataFrame(
                db.session.query(
                        OrderItemDispatch.id,
                        OrderItemDispatch.dispatch_qty,
                        OrderItemDispatch.delivery_batch_id,
                        OrderItemDispatch.order_item_id,
                    ).filter(OrderItemDispatch.data_id == session['data'], OrderItemDispatch.delivery_batch_id.in_(delivery_batch_ids)).all(),
                columns=['order_item_dispatch_id', 'dispatch_qty', 'delivery_batch_id', 'order_item_id']
                )
            order_item_dispatch_df.dropna(inplace = True)
            # print(order_items_df, order_item_dispatch_df)
            order_data_df = pd.merge(order_items_df, order_item_dispatch_df, how='left', on='order_item_id')
            order_data_df =order_data_df.groupby('order_item_id').agg({'dispatch_qty':'sum', 'item_id':'first', 'order_qty':'first',
                'delivery_batch_id':'first', 'item_unit':'first', 'order_item_id':'first'
                })

            order_data_df = pd.merge(order_data_df, items_df, left_on='item_id', right_on='id', how='left')
            order_data_df["balance_qty"] = order_data_df["order_qty"]-order_data_df["dispatch_qty"]
            order_data_dict = order_data_df.set_index("order_item_id").to_dict(orient="index")
            inventory_stock_data = db.session.query(
                Inventory.item_id,
                Item.name,
                Item.unit,
                db.func.sum(Inventory.qty).label("total_quantity")
            ).join(
            Item, Inventory.item_id == Item.id).group_by(
            Inventory.item_id, Item.name, Item.unit).filter(
            Inventory.data_id == session["data"], Inventory.status == "ACTIVE").all()
        # Convert inventory_stock_data to DataFrame
            inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit","total_stock" ])
            # print(inventory_stock_df)
            inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
            return render_template("orders/order_sheet.html", ORDER=order, order_data_dict=order_data_dict, inventory_dict=inventory_dict)
        return "NO ORDER ID"
    
    
    
class ordervalidation(Resource):
    @jwt_required
    #@required_role()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        order_id = data.get("order_id")
        approval = data.get("approval")
        if order_id and approval:
            order = Order.query.filter_by(database=database, id = order_id).first()
            if approval == "ACTIVE":
                order.status = "Active"
                order.active_date = datetime.date.today()
            elif approval == "COMPLETED":
                order.status = "Dispatched"
            elif approval == 'PENDING':
                order.status = 'Pending'
            db.session.commit()
            return {"Message":f"The status of the order by {order.customer.name} has been changed to {order.status}."}, 200
        return {"Message":"check input"}, 401
    

        
class get_order_breakup(Resource):
    @jwt_required
    #@required_role()
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        item_id = req_json.get("item_id", None)
        result=[]
        if item_id:
            item = Item.query.filter_by(database=database, id=item_id).first()
            orders = Order.query.filter_by(database=database, status="Active", order_type=0).all()
            for order in orders:
                for order_item in order.orderitems:
                    if order_item.item.id == item.id:
                        result.append({"code":item.code, "name":item.name,"item_id":item.id,"order_item_id":order_item.id,
                        "customer_name":order.customer.name, "dispatch_date":order.despdate, "note":order.note,
                        "unit":order_item.item_unit,"order_qty":order_item.order_qty, "dispatch_qty":order_item.dispatch_qty})
        return jsonify(result), 200
    
class get_demand_breakup(Resource):
    @jwt_required
    #@required_role
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        item_id = req_json.get("item_id", None)
        result=[]
        if item_id:
            item = Item.query.filter_by(database=database, id=item_id).first()
            orders = pd.DataFrame(
                db.session.query(
                    Order.id,
                    Customer.name,
                    Order.regdate,
                    Order.despdate,
                    Order.status,
                    Order.note,
                    Order.order_type,
                    # Order.data_id,
                    ).join(Customer, Order.customer_id == Customer.id).filter(Order.data_id == database.id, Order.order_type==0).all(),
                columns = ["order_id","customer_name","regdate","despdate","status","note","order_type"]
                )
            order_items = pd.DataFrame(
                db.session.query(
                    OrderItem.id,
                    OrderItem.order_id,
                    OrderItem.item_id,
                    OrderItem.item_unit,
                    OrderItem.order_qty,
                    OrderItem.dispatch_qty,
                    # OrderItem.data_id,
                    OrderItem.inventory_ledger_id
                    ).filter(OrderItem.data_id == database.id).all(),
                columns = ["order_item_id","order_id","item_id","item_unit","order_qty","dispatch_qty","inventory_ledger_id"]
                )

            boms = pd.DataFrame(
                db.session.query(
                    BOM.id,
                    BOM.parent_item_id,
                    BOM.child_item_id,
                    BOM.child_item_qty,
                    BOM.child_item_unit,
                    BOM.margin,
                    # BOM.data_id,
                    ).filter(BOM.data_id == database.id).all(),
                columns = ["bom_id","parent_item_id","child_item_id","child_item_qty","child_item_unit","margin"]
                )
            items = pd.DataFrame(
                db.session.query(
                    Item.id,
                    Item.name,
                    Item.unit,
                    # Item.data_id,
                    ).filter(Item.data_id == database.id).all(),
                columns = ["item_id","name","unit"]
                )
            order_items_df = pd.merge(order_items, orders,left_on='order_id', right_on='order_id', how='inner')
            order_items_df = order_items_df[order_items_df['status'] == 'Active']
            order_items_df = pd.merge(order_items_df, items, left_on = 'item_id', right_on='item_id', how='inner')
            work_df = pd.DataFrame({"parent_item_id_2":[item.id]})
            print(work_df)
            flag = True
            while flag:
                order_item_work_df = pd.merge(left=work_df, right=order_items_df, left_on='parent_item_id_2', right_on='item_id', how='inner')
                if not order_item_work_df.empty:
                    result+= order_item_work_df.to_dict(orient='records')
                    print(result)
                work_df = work_df[["parent_item_id_2"]]
                work_df = pd.merge(left=work_df, right=boms, right_on= 'child_item_id', left_on='parent_item_id_2', how='inner')
                if work_df.empty:
                    flag = False
                work_df.drop("parent_item_id_2", axis=1)
                work_df["parent_item_id_2"] = work_df["parent_item_id"]
        return jsonify(result), 200
    
    
