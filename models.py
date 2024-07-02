from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
# class Person(db.Model):
#     __tablename__ = 'person'
#     pid = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.Text, nullable=False)
#     age = db.Column(db.Integer)
#     job = db.Column(db.Text)
#     gameplayer = db.Column(db.Text, nullable=False)
    
#     def __repr__(self):
#         return f'Person {self.name} {self.age} {self.job} {self.gameplayer}' 
db = SQLAlchemy()

class Conversation(db.Model):
    __bind_key__ = 'chatappdb'
    __tablename__ = 'conversation'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    message = db.Column(db.JSON, nullable=False)
    sendby = db.Column(db.Integer, nullable=False)
    msgtime = db.Column(db.DateTime, nullable=False, default=datetime.now())

class Ticket(db.Model):
    __bind_key__ = 'chatappdb'
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.now())
    creater_id = db.Column(db.Integer, nullable=False)
    description = db.Column(db.JSON, nullable=False)
    type = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=False)

class TicketUserMapping(db.Model):
    __bind_key__ = 'chatappdb'
    __tablename__ = 'ticketusermapping'
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    dateadded = db.Column(db.DateTime, nullable=False, default=datetime.now())

class Subscription(db.Model):
    __tablename__='subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    plan_code = db.Column(db.String(64), default="001")
    plan_name = db.Column(db.String(64), default="SILVER")
    primary_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    regdate = db.Column(db.Date, default=date.today())
    duration = db.Column(db.Float, default=14)
    max_user = db.Column(db.Float, default=5)
    max_sku = db.Column(db.Float, default=500)
    max_data = db.Column(db.Float, default=3)
    status = db.Column(db.String(64), default="Active")
 
    subdatamappings = db.relationship('SubDataMapping', backref='subscription')

class SubDataMapping(db.Model):
    __tablename__ = 'subdatamappings'
    id = db.Column(db.Integer, primary_key=True)
    sub_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class Data(db.Model):
    __tablename__='datas'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    key = db.Column(db.String(64), unique=True)
    regdate = db.Column(db.Date, default=date.today())
    status = db.Column(db.String(64), default="Active")
    
    subdatamappings = db.relationship('SubDataMapping', backref='database')
    userdatamappings = db.relationship('UserDataMapping', backref='database')
    invoices = db.relationship("Invoice", backref="database")
    zoho_info = db.relationship("ZohoInfo", backref='database', uselist=False)
    company = db.relationship("Company", backref='database', uselist=False)
    users = db.relationship("User" , backref='database')
    labors = db.relationship("Labor" , backref='database')
    items = db.relationship("Item" , backref='database')
    itemmastermappings = db.relationship("ItemMasterMapping" , backref='database')
    customermastermappings = db.relationship("CustomerMasterMapping" , backref='database')
    categories = db.relationship("Category" , backref='database')
    itemboms = db.relationship('ItemBOM', backref="database")
    boms = db.relationship('BOM', backref='database')
    itemcategories = db.relationship('ItemCategory', backref='database')
    prodcharts = db.relationship("Prodchart" , backref='database')
    prodchartitems = db.relationship('ProdchartItem', backref='database')
    joballots =  db.relationship("Joballot" , backref='database')
    orders = db.relationship('Order', backref = 'database')
    orderitems = db.relationship('OrderItem', backref='database')
    customers = db.relationship('Customer', backref='database')
    inventories = db.relationship('Inventory', backref='database')
    units = db.relationship('Unit', backref='database')
    unitmappings = db.relationship('UnitMapping', backref='database')
    itemunits = db.relationship('ItemUnit', backref='database')
    workstations = db.relationship('Workstation', backref='database')
    workstationjobs = db.relationship('WorkstationJob', backref='database')
    workstationresources = db.relationship('WorkstationResource', backref='database')
    workstationmappings = db.relationship('WorkstationMapping', backref='database')
    wsprodchartitemmappings = db.relationship('WSJobsProdChartItemMapping', backref='database')
    wsmaterialissues = db.relationship('WSMaterialIssue', backref='database')
    bgprocesses = db.relationship('BGProcess', backref='database')
    itemfinances = db.relationship('ItemFinance', backref='database')
    iteminventories = db.relationship('ItemInventory', backref='database')
    mobilenumbers = db.relationship('MobileNumber', backref='database')
    workstationpreference = db.relationship('WorkstationPreference', backref='database')
    bottasks = db.relationship('BotTasks', backref="database")
    orderitemfinance = db.relationship('OrderItemFinance', backref='database')
    itemcustomfields = db.relationship("ItemCustomField" , backref='database')
    dataconfigs = db.relationship("DataConfiguration" , backref='database')

    resourcecategories = db.relationship('ResourceCategory', backref='database')
    partnercategories = db.relationship('PartnerCategory', backref='database')

    orderitemdispatch = db.relationship('OrderItemDispatch', backref='database')
    deliverybatches = db.relationship('DeliveryBatch', backref='database')
    
