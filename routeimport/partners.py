from flask_restful import Api, Resource
from routeimport.decorators import requires_role, get_segment, createjson, get_conversion_factor
from flask_jwt_extended import jwt_required, get_jwt_identity
from fuzzywuzzy import fuzz
from models import Labor, Data, Customer, BGProcess,Item, Category, PartnerCategory ,db
from flask import Flask,jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from sqlalchemy.orm import joinedload
from sqlalchemy import and_
# class addrecord(Resource):
#     @jwt_required
#     def post(self):
#         current_user = get_jwt_identity()
#         data = request.get_json()
#segment = get_segment(request, current_user['data'])


def compare_strings(s1, s2):
    if s1 in s2:
        score=100
    elif s2 in s1:
        score=100
    else:
        score= fuzz.token_sort_ratio(s1, s2)
    return score

class newPartner(Resource):
    @jwt_required()
    @requires_role(["MASTERS"],1)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        p_name =data.get("p_name")
        p_billing_address =data.get("p_billing_address")
        p_shipping_address =data.get("p_shipping_address")
        p_gst =data.get("p_gst")
        p_phone =data.get("p_phone")
        p_email =data.get("p_email")
        print(p_name)
        if p_name:
            p_billing_address = "" if not p_billing_address else p_billing_address
            p_shipping_address = "" if not p_shipping_address else p_shipping_address
            p_gst = "" if not p_gst else p_gst
            p_phone = "" if not p_phone else p_phone
            p_email = "" if not p_email else p_email
            database = Data.query.filter_by(id=current_user["data"]).first()
            customer = Customer(name=p_name,email=p_email,phone=p_phone,shipping_address = p_shipping_address, billing_address=p_billing_address,
            database=database, gst = p_gst)
            db.session.add(customer)
            db.session.commit()
            return redirect("/partners", code=302)
        return render_template("orders/newcustomer.html")

