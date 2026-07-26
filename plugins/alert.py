# plugins/alert.py
PLUGIN_NAME = "Low Stock Alert System"

def execute(item: dict):
    if item["quantity"] < 5:
        print(f"🚨 [ALERT PLUGIN] Warning! {item['name']} (SKU: {item['sku']}) has only {item['quantity']} left in inventory.")