class DataConfiguration(db.Model):
    __tablename__ = 'dataconfigurations'
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    item_master_config = db.Column(db.Text, default="BASIC")
    invoice_config = db.Column(db.Text, default="{}")
    
#google drive

class Company(db.Model):
    __tablename__="company"
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    name = db.Column(db.String(128), default="")
    billing_address = db.Column(db.Text, default="")
    shipping_address = db.Column(db.Text, default="")
    gst = db.Column(db.String(16), default="")
    email = db.Column(db.String(64), default='')
    phone = db.Column(db.String(16), default='')
    regdate = db.Column(db.Date, default=date.today())


class ZohoInfo(db.Model):
    __tablename__="zohoinfos"
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    organization_id = db.Column(db.String(16))
    client_id = db.Column(db.Text)
    client_secret = db.Column(db.Text)
    refresh_token = db.Column(db.Text, default="null")
    access_token = db.Column(db.Text, default="null")
    access_code = db.Column(db.Text, default="null")

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    email = db.Column(db.String(64), unique=True)
    password = db.Column(db.String(512))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    access_role = db.Column(db.String(64), default="PENDING")
    operation_role = db.Column(db.Text, default="BASIC")
    regdate = db.Column(db.Date, default=date.today())
    token = db.Column(db.String(512),default = 'NAN')
    subscriptions = db.relationship('Subscription', backref='user')
    mobilenumbers = db.relationship('MobileNumber', backref='user')
    userdatamappings = db.relationship('UserDataMapping', backref='user')

class UserDataMapping(db.Model):
    __tablename__ = 'userdatamappings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    access_role = db.Column(db.String(64), default="BASIC")
    operation_role = db.Column(db.Text, default="BASIC")
    

class Labor(db.Model):
    __tablename__ = 'labors'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String, default="NA")
    name = db.Column(db.String(64))
    gender = db.Column(db.String(64), default="WORKER")
    salary = db.Column(db.Float, default=0)
    status = db.Column(db.String(64), default="Active")
    regdate = db.Column(db.Date, default=date.today())
    contract_mode = db.Column(db.String(64), default='PAYROLL')
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

    resourcecategories = db.relationship('ResourceCategory', backref='labor')
    joballots = db.relationship('Joballot', backref='labor')
    workstationresources = db.relationship('WorkstationResource', backref='labor')

class Item(db.Model):
    __tablename__='items'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String, default="NA")
    name = db.Column(db.Text, default = "ITEM_NAME")
    unit = db.Column(db.String(20))
    rate = db.Column(db.Float, default=0)
    regdate = db.Column(db.Date, default=date.today())
    raw_flag = db.Column(db.String, default="YES") ## Yes if no bill of material
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))  

    itemcustomfields = db.relationship("ItemCustomField" , backref='item')
    itemmastermapping = db.relationship("ItemMasterMapping" , backref='item', uselist=False)
    itemfinance = db.relationship('ItemFinance', backref='item', uselist=False)
    iteminventory = db.relationship('ItemInventory', backref='item', uselist=False)
    boms = db.relationship('ItemBOM', backref="item")
    parent_boms = db.relationship('BOM', foreign_keys = "BOM.parent_item_id", backref="parent_item")
    child_boms = db.relationship('BOM', foreign_keys = "BOM.child_item_id", backref="child_item")
    itemcategories = db.relationship('ItemCategory', backref='item')
    joballots = db.relationship('Joballot', backref='item')
    prodchartitems = db.relationship('ProdchartItem', backref='item')
    orderitems = db.relationship('OrderItem', backref='item')
    inventories = db.relationship('Inventory', backref='item')
    itemunits = db.relationship('ItemUnit', backref='item')
    workstationjobs = db.relationship('WorkstationJob', backref='item')
    wsmaterialissues = db.relationship('WSMaterialIssue', backref='item')

class ItemCustomField(db.Model):
    __tablename__ = 'itemcustomfields'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    field_name = db.Column(db.String(64), default="FIELD")
    field_value = db.Column(db.Text, default="NULL")
    
