import sqlite3
import os
import importlib.util
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Enable CORS
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

# Data SCHEMA
class ItemCreate(BaseModel):
	name: str
    brand_name: str
	product_type: str
	price: float
	quantity: int

def get_db():
    conn = sqlite3.connect("inventory.db")
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name like dicts
    return conn

# 3. INITIALIZE DATABASE TABLE
with get_db() as conn:
	cursor = conn.cursor()
	cursor.execute("""
		CREATE TABLE IF NOT EXISTS items (
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			name TEXT NOT NULL,
			description TEXT,
			price REAL NOT NULL,
			quantity INTEGER NOT NULL
		)
	""")
	conn.commit()


# ==========================================
# 4. DYNAMIC PLUGINS LOADER
# ==========================================
loaded_plugins = []

def load_plugins():
    plugins_dir = os.path.join(os.path.dirname(__file__), "plugins")
    if not os.path.exists(plugins_dir):
        return

    for filename in os.listdir(plugins_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            plugin_name = filename[:-3]
            file_path = os.path.join(plugins_dir, filename)
            
            try:
                # Dynamic Python import mechanics
                spec = importlib.util.spec_from_file_location(plugin_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Verify structural contract
                if hasattr(module, "PLUGIN_NAME") and hasattr(module, "execute"):
                    loaded_plugins.append(module)
                    print(f"[Plugin System] Successfully loaded: {module.PLUGIN_NAME}")
            except Exception as e:
                print(f"[Plugin System] Failed to load plugin {filename}: {e}")

# Run the plugin loader on startup
load_plugins()

def on_stock_change(item_dict: dict):
    print(f"[Core System] Stock updated for {item_dict['name']}. Quantity: {item_dict['quantity']}")
    
    # Broadcast event to all python modules in plugins/
    for plugin in loaded_plugins:
        try:
            plugin.execute(item_dict)
        except Exception as e:
            print(f"[Plugin System] Error running plugin {plugin.PLUGIN_NAME}: {e}")

# ==========================================
# 5. CRUD API ENDPOINTS
# ==========================================

# --- READ: Get all items ---
@app.get("/api/items")
def get_items():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items")
        return [dict(row) for row in cursor.fetchall()]

# --- CREATE: Add a new item ---
@app.post("/api/items", status_code=201)
def create_item(item: ItemCreate):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO items (name, description, quantity, price) VALUES (?, ?, ?, ?)",
                (item.name, item.description, item.quantity, item.price)
            )
            conn.commit()
            item_id = cursor.lastrowid
            return {"id": item_id, "name": item.name, "description": item.description, "quantity": item.quantity, "price": item.price}
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Item already exists.")

# --- UPDATE: Modify stock levels ---
@app.put("/api/items/{item_id}")
def update_stock(item_id: int, payload: dict):
    # Expecting {"quantity": X} from frontend
    if "quantity" not in payload:
        raise HTTPException(status_code=400, detail="Missing quantity field")
        
    new_qty = payload["quantity"]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE items SET quantity = ? WHERE id = ?", (new_qty, item_id))
        conn.commit()
        
        # Fetch updated item data for the plugins
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        
        if row:
            item_dict = dict(row)
            on_stock_change(item_dict)  # Trigger hooks!
            return {"message": "Stock updated successfully", "item": item_dict}
        else:
            raise HTTPException(status_code=404, detail="Item not found")

# --- DELETE: Remove an item ---
@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"message": "Deleted successfully"}