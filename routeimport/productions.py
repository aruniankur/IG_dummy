from flask import Flask,current_app, jsonify, render_template, request, redirect, session, send_from_directory, after_this_request, flash, Blueprint
from flask import current_app
from Production.models import Labor,User, Item, BOM, Customer, Category, Prodchart, Joballot, Order, Data, ProdchartItem, Inventory, OrderItem
from Production.models import Workstation, WorkstationMapping, WorkstationJob, WorkstationResource, WSJobsProdChartItemMapping, ItemBOM, OrderItemDispatch
from Production.models import DeliveryBatch
from Production.decorators import requires_role, get_segment
from Production.app import db
from datetime import datetime, date
from collections import OrderedDict
from operator import itemgetter
import pandas as pd
import requests
import json
from iteminfo import search_item
from Production.workstations.workstations import updateMaterialIssue, checkChildJobs
from Production.utility.productionFunctions.max_func import max_psbl_amount
from Production.productions.make_to_stock import mt_stock
from Production.utility.utility import get_mobile_numbers
from Production.bot.bot_utility import SEND_MESSAGE, SEND_CUSTOM_MESSAGE
from Production.workstations.workstations import get_job_totals

