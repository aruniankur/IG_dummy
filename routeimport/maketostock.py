from models import db , Item, ItemInventory, Inventory, BOM
import pandas as pd

def mt_stock(data_id):
    joined_data = pd.DataFrame(db.session.query(ItemInventory.item_id, ItemInventory.consumption_mode,ItemInventory.min_level,ItemInventory.max_level).filter(ItemInventory.data_id == data_id).all())
    joined_data = joined_data[['item_id','consumption_mode','min_level','max_level']]
    Item_data = pd.DataFrame(db.session.query(Item.id, Item.name, Item.unit, Item.raw_flag, Item.code, Item.rate).filter(Item.data_id == data_id).all())
    Item_data = Item_data.rename(columns={'id':'item_id'})
    joined_data = pd.merge(joined_data, Item_data, how='right', on='item_id')
    joined_data['consumption_mode'].fillna('AUTO', inplace=True)
    joined_data['min_level'].fillna(0, inplace=True)
    joined_data['max_level'].fillna(10000000, inplace=True)
    unique_item_id = joined_data['item_id'].tolist()
    inventory_stock_data = db.session.query(
            Inventory.item_id,db.func.sum(Inventory.qty).label("total_quantity")
        ).group_by(Inventory.item_id).filter(Inventory.item_id.in_(unique_item_id),Inventory.status=='ACTIVE',Inventory.data_id == data_id).all()
    df_inventory_stock = pd.DataFrame(inventory_stock_data,columns=['item_id','stock'])
    inventory_stock_data = db.session.query(Inventory.item_id,db.func.sum(Inventory.qty).label("total_quantity")
        ).group_by(Inventory.item_id).filter(Inventory.item_id.in_(unique_item_id),Inventory.status=='WIP',Inventory.data_id == data_id).all()
    df_inventory_stock_wip = pd.DataFrame(inventory_stock_data,columns=['item_id','wip_stock'])
    merged_df = pd.merge(joined_data, df_inventory_stock, how='left', on='item_id')
    merged_df = pd.merge(merged_df, df_inventory_stock_wip, how='left', on='item_id')
    merged_df['stock'].fillna(0, inplace=True)
    merged_df['adv_stock'] = merged_df['stock'].clip(0)
    merged_df['wip_stock'].fillna(0, inplace=True)
    merged_df['demand'] = merged_df['min_level'] - merged_df['adv_stock']
    return merged_df



def max_psbl_amount(data_id,item_id_lst):
    bom_items = db.session.query(BOM.id,BOM.parent_item_id,BOM.child_item_id,BOM.child_item_qty,BOM.child_item_unit,BOM.margin).filter(BOM.parent_item_id.in_(item_id_lst),BOM.data_id == data_id).all()
    df_BOM = pd.DataFrame(bom_items, columns=['id', 'parent_item_id', 'child_item_id', 'child_item_qty','child_item_unit','margin'])
    child_item_list = df_BOM['child_item_id'].unique().tolist()
    inventory_stock_data = db.session.query(
            Inventory.item_id,
            db.func.sum(Inventory.qty).label("total_quantity")
        ).group_by(Inventory.item_id)\
        .filter(Inventory.item_id.in_(child_item_list),Inventory.data_id == data_id).all()
    df_child_inventory = pd.DataFrame(inventory_stock_data,columns=['child_item_id','total_stock'])
    df_child_inventory = df_child_inventory[['child_item_id','total_stock']]
    df_BOM_inventory = pd.merge(left=df_BOM, right=df_child_inventory, how='left', on='child_item_id')
    df_BOM_inventory.fillna(0, inplace=True)
    df_BOM_inventory['max_psbl_production'] = df_BOM_inventory['total_stock']/((1+(0.01*df_BOM_inventory['margin']))*df_BOM_inventory['child_item_qty'])
    min_total_stock_df = df_BOM_inventory.groupby('parent_item_id')['max_psbl_production'].min().reset_index()
    result_dict = min_total_stock_df.set_index('parent_item_id')['max_psbl_production'].to_dict()
    return result_dict