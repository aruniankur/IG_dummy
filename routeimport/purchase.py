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
from models import OrderItemDispatch, DeliveryBatch
from flask import request


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
            sales_invoice.invoice_html= render_template(invoice_config_dict["sales-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=sales_invoice, tax_exclusive_price_flag="NO", intra_state_gst_flag ="YES",
                delivery_batches= delivery_batches, delivery_batches_id_string=delivery_batches_id_string, proforma_invoice=proforma_invoice)
            db.session.commit()
            return sales_invoice.id
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
            prof_invoice.invoice_html= render_template(invoice_config_dict["proforma-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=prof_invoice, tax_exclusive_price_flag="NO", intra_state_gst_flag ="YES")
            db.session.commit()
            return prof_invoice.id
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
            delivery_slip.invoice_html = render_template(invoice_config_dict["delivery-slip"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=delivery_slip, DELIVERY_BATCH = delivery_batch)
            db.session.commit()
            return delivery_slip.id
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
            sales_invoice.invoice_html= render_template(invoice_config_dict["purchase-invoice"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=sales_invoice)
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
            prof_invoice.invoice_html= render_template(invoice_config_dict["purchase-order"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=prof_invoice)
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
            delivery_slip.invoice_html = render_template(invoice_config_dict["receive-slip"]["invoice-file"], ORDER = order, ORDER_ITEMS=[], invoice=delivery_slip, DELIVERY_BATCH = delivery_batch)
            db.session.commit()
            

def get_segment(request, id1):
    try:
        database = Data.query.filter_by(id=id1).first()
        segment = request.path.split('/')
        if segment == '':
            segment = 'index'
        print(database.company.name)
        return segment+[database.company.name]
    except:
        return None

def createjson(dbt):
    def convert_to_dict(instance):
        if instance is None:
            return {}
        result = {}
        for key, value in instance.__dict__.items():
            if key.startswith('_'):
                continue
            if isinstance(value, (datetime.date, datetime.datetime)):
                result[key] = value.isoformat()
            elif isinstance(value, list):
                result[key] = [convert_to_dict(item) if hasattr(item, '__dict__') else item for item in value]
            elif hasattr(value, '__dict__'):  # Check if value is a SQLAlchemy model instance
                result[key] = convert_to_dict(value)
            else:
                result[key] = value
        return result
    if isinstance(dbt, list):
        return [convert_to_dict(item) for item in dbt]
    else:
        return convert_to_dict(dbt)

#----------------------------------------------------------------
            
class getorders(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id = current_user["data"]).first()
        show_flag=['Active', 'Pending']
        customers = Customer.query.filter_by(database=database).all()
        CUSTOMERS = []
        for customer in customers:
            CUSTOMERS.append([customer.id, customer.name])
        items=Item.query.filter_by(database=database).all()
        ITEMS=[]
        for item in items:
            ITEMS.append([item.id, item.name, item.rate, item.unit])
        ORDERS_DATA={}
        orders = Order.query.filter_by(database=database, order_type=0).all()
        for order in orders:
            ORDERS_DATA[order.id]={}
            ORDERS_DATA[order.id]["order"]=order
            customer=Customer.query.filter_by(id=order.customer_id, database=database).first()
            ORDERS_DATA[order.id]["customer"]=customer
            ORDERS_DATA[order.id]["items"]=[]
            ORDERS_DATA[order.id]["chart_items"]=[]
            ORDERS_DATA[order.id]["invoices"] = {invoice.invoice_class: invoice for invoice in order.invoice }
            order_items = OrderItem.query.filter_by(order_id=order.id, database=database).all()
            for order_item in order_items:
                ORDERS_DATA[order.id]["items"].append(order_item)
                ORDERS_DATA[order.id]["chart_items"].append([order_item.id, order_item.item.name, order_item.order_qty, order_item.item.unit, 0, order_item.item.id])
                
        categories = Category.query.filter_by(database=database, category_type = 2).all()
        CATEGORIES=[]
        for item in categories:
            CATEGORIES.append([item.id, item.name])
        segment = get_segment(request,current_user["data"])
        order_id_set = ""
        order = Order.query.filter_by(database=database, order_type = 0, status = show_flag[0]).first()
        if order:
            order_id_set = order.id
        return {"orderdata": ORDERS_DATA, "orderid": order_id_set, "items": ITEMS, "customers": CUSTOMERS, "show_flag": show_flag ,"segment":segment, "Today": datetime.date.today(), "order_info_html": order_info_html, "category":CATEGORIES}, 200