class newPartnerBulkUpload(Resource):
    @jwt_required()
    @requires_role(["MASTERS"],0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        
        

class partners(Resource):
    @jwt_required()
    @requires_role(["MASTERS"],0)
    def get(self):
        current_user = get_jwt_identity()
        CUSTOMERS=Customer.query.filter_by(data_id = current_user["data"]).all()
        segment = get_segment(request, current_user['data'])
        return {"customers":createjson(CUSTOMERS), "segment":segment}, 200
    
    @jwt_required()
    @requires_role(["MASTERS"],0)
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json() 
        database = Data.query.filter_by(id=current_user["data"]).first()
        edit_ids = data.get("edit_ids[]",[])
        edit_names = data.get("edit_names[]",[])
        shipping_addresses = data.get("shipping_addresses[]",[])
        billing_addresses = data.get("billing_addresses[]",[])
        edit_emails = data.get("edit_emails[]",[])
        edit_phones = data.get("edit_phones[]",[])
        edit_gsts = data.get("edit_gsts[]",[])
        res = []
        if len(edit_ids):
            for i in range(len(edit_ids)):
                pid ,name, ship, bill, email, phone, gst = edit_ids[i] ,edit_names[i], shipping_addresses[i], billing_addresses[i], edit_emails[i], edit_phones[i], edit_gsts[i]
                customer = Customer.query.filter_by(id=pid, database=database).first()
                if customer:
                    customer.name=name
                    customer.shipping_address=ship
                    customer.billing_address = bill
                    customer.email = email
                    customer.phone = phone
                    customer.gst = gst
                print(customer.shipping_address)
                res.append(f"edited customer. {customer.name} and id is : {customer.id}")
            db.session.commit()
            return {"Message":res}, 200
        return {"Message":"check input"}, 401
    


class partnersinfo(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def get(self, partner_id):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        PARTNER = Customer.query.filter_by(id = partner_id, database=database).first()
        categories = Category.query.filter_by(database=database, category_type = 2).all()
        CATEGORIES=[]
        for item in categories:
            CATEGORIES.append([item.id, item.name])
        return {"Partner": createjson(PARTNER), "Category": CATEGORIES}, 200
        
        
class addpartnercategory(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        add_category_item_id = data.get("add_category_item_id")
        add_category_id = data.get("add_category_id")
        if add_category_id and add_category_item_id:
            item = Customer.query.filter_by(database=database, id=add_category_item_id).first()
            category= Category.query.filter_by(database=database, id = add_category_id).first()
            item_cat = PartnerCategory.query.filter_by(database=database, customer=item, category=category).first()
            if item_cat:
                return {"Message":"Category already present in the partner","partner_id":item.id}, 200
            item_category = PartnerCategory(database=database, customer=item, category=category)
            print("Add:",item_category.category.name, item.name)
            db.session.add(item_category)
            db.session.commit()
            return {"message":"Added Category!", "partner_id":item.id}, 302
    
class deletepartnercategory(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        data = request.get_json()
        delete_category_item_id = data.get("delete_category_item_id")
        delete_category_id= data.get("delete_category_id")
        if delete_category_id and delete_category_item_id:
            category = Category.query.filter_by(database=database, id=delete_category_id).first()
            item = Customer.query.filter_by(database=database, id=delete_category_item_id).first()
            item_category = PartnerCategory.query.filter_by(database=database, customer=item, category=category).first()
            if item_category:
                db.session.delete(item_category)
                db.session.commit()
                return {"message":"Category Removed", "partner_id":item.id }, 302
    
    
class search_partner(Resource):
    @jwt_required()
    @requires_role(["MASTERS"], 0)
    def post(self):
        current_user = get_jwt_identity()
        database = Data.query.filter_by(id=current_user["data"]).first()
        req_json= request.get_json()
        k = int(req_json.get('k', 10)) 
        item_name =req_json.get('name',None)
        item_id = req_json.get('id',None)
        filters = req_json.get('filters', None)
        items=[]
        if filters:
            filters_list = filters["filters_array"]
            filter_type = filters["filter_type"]
            if filter_type == "inclusive":
                if item_name:
                    items = db.session.query(Customer).join(PartnerCategory).filter(
                        and_(
                            PartnerCategory.category_id.in_(filters_list),
                            Customer.name.ilike(f'%{item_name}%')
                        ),Customer.data_id == current_user["data"]).all()
                else:
                    items = db.session.query(Customer).join(PartnerCategory).filter(
                        PartnerCategory.category_id.in_(filters_list), Customer.data_id == current_user["data"]).all()
            else:
                cat_count = len(filters_list)
                items_filter = db.session.query(
                    Customer.id, db.func.count(PartnerCategory.id).label("category_count")).join(
                    Customer, PartnerCategory.partner_id == Customer.id).filter(
                    Customer.data_id == current_user["data"], PartnerCategory.category_id.in_(filters_list)).group_by(
                    Customer.id).all()
                filter_df =pd.DataFrame(items_filter, columns=["id", "cat_count"])
                filter_df = filter_df[filter_df["cat_count"] == cat_count]
                if item_name:
                    items = db.session.query(Customer).join(PartnerCategory).filter(
                        and_(
                            Customer.id.in_(filter_df["id"]),
                            Customer.name.ilike(f'%{item_name}%')
                        ),
                        Customer.data_id == current_user["data"]
                        ).all()
                else:
                    items = db.session.query(Customer).filter(
                        Customer.id.in_(filter_df["id"]), Customer.data_id == current_user["data"]).all()
        if item_name and not filters:
            # Perform the fuzzy search query and rank the top k matches
            items = (Customer.query.filter(Customer.data_id == current_user["data"]).all())
            item_scores = [(item, compare_strings(item_name.lower(), item.name.lower())) for item in items]
            item_scores.sort(key=lambda x: x[1], reverse=True)
            if k>0:
                top_k_matches = item_scores[:k]
            else:
                top_k_matches = item_scores
            items = [match[0] for match in top_k_matches]
        if item_id:
            items = Item.query.filter_by(id =item_id, data_id = current_user["data"]).all()
        results = [{'id': item.id,'name': item.name,} for item in items]
        return jsonify(results)
    
    