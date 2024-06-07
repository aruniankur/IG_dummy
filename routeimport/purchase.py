from models import db, Data, Order,User, Item, Customer, OrderItem, Inventory, BOM, Invoice, OrderItemFinance, ItemFinance, Category, DataConfiguration, OrderItemDispatch, DeliveryBatch, ItemUnit
import pandas as pd
import json
from flask_restful import Api, Resource
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
import json
import smtplib
import requests
import datetime
from datetime import date
from routeimport.decorators import requires_role
from models import OrderItemDispatch, DeliveryBatch
from flask import request, render_template, jsonify
from routeimport.decorators import requires_role, get_segment, createjson

def ammend_referer_url(referer_url, param='order_id_set', param_value=0):
    if param in referer_url:
        i1 = referer_url.find(param)
        i2 = referer_url[i1:].find('=')
        i3 = referer_url[i1:].find('&')
        if i3 == -1:
            new_url = referer_url[:i1]+f'{param}='+ str(param_value)
        else:
            new_url = referer_url[:i1]+f'{param}='+ str(param_value)+referer_url[i1:][i3:]
        print(new_url)
    else:
        if '?' in referer_url:
            new_url = referer_url+f"&{param}={param_value}"
        else:
            new_url = referer_url+f"?{param}={param_value}"
    return new_url

