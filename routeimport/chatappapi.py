from models import Conversation, Ticket, TicketUserMapping

from flask_restful import Api, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, UserDataMapping
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask import Flask,jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from datetime import datetime

def getconversation(ticket_id, start, end):
    if start < 0 or end <= start:
        return {'error': 'Invalid range'}
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return {"error":"no ticket found"}, 404
    conversations = (Conversation.query
                     .filter_by(ticket_id=ticket_id)
                     .order_by(Conversation.msgtime)
                     .slice(start, end)
                     .all())

    result = [{'id': conv.id, 'ticket_id': conv.ticket_id, 'message': conv.message, 
               'sendby': conv.sendby, 'msgtime': conv.msgtime} for conv in conversations]

    return {'conversations': result}

def addtoconversation(ticket_id, text, googlefilecode, user_id):
    conversationjson = {"msg_text":text, "msg_media": googlefilecode}
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return {"error":"no ticket found"}, 404
    conv = Conversation(ticket_id = ticket.id, message = conversationjson, sendby = user_id)
    db.session.add(conv)
    db.session.commit()
    
# ticket user mapping 
class addusertoticket(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        userid = data.get('user_id')
        
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return jsonify({'error': 'Ticket not found'})
        
        user = User.query.get(userid)
        if not user:
            return jsonify({'error': 'User not found'})
        
        # Check if the mapping already exists
        existing_mapping = TicketUserMapping.query.filter_by(ticket_id=ticket_id, user_id=userid).first()
        if existing_mapping:
            return jsonify({'message': 'Mapping already exists'})
        
        ticketmap = TicketUserMapping(ticket_id=ticket.id, user_id=userid)
        try:
            db.session.add(ticketmap)
            db.session.commit()
            return jsonify({'message': f'User added to ticket {ticket.name} successfully'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)})

        

class getallticketusermapping(Resource):
    @jwt_required()
    def get(self):
        ticket = TicketUserMapping.query.all()
        return jsonify([{'id': i.id,
                         'ticket_id': i.ticket_id,
                         'user.id': i.user_id,
                         'dateadded': str(i.dateadded)} for i in ticket])
    
class remove_user_from_ticket(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        ticket_id = data.get('ticket_id')
        user_id = data.get('user_id')
        ticket_user_mapping = TicketUserMapping.query.filter_by(ticket_id=ticket_id, user_id=user_id).first()
        if not ticket_user_mapping:
            return jsonify({'error': 'Mapping not found'}), 404
        ticket = Ticket.query.get(ticket_id)
        if ticket.creater_id == user_id:
            return jsonify({'error': 'Mapping found. cannot delete the creator'}), 404
        try:
            db.session.delete(ticket_user_mapping)
            db.session.commit()
            return jsonify({'message': f'User removed from ticket successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
class getallticketforuser(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        tickets = Ticket.query.join(TicketUserMapping).filter(TicketUserMapping.user_id == current_user['user_id']).all()
        result = [
            {
                "id": ticket.id,
                "name": ticket.name,
                "date_created": ticket.date_created,
                "creater_id": ticket.creater_id,
                "description": ticket.description,
                "type": ticket.type,
                "status": ticket.status
            } for ticket in tickets
        ]
        return jsonify(result)

class get_conversations_for_ticket(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        ticket_id = data.get('ticketid')
        start_time = datetime.fromisoformat(start_time) if start_time else datetime.min
        end_time = datetime.fromisoformat(end_time) if end_time else datetime.max
        conversations = Conversation.query.filter(
            Conversation.ticket_id == ticket_id,
            Conversation.msgtime.between(start_time, end_time)
        ).all()

        result = [
            {
                "id": conversation.id,
                "ticket_id": conversation.ticket_id,
                "message": conversation.message,
                "sendby": conversation.sendby,
                "msgtime": conversation.msgtime
            } for conversation in conversations
        ]
        return jsonify(result)
    
class get_user_mappings_for_ticket(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        ticket_id = data.get('ticketid')
        mappings = TicketUserMapping.query.filter(TicketUserMapping.ticket_id == ticket_id).all()
        result = [
            {
                "id": mapping.id,
                "ticket_id": mapping.ticket_id,
                "user_id": mapping.user_id,
                "dateadded": mapping.dateadded
            } for mapping in mappings
        ]
        return jsonify(result)
        
#----------------------------------------------------------------

class entrytoticket(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        user_id = current_user['user_id']
        ticket_id = data.get('ticket_id', None)
        if not ticket_id or not user_id:
            return jsonify({"error": "ticket_id and user_id are required"})
        mapping_exists = TicketUserMapping.query.filter_by(ticket_id=ticket_id, user_id=user_id).first() is not None
        return jsonify({"exists": True})
    


class addticket(Resource):
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        data = request.get_json()
        name = data.get('name')
        creater_id = current_user['user_id']
        description = data.get('description')
        type = data.get('type')
        status = data.get('status')
        usere  = User.query.get(creater_id)
        if not usere:
            return {"error": "user not found"}, 400
        if not all([name, creater_id, description, type, status]):
            return jsonify({'error': 'Missing data'})
        tickete = Ticket.query.filter_by(name=name).first()
        if tickete:
            return {"error":f"ticket already exists at ticket id : {tickete.id}"}, 400
        new_ticket = Ticket( name=name,creater_id=creater_id,description=description,type=type,status=status)
        try:
            db.session.add(new_ticket)
            db.session.commit()
            ticketmap = TicketUserMapping(ticket_id = new_ticket.id, user_id = creater_id)
            db.session.add(ticketmap)
            db.session.commit()
            return jsonify({'message': 'Ticket created successfully', 'ticket_id': new_ticket.id})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)})
    
    
class editticket(Resource):
    @jwt_required()
    def post(self):
        data = request.get_json()
        ticketid = data.get('ticket_id')
        name = data.get('name')
        creater_id = data.get('creater_id')
        description = data.get('description')
        type = data.get('type')
        status = data.get('status')
        ticket = Ticket.query.get(ticketid)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        if not all([name, creater_id, description, type, status]):
            return jsonify({'error': 'Missing data'}), 400
        ticket.name = name
        ticket.creater_id = creater_id
        ticket.description = description
        ticket.type = type
        ticket.status = status
        try:
            db.session.commit()
            return jsonify({'message': 'Ticket updated successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500


class deleteticket(Resource):
    @jwt_required()
    def post(self,ticket_id):
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404
        try:
            db.session.delete(ticket)
            db.session.commit()
            return jsonify({'message': 'Ticket deleted successfully'}), 200
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
class getallticket(Resource):
    @jwt_required()
    def get(self):
        ticket = Ticket.query.all()
        return jsonify([{'id': i.id,
                         'name':i.name,
                         'date_created':str(i.date_created),
                         'creater_id':i.creater_id,
                         'description':i.description,
                         'type':i.type,
                         'status':i.status} for i in ticket])
    

class getalluser(Resource):
    @jwt_required()
    def get(self):
        users = User.query.all()
        return jsonify([{
            'id': user.id,
            'mainuser': user.email,
            'name': user.name,
            'googlekey': user.access_role,
            'folderid': user.token
        } for user in users])