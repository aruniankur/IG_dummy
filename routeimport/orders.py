from models import db, Data, Order,User, Item, Customer, OrderItem,ItemUnit, Inventory, BOM, Invoice, OrderItemFinance, ItemFinance, Category, DataConfiguration, OrderItemDispatch, DeliveryBatch
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
from routeimport.decorators import requires_role, get_segment, createjson
from routeimport.purchase import create_invoices
from routeimport.utility import get_mobile_numbers
from routeimport.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE, html_to_pdf_kit, send_custom_pdf

def get_conversion_factor(database, item, unit_name):
    print(database.id, item.name, unit_name)
    if item.unit == unit_name:
        return 1
    item_unit = ItemUnit.query.filter_by(database=database, item = item, unit_name = unit_name).first()
    if item_unit:
        return item_unit.conversion_factor
    return 1

class getorder(Resource):
    @jwt_required()
    @requires_role(["ORDERS"], 0)
    def get(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        show_flag_param = request.args.get("show_flag", 'Active')
        if show_flag_param:
            show_flag = [show_flag_param]
        else:
            show_flag=['Active', 'Pending']
        ORDERS_DATA={}
        orders = Order.query.filter_by(database=database, order_type=0, status=show_flag_param).all()
        for order in orders:
            ORDERS_DATA[order.id]={}
            ORDERS_DATA[order.id]["order"]=createjson(order)
            customer=Customer.query.filter_by(id=order.customer_id, database=database).first()
            ORDERS_DATA[order.id]["customer"]=createjson(customer)
            # ORDERS_DATA[order.id]["items"]=[]
            # ORDERS_DATA[order.id]["chart_items"]=[]
            # #ORDERS_DATA[order.id]["invoices"] = {invoice.invoice_class: createjson(invoice) for invoice in order.invoice }
            # order_items = OrderItem.query.filter_by(order_id=order.id, database=database).all()
            # for order_item in order_items:
            #     ORDERS_DATA[order.id]["items"].append(createjson(order_item))
            #     ORDERS_DATA[order.id]["chart_items"].append([order_item.id, order_item.item.name, 
            #         order_item.order_qty, order_item.item.unit, 0, order_item.item.id])
        # items=Item.query.filter_by(database=database).all()
        # ITEMS=[]
        # for item in items:
        #     ITEMS.append([item.id, item.name, item.rate, item.unit])
        customers = Customer.query.filter_by(database=database).all()
        CUSTOMERS = []
        for customer in customers:
            CUSTOMERS.append([customer.id, customer.name])
        segment = get_segment(request, current_user['data'])
        categories = Category.query.filter_by(database=database, category_type = 2).all()
        CATEGORIES=[]
        for item in categories:
            CATEGORIES.append([item.id, item.name])
        order_id_set = None
        order = Order.query.filter_by(database=database, order_type = 0, status = show_flag[0]).first()
        if order:
            order_id_set = order.id
        params = {'order_id': order_id_set}
        orderinfo = order_info()
        order_info_html = ''
        try:
            orderinfo_post_response =orderinfo.post(params)
            if orderinfo_post_response:
                if 200 in orderinfo_post_response:
                    order_info_html = orderinfo_post_response['html']
        except:
            print("Error in catching order_info")
        order_id_set = int(order_id_set)
        #print({"template_name":'orders_list_component_ui', "orders_data":ORDERS_DATA, "items" : ITEMS, "customers":CUSTOMERS, "show_flag":show_flag, "segment":segment, "TODAY" :datetime.date.today(), "order_info_html":order_info_html, "order_id_set":order_id_set, "categories":CATEGORIES})
        return {"template_name":'orders_list_component_ui',"orders_data":ORDERS_DATA,"customers":CUSTOMERS, "show_flag":show_flag,
                "segment":segment, "TODAY" : str(datetime.date.today()), "order_info_html":order_info_html, "order_id_set":order_id_set, "categories":CATEGORIES}, 200


class addorder(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 0)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        new_order_cust_id = req_json.get("new_order_cust_id")
        new_order_note = req_json.get("new_order_note")
        new_order_desp_date = req_json.get("new_order_desp_date")
        if new_order_desp_date and new_order_cust_id:
            customer=  Customer.query.filter_by(id=new_order_cust_id, database=database).first()
            if not new_order_note:
                new_order_note=""
            order = Order(customer=customer, database = database, note = new_order_note, despdate=new_order_desp_date,actual_desp_date=new_order_desp_date, status="Pending")
            db.session.add(order)
            db.session.commit()
            order = Order.query.filter_by(database=database, id = order.id).first()
            create_invoices(database.id, order.id, 'proforma-invoice')
            return {"message": "order added successfully", "order_id":order.id}, 200
        return {"message": "data not found. please check input"}, 401
        
        
class deleteorder(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 1)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        delete_order_id = req_json.get("delete_order_id")
        if not delete_order_id:
            return {"message": "data not found. please check input"}, 401
        delete_order = Order.query.filter_by(database=database, id=delete_order_id).first()
        if delete_order:
            print(createjson(delete_order))
            delete_order_items = OrderItem.query.filter_by(database=database, order = delete_order).all()
            for delete_item in delete_order_items:
                if delete_item.inventory:
                    del_inventory = Inventory.query.filter_by(database=database, id=delete_item.inventory.id).first()
                    db.session.delete(del_inventory)
                db.session.delete(delete_item)
                db.session.commit()
            delete_order_invoices = Invoice.query.filter_by(database=database, order=delete_order).all()
            for inv in delete_order_invoices:
                db.session.delete(inv)
            db.session.delete(delete_order)
            db.session.commit()
            return {"message":"order deleted successfully"}, 200
        else:
            return {"message":"order not found"}, 401
        
    
class dispatchorder(Resource):
    @jwt_required()
    @requires_role(['ORDERS'],0)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        dispatched_order_id = req_json.get("dispatched_order_id")
        if dispatched_order_id:
            order = Order.query.filter_by(database=database, id=dispatched_order_id).first()
            order_items = OrderItem.query.filter_by(database=database, order=order).all()
            if not order_items or not order:
                return {"message": "order or order_items not found"}, 400
            new_order = Order(database=database, customer=order.customer, despdate = order.despdate, note = order.note + "_backorder", order_type=order.order_type, status="Pending")
            db.session.add(new_order)
            db.session.commit()
            new_order = Order.query.filter_by(database=database, id = new_order.id).first()
            delivery_batch_ids = []
            for delivery_batch in order.deliverybatches:
                if delivery_batch.status == 'DISPATCHED':
                    delivery_batch_ids.append(delivery_batch.id)
            order_items_df = pd.DataFrame(db.session.query(OrderItem.id,OrderItem.item_id,OrderItem.item_unit,OrderItem.order_qty,
                        ).filter(OrderItem.data_id == database.id, OrderItem.order_id == order.id).all(),columns=['order_item_id', 'item_id', 'item_unit','order_qty'])
            items_df = pd.DataFrame(db.session.query(Item.id,Item.name,Item.unit
                        ).filter(Item.data_id == database.id,
                            Item.id.in_(order_items_df['item_id'].tolist())
                        ).all(),columns=['id', 'item_name', 'unit'])
            order_item_dispatch_df = pd.DataFrame(
                db.session.query(OrderItemDispatch.id,OrderItemDispatch.dispatch_qty,OrderItemDispatch.delivery_batch_id,OrderItemDispatch.order_item_id,
                    ).filter(OrderItemDispatch.data_id == current_user['data'], OrderItemDispatch.delivery_batch_id.in_(delivery_batch_ids)).all(),
                columns=['order_item_dispatch_id', 'dispatch_qty', 'delivery_batch_id', 'order_item_id']
                )
            order_item_dispatch_df.dropna(inplace = True)
            #print(order_items_df, order_item_dispatch_df)
            order_data_df = pd.merge(order_items_df, order_item_dispatch_df, how='left', on='order_item_id')
            order_data_df =order_data_df.groupby('order_item_id').agg({'dispatch_qty':'sum', 'item_id':'first', 'order_qty':'first',
                'delivery_batch_id':'first', 'item_unit':'first', 'order_item_id':'first'
                })
            order_data_df = pd.merge(order_data_df, items_df, left_on='item_id', right_on='id', how='left')
            order_data_df["balance_qty"] = order_data_df["order_qty"]-order_data_df["dispatch_qty"]
            for order_item in order_items:
                balance_qty = order_data_df.loc[order_data_df['order_item_id'] == order_item.id]
                back_order_qty = max((order_item.order_qty - order_item.dispatch_qty),0)
                new_inventory= Inventory(database=database, item=order_item.item, item_unit=order_item.item_unit,qty = 0, note=order_item.inventory.note+"_backorder")
                db.session.add(new_inventory)
                new_order_item = OrderItem(database=database, order=new_order, item=order_item.item,item_unit = order_item.item_unit, order_qty= back_order_qty,inventory=new_inventory)
                db.session.add(new_order_item)
                db.session.commit()
                item = order_item.item
                if not item.itemfinance:
                    item_finance = ItemFinance(database=database, item=item)
                    db.session.add(item_finance)
                    db.session.commit()
                order_item_finance = OrderItemFinance(database=database, orderItem=new_order_item, sale_price=item.itemfinance.sale_price, discount_percentage=0, tax_percentage=item.itemfinance.tax)
                db.session.add(order_item_finance)
                db.session.commit()
            create_invoices(database.id, new_order.id, 'proforma-invoice')
            return {"message":"order dispatch successfully", "order_id": new_order.id}, 200
        
class bulkentry(Resource):
    @jwt_required()
    @requires_role(['ORDERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        req_json = request.get_json()
        database = Data.query.filter_by(id=current_user['data']).first()
        add_items_check = req_json.get("add_items_check")
        chart_id = req_json.get("chart_id")
        order_note = req_json.get("order_note")
        despdate = req_json.get("despdate")
        print(add_items_check)
        if add_items_check and chart_id:
            order = Order.query.filter_by(id = chart_id, database = database).first()
            if order_note and despdate:
                order.note = order_note
                order.despdate = despdate
                db.session.commit()
            id_list = req_json.get("items_ids[]",None)
            qty_list = req_json.get("items_qtys[]",None)
            item_units = req_json.get("item_units[]",None)
            chart_items_ids = req_json.get("chart_items_ids[]",None)
            add_type = req_json.get('add_type')
            print(id_list, chart_items_ids)    
            order_items = OrderItem.query.filter_by(order = order, database=database).all()
            order_items_df = pd.DataFrame(db.session.query(OrderItem.id,OrderItem.item_id,).filter(
                OrderItem.data_id == database.id, OrderItem.order_id == order.id).all(),columns=['order_item_id', 'item_id'])
            old_order_item_ids_list = order_items_df['order_item_id'].tolist()

            if add_type and add_type == "ADDITION":
                print("ADDITION TYPE")
                
            for item in order_items:
                if str(item.id) not in chart_items_ids:
                    if item.orderitemfinance:
                        db.session.delete(item.orderitemfinance)
                    for dispatch_item in item.orderitemdispatch:
                        if dispatch_item.inventory:
                            db.session.delete(dispatch_item.inventory)
                        db.session.delete(dispatch_item)
                    if item.inventory:
                        db.session.delete(item.inventory)
                    db.session.delete(item)
            for i in range(len(id_list)):

                order_item_id = chart_items_ids[i]

                if int(order_item_id) == -1:
                    item = Item.query.filter_by(id =id_list[i], database=database).first()
                    inventory = Inventory(item = item, qty = 0, item_unit = item.unit, note= f"order_{order.customer.name}_{order.despdate}",
                database=database) 
                    db.session.add(inventory)
                    conversion_factor = get_conversion_factor(database, item, item_units[i])
                    order_qty = float(qty_list[i])/conversion_factor
                    order_new_item = OrderItem(database=database, order=order, item=item, order_qty = order_qty, item_unit=item.unit, inventory=inventory)
                    db.session.add(order_new_item)
                    db.session.commit()
                    if not item.itemfinance:
                        item_finance = ItemFinance(database=database, item=item)
                        db.session.add(item_finance)
                        db.session.commit()
                    order_item_finance = OrderItemFinance(database=database, orderItem=order_new_item, sale_price=item.itemfinance.sale_price, discount_percentage=0, tax_percentage=item.itemfinance.tax)
                    db.session.add(order_item_finance)
                    db.session.commit()
                    print("OrderItemAdded")
                elif int(order_item_id) in old_order_item_ids_list:
                    order_item = OrderItem.query.filter_by(database=database, id=order_item_id).first()
                    if order_item:
                        conversion_factor = get_conversion_factor(database, order_item.item, item_units[i])
                        order_qty = float(qty_list[i])/conversion_factor
                        order_item.order_qty = order_qty
                        print("OrderItemEdited")
            # numbers_list = get_mobile_numbers(current_user["data"])
            # user = User.query.filter_by(id=current_user["user_id"]).first()
            # for number in numbers_list:
            #     if order.order_type == 0:
            #         resp = SEND_CUSTOM_MESSAGE(f"Items added to Sales Order of {order.customer.name} by {user.name}!", number)
            #     else:
            #         resp = SEND_CUSTOM_MESSAGE(f"Items added to Purchase Order of {order.customer.name} by {user.name}!", number)
            # referer_url = request.headers.get('Referer', '/')
            # new_url = ammend_referer_url(referer_url, 'order_id_set', order.id)
            # return redirect(new_url)    
            return {"message":"bulk order added"}, 200

class addorderitem(Resource):
    @jwt_required()
    @requires_role(['ORDERS'],1)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        item_id = req_json.get("item_id")
        order_id = req_json.get("order_id")
        order_qty = req_json.get("order_qty")
        desp_qty = req_json.get("desp_qty")
        order_unit = req_json.get("order_unit")
        if item_id and order_id and order_qty and desp_qty and order_unit:
            item = Item.query.filter_by(id=item_id).first()
            order=Order.query.filter_by(id=order_id).first()
            conversion_factor = get_conversion_factor(database, item, order_unit)
            order_qty = float(order_qty)/conversion_factor
            desp_qty = float(desp_qty)/conversion_factor
            inventory = Inventory(item = item, qty = -1*float(desp_qty), item_unit = item.unit, note= f"order_{order.customer.name}_{order.despdate}",database=database) 
            db.session.add(inventory)
            db.session.commit()
            order_item = OrderItem(item=item, order=order, database=database, order_qty=order_qty, dispatch_qty=desp_qty,
            item_unit=item.unit, inventory = inventory)
            db.session.add(order_item)
            db.session.commit()
            return {"Message":"order item added successfully", "order_id_set": order.id}, 200
        return {"Message":"please check the input"}, 401
    
existing_qty=0

class editorderitem(Resource):
    @jwt_required()
    @requires_role(['ORDERS'],1)
    def post(self):
            current_user = get_jwt_identity()
            req_json= request.get_json()
            database = Data.query.filter_by(id = current_user["data"]).first()
            edit_id=req_json.get("edit_id")
            edit_order_quant=req_json.get("edit_order_quant")
            edit_desp_quant=req_json.get("edit_desp_quant")
            edit_unit=req_json.get("edit_unit")
            print(edit_id, edit_order_quant, edit_desp_quant, edit_unit)
            if edit_id and edit_order_quant and edit_desp_quant:
                order_item=OrderItem.query.filter_by(id=edit_id, database=database).first()
                conversion_factor = get_conversion_factor(database, order_item.item, edit_unit)
                edit_order_quant = float(edit_order_quant)/conversion_factor
                edit_desp_quant = float(edit_desp_quant)/conversion_factor
                existing_qty = order_item.order_qty
                order_item.order_qty = edit_order_quant
                order_item.dispatch_qty = edit_desp_quant
                db.session.commit()
                inventory = Inventory.query.filter_by(id= order_item.inventory_ledger_id, database = database).first()
                inventory.qty = -1*float(edit_desp_quant)
                db.session.commit()
                return {"Message":"order item edited successfully", "order_id_set":order_item.order.id}, 200
            
    
class deleteorderitem(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 1)
    def post(self):
        current_user = get_jwt_identity()
        req_json= request.get_json()
        delete_id = req_json.get("delete_id")
        if not delete_id: 
            return {"Message": "no id found"} ,401
        database = Data.query.filter_by(id = current_user["data"]).first()
        order_item=OrderItem.query.filter_by(id=delete_id).first()
        existing_qty = order_item.order_qty
        existing_item=order_item.item
        inventory = Inventory.query.filter_by(id= order_item.inventory_ledger_id, database = database).first()
        db.session.delete(order_item)
        db.session.delete(inventory)
        print("delete item reached")
        return {"Message":"order item deleted successfully"}, 200
    

class order_info(Resource):
    @jwt_required()
    @requires_role(["ORDERS"],0)
    def post(self, req_json = None):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        DATA={}
        DATA["order_info"]=None
        DATA["order_items"]=None        
        TODAY = datetime.date.today()
        if req_json is None:
            req_json= request.get_json()
        order_id = req_json.get("order_id", None)
        if order_id:
            order = Order.query.filter_by(database=database, id=order_id).first()
            if not order:
                return {"message": "no order found"} , 401
            delivery_batches = order.deliverybatches
            delivery_batch_ids = []
            for delivery_batch in delivery_batches:
                if delivery_batch.status == 'DISPATCHED':
                    delivery_batch_ids.append(delivery_batch.id)
            ORDERS_DATA={}
            ORDERS_DATA[order.id]={}
            orderjson = createjson(order)
            for i in range(len(orderjson['deliverybatches'])):
                # [i1, i2]
                orderjson['deliverybatches'][i]['orderitemdispatch'] = createjson(order.deliverybatches[i].orderitemdispatch)
                
            orderjson['invoices'] = createjson(order.invoice)
            #for i in order.deliverybatches:
                #print(createjson(i.orderitemdispatch))
            ORDERS_DATA[order.id]["order"]=orderjson
            customer=Customer.query.filter_by(id=order.customer_id, database=database).first()
            ORDERS_DATA[order.id]["customer"]=createjson(customer)
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
                    ).filter(OrderItemDispatch.data_id == current_user['data'], OrderItemDispatch.delivery_batch_id.in_(delivery_batch_ids)).all(),
                columns=['order_item_dispatch_id', 'dispatch_qty', 'delivery_batch_id', 'order_item_id']
                )
            #print(order_items_df)
            order_item_dispatch_df.dropna(inplace = True)
            order_data_df = pd.merge(order_items_df, order_item_dispatch_df, how='left', on='order_item_id')
            order_data_df =order_data_df.groupby('order_item_id').agg({'dispatch_qty':'sum', 'item_id':'first', 'order_qty':'first',
                'delivery_batch_id':'first', 'item_unit':'first', 'order_item_id':'first'
                })

            order_data_df = pd.merge(order_data_df, items_df, left_on='item_id', right_on='id', how='left')
            order_data_df["balance_qty"] = order_data_df["order_qty"]-order_data_df["dispatch_qty"]
            order_items = OrderItem.query.filter_by(order_id=order.id, database=database).all()
            for _,order_item in order_data_df.iterrows():
                total_desp_qty = order_item.dispatch_qty
                ORDERS_DATA[order.id]["items"].append(json.loads(order_item.to_json()))
                ORDERS_DATA[order.id]["chart_items"].append([order_item.order_item_id, order_item.item_name,order_item.order_qty, order_item.item_unit, total_desp_qty, order_item.item_id])
            print(order_data_df)
            DATA["order_info"]=createjson(order)
            DATA["order_items"]=createjson(order_items)
            order_item_id = []
            for i in order_items:
                order_item_id.append(i.item_id)
            inventory_stock_data = db.session.query(Inventory.item_id,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity")).join(
            Item, Inventory.item_id == Item.id).group_by(
            Inventory.item_id, Item.name, Item.unit).filter(
            Inventory.data_id == current_user["data"], Inventory.status == "ACTIVE", Inventory.item_id.in_(order_item_id)).all()
            inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit","total_stock" ])
            inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
            #print({"message":"Redirect", "uri": "order_info_component.html" ,"orders_data":ORDERS_DATA, "DATA": DATA, "TODAY":TODAY, "INVENTORY_DATA":inventory_dict })
            return {"message":"Redirect", "uri": "order_info_component.html" ,"orders_data":ORDERS_DATA, "order_data_df": json.loads(order_data_df.to_json(orient='records')),"DATA": DATA, "TODAY":str(TODAY), "INVENTORY_DATA":inventory_dict }, 302
        return {"message": "no order id found"}, 200
    
    
class order_sheet(Resource):
    @jwt_required()
    @requires_role(['ORDER'], 0)
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
            order_items_df = pd.DataFrame(db.session.query(OrderItem.id,OrderItem.item_id,OrderItem.item_unit,OrderItem.order_qty,
                        ).filter(OrderItem.data_id == database.id, OrderItem.order_id == order_id).all(),
                        columns=['order_item_id', 'item_id', 'item_unit','order_qty']
                    )
            items_df = pd.DataFrame(db.session.query(Item.id,Item.name,
                        Item.unit,Item.code).filter(Item.data_id == database.id,
                            Item.id.in_(order_items_df['item_id'].tolist())
                        ).all(),columns=['id', 'item_name', 'unit', "item_code"])
            order_item_dispatch_df = pd.DataFrame(
                db.session.query(OrderItemDispatch.id,OrderItemDispatch.dispatch_qty,
                        OrderItemDispatch.delivery_batch_id,OrderItemDispatch.order_item_id,
                    ).filter(OrderItemDispatch.data_id == current_user['data'], OrderItemDispatch.delivery_batch_id.in_(delivery_batch_ids)).all(),
                columns=['order_item_dispatch_id', 'dispatch_qty', 'delivery_batch_id', 'order_item_id'])
            order_item_dispatch_df.dropna(inplace = True)
            # print(order_items_df, order_item_dispatch_df)
            order_data_df = pd.merge(order_items_df, order_item_dispatch_df, how='left', on='order_item_id')
            order_data_df =order_data_df.groupby('order_item_id').agg({'dispatch_qty':'sum', 'item_id':'first', 'order_qty':'first',
                'delivery_batch_id':'first', 'item_unit':'first', 'order_item_id':'first'})
            order_data_df = pd.merge(order_data_df, items_df, left_on='item_id', right_on='id', how='left')
            order_data_df["balance_qty"] = order_data_df["order_qty"]-order_data_df["dispatch_qty"]
            order_data_dict = order_data_df.set_index("order_item_id").to_dict(orient="index")
            inventory_stock_data = db.session.query(
                Inventory.item_id,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity")).join(
            Item, Inventory.item_id == Item.id).group_by(
            Inventory.item_id, Item.name, Item.unit).filter(
            Inventory.data_id == current_user["data"], Inventory.status == "ACTIVE").all()
        # Convert inventory_stock_data to DataFrame
            inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit","total_stock" ])
            inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
            return {'message':"redirect", "uri": "order_sheet.html","order":createjson(order), "order_data_dict":order_data_dict, "inventory_dict": inventory_dict}, 302
        return {"message":"NO ORDER ID"}, 401
    
    
    
class ordervalidation(Resource):
    @jwt_required()
    @requires_role(['ORDER'], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id = current_user["data"]).first()
        order_id = data.get("order_id")
        approval = data.get("approval")
        if order_id and approval:
            order = Order.query.filter_by(database=database, id = order_id).first()
            if not order:
                return {"message":"order not found"}, 401
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
    @jwt_required()
    @requires_role(['ORDER'], 2)
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
        return jsonify(result)
    
    
class get_demand_breakup(Resource):
    @jwt_required()
    @requires_role(['ORDER'], 0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        item_id = req_json.get("item_id", None)
        result=[]
        if item_id:
            item = Item.query.filter_by(database=database, id=item_id).first()
            orders = pd.DataFrame(
                db.session.query(Order.id,Customer.name,Order.regdate,Order.despdate,Order.status,Order.note,Order.order_type,
                    ).join(Customer, Order.customer_id == Customer.id).filter(Order.data_id == database.id, Order.order_type==0).all(),
                columns = ["order_id","customer_name","regdate","despdate","status","note","order_type"])
            order_items = pd.DataFrame(
                db.session.query(OrderItem.id,OrderItem.order_id,OrderItem.item_id,OrderItem.item_unit,OrderItem.order_qty,OrderItem.dispatch_qty,OrderItem.inventory_ledger_id
                    ).filter(OrderItem.data_id == database.id).all(),
                columns = ["order_item_id","order_id","item_id","item_unit","order_qty","dispatch_qty","inventory_ledger_id"])

            boms = pd.DataFrame(
                db.session.query(BOM.id,BOM.parent_item_id,BOM.child_item_id,BOM.child_item_qty,BOM.child_item_unit,BOM.margin,
                    ).filter(BOM.data_id == database.id).all(),
                columns = ["bom_id","parent_item_id","child_item_id","child_item_qty","child_item_unit","margin"])
            items = pd.DataFrame(
                db.session.query(Item.id,Item.name,Item.unit,
                    ).filter(Item.data_id == database.id).all(),
                columns = ["item_id","name","unit"])
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
        return jsonify(result)
    
    
class updateDeliveryBatchInvoice(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 0)
    def get(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        orders = Order.query.filter_by(database = database, status = "Active").all()
        for order in orders:
            for delivery_batch in order.deliverybatches:
                if not delivery_batch.invoice_id:
                    if order.order_type == 0:
                        create_invoices(database.id, order.id, 'delivery-slip', [delivery_batch.id])
                    else:
                        create_invoices(database.id, order.id, 'receive-slip', [delivery_batch.id])
    

class addDeliveryBatch(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json = request.get_json()
        batch_name = req_json.get('batch_name')
        desp_date = req_json.get('desp_date')
        order_id = req_json.get('order_id')
        t = 0
        if batch_name:
            t = t + 1
        if order_id:
            t = t + 1
        if desp_date:   
            t = t + 1
        if t == 3:
            order = Order.query.filter_by(id = order_id, database = database).first()
            if not order:
                return {"message":"no such order found"}, 401
            new_batch = DeliveryBatch(order=order, database=database, batch_name = batch_name, despdate = desp_date, actual_desp_date=desp_date, status="STORE")
            db.session.add(new_batch)
            db.session.commit()
            for order_item in order.orderitems:
                dispatch_order_item = OrderItemDispatch(database=database, orderItem = order_item, deliverybatch = new_batch)
                db.session.add(dispatch_order_item)
            db.session.commit()
            if order.order_type == 0:
                create_invoices(database.id, order.id, 'delivery-slip', [new_batch.id])
            else:
                create_invoices(database.id, order.id, 'receive-slip', [new_batch.id])
            return {"messages":"added successfully", "id": new_batch.id}, 200
        return {"message":"no order id or batch name or desp date found"}, 401
    

class generateInvoice(Resource):
    @jwt_required()
    @requires_role(["ORDERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json = request.get_json()
        delivery_batch_ids = req_json.getlist('delivery_batch_ids[]')
        order_id = req_json.get('order_id')
        print("batch_ids", delivery_batch_ids, 'order_id', order_id)
        if len(delivery_batch_ids) and order_id:
            order = Order.query.filter_by(id = order_id, database = database).first()
            invoice_id = create_invoices(database.id, order.id, 'sales-invoice', delivery_batch_ids)
            return {"message":"redirect", "redirect_uri": f'/invoices?invoice_id={invoice_id}&action=view'} , 302
        return {"message": "Invalid request"}, 401


class dispatchchallan(Resource):
    @jwt_required()
    @requires_role(['ORDERS'], 0)
    def post(self):
        current_user = get_jwt_identity()
        database=Data.query.filter_by(id=current_user["data"]).first()
        req_json = request.get_json()
        order_id = req_json.get("order_id",None)
        dispatch_flag = req_json.get("dispatch_flag",None)
        dispatch_order_id = req_json.get("dispatch_order_id",None)
        action = req_json.get("action",None)
        delivery_batch_id = req_json.get('delivery_batch_id',None)
        actual_desp_date = req_json.get("actual_desp_date",None)
        if dispatch_flag and dispatch_order_id and action and delivery_batch_id:
            order = Order.query.filter_by(database=database, id = dispatch_order_id).first()
            delivery_batch = DeliveryBatch.query.filter_by(database=database, id=delivery_batch_id).first()
            if action == 'dispatch':
                delivery_batch.status = "DISPATCHED"
                db.session.commit()
            if actual_desp_date:
                delivery_batch.actual_desp_date = actual_desp_date
                db.session.commit()
                
        order_item_ids= req_json.get("order_item_ids[]", None)
        desp_qtys=req_json.get("desp_qtys[]", None)
        desp_units=req_json.get("desp_units[]", None)
        print(desp_units)
        result = []
        for i in range(len(order_item_ids)):
            order_item_id = order_item_ids[i]
            edit_disp_qty= desp_qtys[i]
            # order_item = OrderItem.query.filter_by(database=database, id=order_item_id).first()
            try:
                order_item = OrderItemDispatch.query.filter_by(database=database, id=order_item_id).first()
                conversion_factor = get_conversion_factor(database, order_item.orderItem.item, desp_units[i])
                edit_disp_qty = float(edit_disp_qty)/conversion_factor
                order_item.dispatch_qty = edit_disp_qty
                db.session.commit()
            except:
                result.append(f"order_item {i} not found")
            if action == 'dispatch':
                if order_item.inventory_ledger_id:
                    inventory = Inventory.query.filter_by(id= order_item.inventory_ledger_id, database = database).first()
                else:
                    inventory = Inventory(item = order_item.orderItem.item, qty = 0, item_unit = order_item.orderItem.item.unit, note= "",
                 database=database) 
                    db.session.add(inventory)
                    db.session.commit()
                    order_item.inventory = inventory
                    db.session.commit()
                if order.order_type == 0:
                    inventory.qty = -1*float(edit_disp_qty)
                    inventory.note = f"sales_{delivery_batch.batch_name}_{order.customer.name}_{datetime.date.today()}"
                else:
                    inventory.qty = 1*float(edit_disp_qty)
                    inventory.note = f"purchase_{delivery_batch.batch_name}_{order.customer.name}_{datetime.date.today()}"

                inventory.regdate = delivery_batch.actual_desp_date
                db.session.commit()
        numbers_list = get_mobile_numbers(current_user["data"])
        user = User.query.filter_by(id=current_user["user_id"]).first()
        show_flag = 'Dispatched' if order.status == 'Dispatched' else 'Active'
        if action=="save":
            for number in numbers_list:
                if order.order_type == 0:
                    resp = SEND_CUSTOM_MESSAGE(f"Items saved for Dispatch of order, {order.customer.name} by {user.name}!", number)
                    result.append([f"Items saved for Dispatch of order, {order.customer.name} by {user.name}!", number])
                else:
                    resp = SEND_CUSTOM_MESSAGE(f"Items saved for Receive of order, {order.customer.name} by {user.name}!", number)
                    result.append([f"Items saved for Receive of order, {order.customer.name} by {user.name}!", number])
            # return redirect(f"/dispatchchallan?order_id={order.id}", code=302)
            if order.order_type == 0:
                return {"message": "Items Saved in Dispatch Console!", "order_id": order.id, "flag": show_flag, "message_result": result}, 302
            else:
                return {"message": "Items Saved in Dispatch Console!", "order_id": order.id, "flag": show_flag, "message_result": result}, 302
 
        ## Invoice
        # url = url_for('invoice_bp.invoice_route', order_id=order.id, action='generate', invoice_class='delivery-slip', invoice_file='delivery_slip')
        
        # this need changes  - Aruni 
        
        
        # if delivery_batch.invoice:
            
            # url = url_for('invoice_bp.invoice_route', invoice_id=delivery_batch.invoice.id, action='generate', delivery_batch_id=delivery_batch.id)

            # base_url = current_app.config['API_BASE_URL']
            # base_url_local = current_app.config['API_BASE_URL_LOCAL']
            # # Pass request.cookies as context in the headers
            # headers = {'Cookie': '; '.join([f"{key}={value}" for key, value in request.cookies.items()])}
            # try:
            #     full_url = f"{base_url}{url}"
            #     response = requests.get(full_url, cookies=request.cookies)
            # except:
            #     full_url = f"{base_url_local}{url}"
            #     response = requests.get(full_url, cookies=request.cookies)
            # # response = requests.get(full_url)
            # invoice_html = response.text
            # # print(invoice_html)
            # result_pdf_path, result_pdf_name = html_to_pdf_kit(invoice_html,current_user['data'])
            # for number in numbers_list:
            #     resp = SEND_CUSTOM_MESSAGE(f"Items Dispatched of order, {order.customer.name} by {user.name}!", number)
            #     send_custom_pdf(number, result_pdf_name, result_pdf_path)
            # return redirect("/orders?show_flag=Dispatched", code=302)
        # if order.order_type == 0:
        #     return redirect(f"/orders?show_flag={show_flag}&order_id_set={order.id}", code=302)
        # else:
        #     return redirect(f"/purchase?show_flag={show_flag}&order_id_set={order.id}", code=302)
        
        DATA={}
        DATA["order_info"]=None
        DATA["order_items"]=None
        if order_id:
            order = Order.query.filter_by(database=database, id = order_id).first()
            order_items = OrderItem.query.filter_by(database=database, order = order).all()
            DATA["order_info"]=createjson(order)
            DATA["order_items"]=createjson(order_items)
        inventory_stock_data = db.session.query(Inventory.item_id,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity")
            ).join(Item, Inventory.item_id == Item.id).group_by(Inventory.item_id, Item.name, Item.unit).filter(Inventory.data_id == current_user["data"]).all()
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit","total_stock" ])
        inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
        return {"message":"redirect", "url":"dispatch_challan_new.html", "Data":DATA, "Today": str(datetime.date.today()), "Inventory_data":inventory_dict}, 200