class ItemFinance(db.Model):
    __tablename__="itemfinances"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    cost_price = db.Column(db.Float, default=0)
    sale_price = db.Column(db.Float, default=0)
    tax = db.Column(db.Float, default=0)
    hsn_code = db.Column(db.String(10), default="000000")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class ItemInventory(db.Model):
    __tablename__="iteminventories"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    consumption_mode = db.Column(db.String(10), default="AUTO")
    min_level = db.Column(db.Float, default=0)
    max_level = db.Column(db.Float, default=10000000)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class ItemMasterMapping(db.Model):
    __tablename__="itemmastermappings"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    foreign_item_id = db.Column(db.String(64))
    foreign_type = db.Column(db.String(32), default="zoho")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id')) 

class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    category_type = db.Column(db.Integer, default=0)

    itemcategories = db.relationship('ItemCategory', backref='category')
    resourcecategories = db.relationship('ResourceCategory', backref='category')
    partnercategories = db.relationship('PartnerCategory', backref='category')

class ItemBOM(db.Model):
    __tablename__ = 'itemboms'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    bom_name = db.Column(db.String(64))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class BOM(db.Model):
    __tablename__ = 'boms'
    id = db.Column(db.Integer, primary_key=True)
    parent_item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    child_item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    child_item_qty = db.Column(db.Float, default=0)
    child_item_unit = db.Column(db.String(20))
    margin = db.Column(db.Float, default=0.0) ## Percentage of margin or wastage
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class ItemCategory(db.Model):
    __tablename__ = 'itemcategories'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class ResourceCategory(db.Model):
    __tablename__ = 'resourcecategories'
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('labors.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class PartnerCategory(db.Model):
    __tablename__ = 'partnercategories'
    id = db.Column(db.Integer, primary_key=True)
    partner_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class Prodchart(db.Model):
    __tablename__ = 'prodcharts'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, default=date.today())
    note = db.Column(db.Text, default="")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    status = db.Column(db.Text, default="ACTIVE")

    prodchartitems = db.relationship('ProdchartItem', backref='prodchart')

class ProdchartItem(db.Model):
    __tablename__ = 'prodchartitems'
    id = db.Column(db.Integer, primary_key=True)
    chart_id = db.Column(db.Integer, db.ForeignKey('prodcharts.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    item_unit = db.Column(db.String(64))
    item_rate = db.Column(db.Float)
    qty_allot = db.Column(db.Float)
    qty_recv = db.Column(db.Float, default=0)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

    wsprodchartitemmappings = db.relationship('WSJobsProdChartItemMapping', backref='prodchartitem')
class Joballot(db.Model):
    __tablename__='joballots'
    id = db.Column(db.Integer, primary_key=True)
    labor_id = db.Column(db.Integer, db.ForeignKey('labors.id'))
    labor_salary = db.Column(db.Float)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    item_unit = db.Column(db.String(64))
    item_rate = db.Column(db.Float)
    qty_allot = db.Column(db.Float)
    qty_recv = db.Column(db.Float, default=0)
    status = db.Column(db.String(64), default="Active")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    date = db.Column(db.Date, default=date.today())
    inventory_ledger_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))


class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    regdate = db.Column(db.Date, default=date.today())
    despdate = db.Column(db.Date, default=date.today())
    status = db.Column(db.String(20), default="Active")
    note = db.Column(db.Text)
    order_type = db.Column(db.Integer, default=0)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

    active_date=db.Column(db.Date, default=date.today())
    actual_desp_date=db.Column(db.Date, default=date.today())

    orderitems = db.relationship('OrderItem', backref='order')
    invoice = db.relationship("Invoice", backref='order')
    deliverybatches = db.relationship('DeliveryBatch', backref='order')

class OrderItem(db.Model):
    __tablename__ = 'orderitems'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    item_unit = db.Column(db.String(64))
    order_qty = db.Column(db.Float)
    dispatch_qty = db.Column(db.Float, default = 0)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    inventory_ledger_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))

    orderitemfinance = db.relationship('OrderItemFinance', backref='orderItem', uselist=False)
    orderitemdispatch = db.relationship('OrderItemDispatch', backref='orderItem')

class OrderItemDispatch(db.Model):
    __tablename__ = 'orderitemdispatch'
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('orderitems.id'))
    dispatch_qty = db.Column(db.Float, default=0)
    delivery_batch_id =  db.Column(db.Integer, db.ForeignKey('deliverybatches.id'))
    inventory_ledger_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class DeliveryBatch(db.Model):
    __tablename__ = 'deliverybatches'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    batch_name = db.Column(db.String(128), default="BATCH-01")
    despdate = db.Column(db.Date, default=date.today())
    actual_desp_date = db.Column(db.Date, default=date.today())
    status = db.Column(db.String(20), default="STORE")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'))

    orderitemdispatch = db.relationship('OrderItemDispatch', backref='deliverybatch')
