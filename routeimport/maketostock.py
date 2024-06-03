from models import db , Item, ItemInventory, Inventory
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