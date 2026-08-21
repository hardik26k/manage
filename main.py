import os
from dotenv import load_dotenv
from typing import Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from supabase import create_client, Client

load_dotenv()

app = FastAPI(title="Inventory Management API")

# Enable CORS for deployed frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Supabase Client
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables must be set.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Pydantic Schemas ---
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1)
    brand_name: Optional[str] = None
    product_type: Optional[str] = None
    quantity: int = Field(0, ge=0)

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    brand_name: Optional[str] = None
    product_type: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=0)

# --- Plugin / Event Hook Placeholder ---
def on_stock_change(item_data: dict):
    print(f"[EVENT] Item state changed: {item_data}")

# --- API Endpoints using supabase-py ---

@app.get("/api/items")
def get_items():
    try:
        # SELECT * FROM items ORDER BY id ASC
        response = supabase.table("items").select("*").order("id", desc=False).execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/items/{item_id}")
def get_item(item_id: int):
    try:
        # SELECT * FROM items WHERE id = item_id
        response = supabase.table("items").select("*").eq("id", item_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Item not found")
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate):
    try:
        payload = item.model_dump(exclude_unset=True)
        # INSERT INTO items (...) VALUES (...)
        response = supabase.table("items").insert(payload).execute()
        
        new_item = response.data[0]
        on_stock_change(new_item)
        return new_item
    except Exception as e:
        error_msg = str(e)
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            raise HTTPException(
                status_code=400, 
                detail=f"An item named '{item.name}' already exists."
            )
        raise HTTPException(status_code=500, detail=error_msg)

@app.put("/api/items/{item_id}")
def update_item(item_id: int, payload: ItemUpdate):
    try:
        # 1. Verify item exists
        existing = supabase.table("items").select("*").eq("id", item_id).execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Item not found")

        # 2. Extract only fields provided in request body
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            return {"message": "No fields to update", "item": existing.data[0]}

        # UPDATE items SET ... WHERE id = item_id
        response = supabase.table("items").update(update_data).eq("id", item_id).execute()
        updated_item = response.data[0]

        on_stock_change(updated_item)
        return {"message": "Updated successfully", "item": updated_item}
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        if "duplicate key" in error_msg.lower() or "unique constraint" in error_msg.lower():
            raise HTTPException(
                status_code=400, 
                detail="An item with this name already exists."
            )
        raise HTTPException(status_code=500, detail=error_msg)

@app.delete("/api/items/{item_id}")
def delete_item(item_id: int):
    try:
        # DELETE FROM items WHERE id = item_id
        response = supabase.table("items").delete().eq("id", item_id).execute()
        if not response.data:
            raise HTTPException(status_code=404, detail="Item not found")
            
        return {"message": f"Item {item_id} successfully deleted."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))