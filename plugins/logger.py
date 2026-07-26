# plugins/logger.py
import os
from datetime import datetime

PLUGIN_NAME = "Activity Logger"

def execute(item: dict):
    log_path = os.path.join(os.path.dirname(__file__), "../inventory_audit.log")
    timestamp = datetime.now().isoformat()
    log_message = f"[Log Record] {timestamp} - Item: {item['name']} (ID: {item['id']}) stock is now {item['quantity']}\n"
    
    with open(log_path, "a") as f:
        f.write(log_message)