def create_invoices(data_id, new_order_id, invoice_class, delivery_batch_ids=[]):
    database = Data.query.filter_by(id = data_id).first()
    order = Order.query.filter_by(database = database, id=new_order_id).first()
    new_order_desp_date =  order.despdate

    data_config = DataConfiguration.query.filter_by(database=database).first()
    invoice_config = data_config.invoice_config
    invoice_config_dict = json.loads(invoice_config)
    if not len(invoice_config_dict.keys()):
        invoice_config_dict = {"proforma-invoice":{"invoice-class":"proforma-invoice", "invoice-file": "invoices/proforma_invoice.html"},
        "sales-invoice":{"invoice-class":"sales-invoice", "invoice-file": "invoices/sales_invoice.html"},
        "delivery-slip":{"invoice-class":"delivery-slip", "invoice-file": "invoices/delivery_slip.html"},
        "purchase-invoice":{"invoice-class":"purchase-invoice", "invoice-file": "invoices/purchase_invoice.html"},
        "purchase-order":{"invoice-class":"purchase-order", "invoice-file": "invoices/purchase_order.html"},
        "receive-slip":{"invoice-class":"receive-slip", "invoice-file": "invoices/receive_slip.html"}}
        data_config.invoice_config = json.dumps(invoice_config_dict)
        db.session.commit()
    invoice_config_dict = json.loads(data_config.invoice_config)

    if order.order_type == 0:
        if invoice_class== 'sales-invoice':
            delivery_batches = DeliveryBatch.query.filter(DeliveryBatch.id.in_(delivery_batch_ids), DeliveryBatch.data_id==database.id).all()
            invoice_count = len(Invoice.query.filter_by(database=database, invoice_class="sales-invoice").all()) + 1
            invoice_number = f"SALES/{invoice_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="sales-invoice", invoice_number= invoice_number).first()
            while number_check:
                invoice_count+=1
                invoice_number = f"SALES/{invoice_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="sales-invoice", invoice_number= invoice_number).first()
            sales_invoice = Invoice(database=database, order_id=order.id, invoice_number=invoice_number, invoice_class="sales-invoice", invoice_date=new_order_desp_date)
            db.session.add(sales_invoice)
            db.session.commit()

            delivery_batches_id_string = ""
            for batch in delivery_batches:
                delivery_batches_id_string+= str(batch.id)+","
            delivery_batches_id_string = delivery_batches_id_string[:-1]
            proforma_invoice = Invoice.query.filter_by(database=database, order=order, invoice_class='proforma-invoice').first()
            sales_invoice.invoice_html= jsonify(uri=invoice_config_dict["sales-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=sales_invoice, tax_exclusive_price_flag="NO", intra_state_gst_flag ="YES",
                delivery_batches= delivery_batches, delivery_batches_id_string=delivery_batches_id_string, proforma_invoice=proforma_invoice)
            db.session.commit()
            return {"message" : sales_invoice.id}, 200
        
        elif invoice_class == 'proforma-invoice':
            prof_invoice_count = len(Invoice.query.filter_by(database=database, invoice_class="proforma-invoice").all()) + 1
            prof_invoice_number = f"PROFORMA/{prof_invoice_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="proforma-invoice", invoice_number= prof_invoice_number).first()
            while number_check:
                prof_invoice_count+=1
                prof_invoice_number = f"PROFORMA/{prof_invoice_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="proforma-invoice", invoice_number= prof_invoice_number).first()
            prof_invoice = Invoice(database=database, order=order, invoice_number=prof_invoice_number,invoice_class="proforma-invoice", invoice_date=new_order_desp_date)
            db.session.add(prof_invoice)
            db.session.commit()
            #prof_invoice.invoice_html= jsonify(uri=invoice_config_dict["proforma-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=prof_invoice, tax_exclusive_price_flag="NO", intra_state_gst_flag ="YES")
            db.session.commit()
            return {"message" : prof_invoice.id }, 200 
        
        elif invoice_class == 'delivery-slip':
            delivery_batch_id = delivery_batch_ids[0]
            delivery_batch = DeliveryBatch.query.filter_by(database = database, id = delivery_batch_id).first()

            delivery_slip_count = len(Invoice.query.filter_by(database=database, invoice_class="delivery-slip").all()) + 1
            deliver_slip_number = f"DELIVERY/{delivery_slip_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="delivery-slip", invoice_number= deliver_slip_number).first()
            while number_check:
                delivery_slip_count+=1
                deliver_slip_number = f"DELIVERY/{delivery_slip_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="delivery-slip", invoice_number= deliver_slip_number).first()
            delivery_slip = Invoice(database=database, order=order, invoice_number=deliver_slip_number,invoice_class="delivery-slip", invoice_date=new_order_desp_date)
            db.session.add(delivery_slip)
            db.session.commit()

            delivery_batch.invoice = delivery_slip
            db.session.commit()
            #delivery_slip.invoice_html = jsonify(uri=invoice_config_dict["delivery-slip"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=delivery_slip, DELIVERY_BATCH = delivery_batch)
            db.session.commit()
            return {"message" : delivery_slip.id }, 200
        
    else:
        if invoice_class== 'purchase-invoice':
            invoice_count = len(Invoice.query.filter_by(database=database, invoice_class="purchase-invoice").all()) + 1
            invoice_number = f"PURCHASE/{invoice_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="purchase-invoice", invoice_number= invoice_number).first()
            while number_check:
                invoice_count+=1
                invoice_number = f"PURCHASE/{invoice_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="purchase-invoice", invoice_number= invoice_number).first()
            sales_invoice = Invoice(database=database, order_id=order.id, invoice_number=invoice_number, invoice_class="purchase-invoice", invoice_date=new_order_desp_date)
            db.session.add(sales_invoice)
            db.session.commit()
            #sales_invoice.invoice_html= jsonify(uri=invoice_config_dict["purchase-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=sales_invoice)
            db.session.commit()
        elif invoice_class == 'purchase-order':
            prof_invoice_count = len(Invoice.query.filter_by(database=database, invoice_class="purchase-order").all()) + 1
            prof_invoice_number = f"PO/{prof_invoice_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="purchase-order", invoice_number= prof_invoice_number).first()
            while number_check:
                prof_invoice_count+=1
                prof_invoice_number = f"PO/{prof_invoice_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="purchase-order", invoice_number= prof_invoice_number).first()
            prof_invoice = Invoice(database=database, order=order, invoice_number=prof_invoice_number,invoice_class="purchase-order", invoice_date=new_order_desp_date)
            db.session.add(prof_invoice)
            db.session.commit()
            #prof_invoice.invoice_html= jsonify(uri=invoice_config_dict["purchase-order"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=prof_invoice)
            db.session.commit()
        elif invoice_class == 'receive-slip':
            delivery_batch_id = delivery_batch_ids[0]
            delivery_batch = DeliveryBatch.query.filter_by(database = database, id = delivery_batch_id).first()

            delivery_slip_count = len(Invoice.query.filter_by(database=database, invoice_class="receive-slip").all()) + 1
            deliver_slip_number = f"RECEIVING/{delivery_slip_count}"
            number_check = Invoice.query.filter_by(database=database, invoice_class="receive-slip", invoice_number= deliver_slip_number).first()
            while number_check:
                delivery_slip_count+=1
                deliver_slip_number = f"RECEIVING/{delivery_slip_count}"
                number_check = Invoice.query.filter_by(database=database, invoice_class="receive-slip", invoice_number= deliver_slip_number).first()
            delivery_slip = Invoice(database=database, order=order, invoice_number=deliver_slip_number,invoice_class="receive-slip", invoice_date=new_order_desp_date)
            db.session.add(delivery_slip)
            db.session.commit()
            delivery_batch.invoice = delivery_slip
            db.session.commit()
            #delivery_slip.invoice_html = jsonify(uri=invoice_config_dict["receive-slip"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=delivery_slip, DELIVERY_BATCH = delivery_batch)
            db.session.commit()
            

#----------------------------------------------------------------
            
class PurchaseOrders(Resource):
    @jwt_required()
    @requires_role(["PURCHASE"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        show_flag_param = data.get("show_flag")
        show_flag = [show_flag_param] if show_flag_param else ['Active', 'Pending']
        filters_list = data.get("filters[]",[])
        filter_type = data.get('filter_type')
        FILTER_CATEGORY_PAIRS = []
        for cat_id in filters_list:
            category = Category.query.filter_by(database=database, id=cat_id).first()
            FILTER_CATEGORY_PAIRS.append((int(cat_id), category.name))
        customer_id_list = []
        if filters_list and filter_type:
            try:
                # url = "/partners/search"
                # headers = {'Content-Type': 'application/json'}
                # body = {"k": -1, "filters": {"filter_type": filter_type, "filters_array": filters_list}}
                # body["session_data"] = session.get('BAD_SECRET_KEY')
                # try:
                #     process_data_response = requests.post(f'{current_app.config["API_BASE_URL_LOCAL"]}/{url}', json=body, cookies=request.cookies)
                # except:
                #     process_data_response = requests.post(f'{current_app.config["API_BASE_URL"]}/{url}', json=body, cookies=request.cookies)
                # response_json = process_data_response.json()
                # items_dict = response_json
                items_dict={"id":[]}
            except requests.ConnectionError:
                return {"message": "Connection Error"}, 500
            customers_df = pd.DataFrame(items_dict)
            customer_id_list = customers_df["id"].tolist()
        ORDERS_DATA = {}
        orders = Order.query.filter_by(database=database, order_type=1).all()
        for order in orders:
            if customer_id_list and order.customer.id not in customer_id_list:
                continue
            ORDERS_DATA[order.id] = {
                "order": order,
                "customer": Customer.query.filter_by(id=order.customer_id, database=database).first(),
                "items": [],
                "chart_items": []
            }
            order_items = OrderItem.query.filter_by(order_id=order.id, database=database).all()
            for order_item in order_items:
                ORDERS_DATA[order.id]["items"].append(order_item)
                ORDERS_DATA[order.id]["chart_items"].append([
                    order_item.id, order_item.item.name, 
                    order_item.order_qty, order_item.item.unit, 0, order_item.item.id
                ])
        
        categories = Category.query.filter_by(database=database, category_type=2).all()
        CATEGORIES = [[item.id, item.name] for item in categories]
        segment = get_segment(request)
        order_id_set = data.get('order_id_set')
        order_id_set_2 = data.get('order_id_set_2')
        if order_id_set_2:
            order_id_set = order_id_set_2
        order_info_html = ""
        if not order_id_set:
            order = Order.query.filter_by(database=database, order_type=1, status=show_flag[0]).first()
            if order:
                order_id_set = order.id
        # if order_id_set:
        #     url = url_for('orders_bp.order_info')  # Replace with your actual URL
        #     params = {'order_id': order_id_set}
        #     headers = {'Content-Type': 'application/json'}
        #     try:
        #         response = requests.post(f'{current_app.config["API_BASE_URL_LOCAL"]}/{url}', data=json.dumps(params), headers=headers, cookies=request.cookies)
        #     except:
        #         response = requests.post(f'{current_app.config["API_BASE_URL"]}/{url}', data=json.dumps(params), headers=headers, cookies=request.cookies)
        #     if response.status_code == 200:
        #         data = response.json()
        #         order_info_html = data['html']
        #     else:
        #         print(f"Failed to fetch data. Status code: {response.status_code}")
            order_id_set = int(order_id_set)
        customers = Customer.query.filter_by(database=database).all()
        CUSTOMERS = [[customer.id, customer.name] for customer in customers]
        items = Item.query.filter_by(database=database).all()
        ITEMS = [[item.id, item.name, item.rate, item.unit] for item in items]
        return {
            "orders_data": ORDERS_DATA,"items": ITEMS,"customers": CUSTOMERS,"show_flag": show_flag,"segment": segment,
            "today": date.today(),"order_info_html": order_info_html,"order_id_set": order_id_set,"categories": CATEGORIES}
    

class addneworder(Resource):
    @jwt_required()
    @requires_role(["PURCHASE"], 1)    
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        new_order_cust_id = data.get("new_order_cust_id")
        new_order_note = data.get("new_order_note")
        new_order_desp_date = data.get("new_order_desp_date")
        
        if new_order_desp_date and new_order_cust_id:
            customer = Customer.query.filter_by(id=new_order_cust_id, database=database).first()
            order = Order(customer=customer, database=database, note=new_order_note, despdate=new_order_desp_date, status="Pending", order_type=1)
            db.session.add(order)
            db.session.commit()
            order = Order.query.filter_by(database=database, id=order.id).first()
            create_invoices(database.id, order.id, 'purchase-order')
            referer_url = request.headers.get('Referer', '/')
            new_url = ammend_referer_url(referer_url, 'order_id_set', order.id)
            return {"message":"redirect","url":new_url}, 302
        
        return {"message": "Order creation failed"}, 400

    
class PurchaseOrderBreakupResource(Resource):
    @jwt_required()
    @requires_role(["PURCHASE"], 0)
    def post(self):
        try:
            current_user = get_jwt_identity()
            database = Data.query.filter_by(id = current_user["data"]).first()
            req_json = request.get_json()
            item_id = req_json.get("item_id", None)
            result = []
            if item_id:
                item = Item.query.filter_by(database=database, id=item_id).first()
                if item:
                    orders = Order.query.filter_by(database=database, status="Active", order_type=1).all()
                    for order in orders:
                        for order_item in order.orderitems:
                            if order_item.item.id == item.id:
                                result.append({
                                    "code": item.code,"name": item.name,"item_id": item.id,"order_item_id": order_item.id,"customer_name": order.customer.name,
                                    "dispatch_date": order.despdate,"note": order.note,"unit": order_item.item_unit,"order_qty": order_item.order_qty,"dispatch_qty": order_item.dispatch_qty})
            return jsonify(result), 200
        except Exception as e:
            return {"message": f"An error occurred: {e}"}, 500


def get_conversion_factor(database, item, unit_name):
    print(database.id, item.name, unit_name)
    if item.unit == unit_name:
        return 1
    item_unit = ItemUnit.query.filter_by(database=database, item = item, unit_name = unit_name).first()
    if item_unit:
        return item_unit.conversion_factor
    return 1


class ReceiveChallan(Resource):
    @jwt_required()
    @requires_role(["PURCHASE"], 0)
    def get(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        order_id = data.get("order_id")
        DATA = {"order_info": None, "order_items": None}
        if order_id:
            database = Data.query.filter_by(id=current_user["data"]).first()
            order = Order.query.filter_by(database=database, id=order_id).first()
            order_items = OrderItem.query.filter_by(database=database, order=order).all()
            DATA["order_info"] = order
            DATA["order_items"] = order_items
        
        inventory_stock_data = db.session.query(Inventory.item_id,Item.name,Item.unit,db.func.sum(Inventory.qty).label("total_quantity")
            ).join(
            Item, Inventory.item_id == Item.id).group_by(Inventory.item_id, Item.name, Item.unit).filter(Inventory.data_id == current_user["data"]).all()
        
        inventory_stock_df = pd.DataFrame(inventory_stock_data, columns=["item_id", "Item Name", "Item Unit", "total_stock"])
        inventory_dict = inventory_stock_df.set_index("item_id").to_dict(orient="index")
        
        return {"DATA": DATA,"TODAY": date.today(),"INVENTORY_DATA": inventory_dict}
    
    @jwt_required()
    @requires_role(["PURCHASE"], 0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        database = Data.query.filter_by(id=current_user["data"]).first()
        dispatch_flag = data.get("dispatch_flag")
        dispatch_order_id = data.get("dispatch_order_id")
        action = data.get("action")
        
        if dispatch_flag and dispatch_order_id and action:
            order = Order.query.filter_by(database=database, id=dispatch_order_id).first()
            if not order:
                return {'message':"order not found"}, 401
            if action == 'dispatch':
                order.status = "Dispatched"
                db.session.commit()
            # Getting Dispatch item ids and qtys
            order_item_ids = data.get("order_item_ids[]", [])
            desp_qtys = data.get("desp_qtys[]", [])
            desp_units = data.get("desp_units[]", [])
            
            for i in range(len(order_item_ids)):
                order_item_id = order_item_ids[i]
                edit_disp_qty = desp_qtys[i]
                order_item = OrderItem.query.filter_by(database=database, id=order_item_id).first()
                conversion_factor = get_conversion_factor(database, order_item.item, desp_units[i])
                edit_disp_qty = float(edit_disp_qty) / conversion_factor
                order_item.dispatch_qty = edit_disp_qty
                db.session.commit()
                
                if action == 'dispatch':
                    inventory = Inventory.query.filter_by(id=order_item.inventory_ledger_id, database=database).first()
                    inventory.qty = float(edit_disp_qty)
                    inventory.note = f"purchaseReceipt_{order.customer.name}_{date.today()}"
                    inventory.regdate = order.actual_desp_date
                    db.session.commit()
            numbers_list = []
            try:
                numbers_list = get_mobile_numbers(current_user["data"])
            except:
                print("number not found")
            user = User.query.filter_by(id=current_user["user_id"]).first()
            res = []
            if action == "save":
                for number in numbers_list:
                    try:
                        SEND_CUSTOM_MESSAGE(f"Items saved for receiving of purchase order, {order.customer.name} by {user.name}!", number)
                    except:
                        continue
                return {"message":f"Items saved for receiving of purchase order, {order.customer.name} by {user.name}!"}, 200
            for number in numbers_list:
                try:
                    SEND_CUSTOM_MESSAGE(f"Items Received of purchase order, {order.customer.name} by {user.name}!", number)
                except:
                    continue
            #return redirect("/purchase?show_flag=Dispatched", code=302)
            return {"message":"redirect to purchase", "show_flag": "Dispatched"}, 302
        return {"message": "Invalid request"}, 400