class OrderItemFinance(db.Model):
    __tablename__ = 'orderitemfinance'
    id = db.Column(db.Integer, primary_key=True)
    order_item_id = db.Column(db.Integer, db.ForeignKey('orderitems.id'))
    sale_price = db.Column(db.Float, default=0)
    discount_percentage = db.Column(db.Float, default=0)
    tax_percentage = db.Column(db.Float, default=0)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    invoice_number = db.Column(db.String(32), nullable=False)
    invoice_date=db.Column(db.Date, default=date.today())
    invoice_html=db.Column(db.Text, default="")
    invoice_type=db.Column(db.String(16), default="intra-state")
    invoice_class=db.Column(db.String(16), default="sales-invoice")
    invoice_amount = db.Column(db.Float, default=0)
    invoice_tax_amount = db.Column(db.Float, default=0)

    deliverybatch = db.relationship('DeliveryBatch', backref='invoice')

# class DataInvoice(db.Model):
#     __tablename__="datainvoice"
#     id = db.Column(db.Integer, primary_key=True)
#     data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
#     invoice_html=db.Column(db.Text, default="")
#     invoice_type=db.Column(db.String(16), default="intra-state")
#     invoice_class=db.Column(db.String(16), default="sales-invoice")

class Customer(db.Model):
    ## Stores both customers and vendors or any other business partners
    __tablename__ = 'customers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64))
    billing_address = db.Column(db.Text, default="")
    shipping_address = db.Column(db.Text, default="")
    gst = db.Column(db.String(16), default="")
    email = db.Column(db.String(64))
    phone = db.Column(db.String(16))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    regdate = db.Column(db.Date, default=date.today())

    lead_time = db.Column(db.Float, default=0)

    partnercategories = db.relationship('PartnerCategory', backref='customer')
    customermastermapping = db.relationship("CustomerMasterMapping" , backref='customer', uselist=False)
    orders = db.relationship('Order', backref='customer')

class CustomerMasterMapping(db.Model):
    __tablename__="customermastermappings"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    foreign_customer_id = db.Column(db.String(64))
    foreign_type = db.Column(db.String(32), default="zoho")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class Inventory(db.Model):
    __tablename__ = 'inventories'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    item_unit = db.Column(db.String(64))
    qty = db.Column(db.Float, default=0)
    note = db.Column(db.Text, default="")
    regdate = db.Column(db.DateTime, default=datetime.utcnow)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    status = db.Column(db.Text, default="ACTIVE")

    orderitems = db.relationship('OrderItem', backref='inventory')
    joballots = db.relationship('Joballot', backref='inventory')
    workstationjobs = db.relationship('WorkstationJob', foreign_keys = "WorkstationJob.inventory_id", backref='inventory')
    wipworkstationjobs = db.relationship('WorkstationJob', foreign_keys = "WorkstationJob.wip_inventory_id", backref='wipinventory')
    rejectworkstationjobs = db.relationship('WorkstationJob', foreign_keys = "WorkstationJob.reject_inventory_id", backref='rejectinventory')
    wsmaterialissues = db.relationship('WSMaterialIssue', foreign_keys = "WSMaterialIssue.inventory_id", backref='inventory')
    rejectwsmaterialissues = db.relationship('WSMaterialIssue', foreign_keys = "WSMaterialIssue.reject_inventory_id", backref='rejectinventory')
    orderitemdispatch = db.relationship('OrderItemDispatch', backref='inventory')
class Unit(db.Model):
    __tablename__ = 'units'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

    parent_units = db.relationship('UnitMapping', foreign_keys = "UnitMapping.parent_unit_id", backref="parent_unit")
    child_units = db.relationship('UnitMapping', foreign_keys = "UnitMapping.child_unit_id", backref="child_unit")


class UnitMapping(db.Model):
    __tablename__ = 'unitmappings'
    id = db.Column(db.Integer, primary_key=True)
    parent_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    child_unit_id = db.Column(db.Integer, db.ForeignKey('units.id'))
    conversion_factor = db.Column(db.Float, default=1)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class ItemUnit(db.Model):
    __tablename__ = 'itemunits'
    id = db.Column(db.Integer, primary_key = True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    unit_name = db.Column(db.String(16))
    conversion_factor = db.Column(db.Float)
    unit_type = db.Column(db.String(16), default="production")
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))


class Workstation(db.Model):
    __tablename__ = 'workstations'
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(64))
    primary_flag = db.Column(db.String(16))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    category_config = db.Column(db.Text, default='{}')
    
    workstationjobs = db.relationship('WorkstationJob', backref="workstation")
    workstationresources = db.relationship('WorkstationResource', backref="workstation")
    workstation_parents = db.relationship('WorkstationMapping',foreign_keys = "WorkstationMapping.parent_ws_id", backref="parent_ws")
    workstation_childs = db.relationship('WorkstationMapping', foreign_keys = "WorkstationMapping.child_ws_id", backref="child_ws")
    wsmaterialissues = db.relationship('WSMaterialIssue', backref="workstation")

class WorkstationMapping(db.Model):
    __tablename__ = "workstationmapping"
    id = db.Column(db.Integer, primary_key = True)
    parent_ws_id = db.Column(db.Integer, db.ForeignKey('workstations.id'))
    child_ws_id = db.Column(db.Integer, db.ForeignKey('workstations.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class WorkstationJob(db.Model):
    __tablename__ = 'workstationjobs'
    id = db.Column(db.Integer, primary_key = True)
    workstation_id = db.Column(db.Integer, db.ForeignKey('workstations.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    qty_allot = db.Column(db.Float)
    qty_recv = db.Column(db.Float, default=0)
    qty_wip = db.Column(db.Float, default = 0)
    qty_reject = db.Column(db.Float, default = 0)
    date_allot = db.Column(db.Date, default=date.today())
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    wip_inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    reject_inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    wsprodchartitemmappings = db.relationship('WSJobsProdChartItemMapping', backref="workstationjob")

class WorkstationResource(db.Model):
    __tablename__ = 'workstationresources'
    id = db.Column(db.Integer, primary_key = True)
    workstation_id = db.Column(db.Integer, db.ForeignKey('workstations.id'))
    resource_id = db.Column(db.Integer, db.ForeignKey('labors.id'))
    time_allot = db.Column(db.Float)
    time_lost = db.Column(db.Float, default=0)
    date_allot = db.Column(db.Date, default=date.today())
    contract_mode = db.Column(db.String(64), default='PAYROLL')
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class WSJobsProdChartItemMapping(db.Model):
    __tablename__="wsprodchartitemmappings"
    id = db.Column(db.Integer, primary_key = True)
    workstationjob_id = db.Column(db.Integer, db.ForeignKey('workstationjobs.id'))
    prodchartitem_id = db.Column(db.Integer, db.ForeignKey('prodchartitems.id'))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class WSMaterialIssue(db.Model):
    __tablename__="wsmaterialissues"
    id = db.Column(db.Integer, primary_key = True)
    workstation_id = db.Column(db.Integer, db.ForeignKey('workstations.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    item_unit = db.Column(db.String(64))
    issue_qty = db.Column(db.Float, default=0)
    return_qty = db.Column(db.Float, default=0)
    reject_qty = db.Column(db.Float, default=0)
    date_issue = db.Column(db.Date, default=date.today())
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    reject_inventory_id = db.Column(db.Integer, db.ForeignKey('inventories.id'))
    wip_flag = db.Column(db.String, default="NO")
    
class WorkstationPreference(db.Model):
    __tablename__="workstationpreferences"
    id = db.Column(db.Integer, primary_key=True)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    workstation_config = db.Column(db.Text, default="{}")
    # category_config = db.Column(db.Text, default='{}')
    
class BGProcess(db.Model):
    __tablename__ = "bgprocesses"
    id = db.Column(db.Integer, primary_key = True)
    process_id = db.Column(db.Text)
    name = db.Column(db.String(64))
    status = db.Column(db.String(64), default="Active")
    note = db.Column(db.Text, default="")
    datetime = db.Column(db.DateTime, default=datetime.utcnow)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

class MobileNumber(db.Model):
    __tablename__= "mobilenumbers"
    id = db.Column(db.Integer, primary_key = True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    mobile_number = db.Column(db.String(12))
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))

    bottasks = db.relationship('BotTasks', backref="mobilenumber")
    
class BotTasks(db.Model):
    __tablename__="bottasks"
    id = db.Column(db.Integer, primary_key = True)
    data_id = db.Column(db.Integer, db.ForeignKey('datas.id'))
    mobile_number_id = db.Column(db.Integer, db.ForeignKey('mobilenumbers.id'))
    context = db.Column(db.Text)
    status = db.Column(db.Text, default="READY")

class BotLogs(db.Model):
    __tablename__="botlogs"
    id = db.Column(db.Integer, primary_key = True)
    mobile_number = db.Column(db.String(12))
    log = db.Column(db.Text, default="{}")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
