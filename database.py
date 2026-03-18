import os
import uuid
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from supabase import create_client, Client
from flask_cors import CORS

# ==========================================
# 1. SETUP ENVIRONMENT & DATABASE
# ==========================================
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# ==========================================
# 2. SETUP FLASK, CORS, & SOCKET.IO
# ==========================================
app = Flask(__name__)
# Pinapayagan na natin ang lahat ng ports (5173, 5174, etc.) para walang "Connection refused"
CORS(app, resources={r"/api/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

# Pang-harang sa CORS issues bago mag-process ng Add/Update/Delete
@app.after_request
def after_request(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response


# ==========================================
# 3. [API] LOGIN MODULE
# ==========================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    try:
        query = supabase.table("admins").select("*").eq("email", email).eq("password", password).execute()
        if query.data:
            user = query.data[0]
            if user.get('status') == 'Active':
                # Ipapasa natin ang admin_user pabalik sa React para sa "Hi, [Name]"
                return jsonify({"success": True, "user": {"name": user.get('admin_user'), "role": user.get('role')}}), 200
            return jsonify({"success": False, "message": "Inactive account."}), 403
        return jsonify({"success": False, "message": "Invalid credentials."}), 401
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 4. [API] FETCH ALL DATA (DASHBOARD)
# ==========================================
@app.route('/api/data', methods=['GET'])
def get_all_data():
    try:
        try: p_res = supabase.table("products").select("*").execute(); products = p_res.data
        except: products = []

        try: m_res = supabase.table("stock_movements").select("*").order("updated_at", desc=True).limit(20).execute(); movements = m_res.data
        except: 
            try: m_res = supabase.table("stock_movements").select("*").order("created_at", desc=True).limit(20).execute(); movements = m_res.data
            except: movements = []

        try: s_res = supabase.table("suppliers").select("*").execute(); suppliers = s_res.data
        except: suppliers = []

        try: c_res = supabase.table("categories").select("*").execute(); categories = c_res.data
        except: categories = []

        return jsonify({
            "products": products or [], 
            "stock_movements": movements or [],
            "suppliers": suppliers or [],
            "categories": categories or []
        }), 200
    except Exception as e:
        print(f"System Error: {e}")
        return jsonify({"error": str(e)}), 500


# ==========================================
# 5. [API] USERS / ADMIN MANAGEMENT
# ==========================================
@app.route('/api/users', methods=['GET'])
def get_users():
    try:
        res = supabase.table("admins").select("*").execute()
        return jsonify({"success": True, "data": res.data}), 200
    except Exception as e:
        print(f"🔥 GET USERS ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.json
    try:
        new_user = {
            "admin_user": data.get("admin_user"),
            "email": data.get("email"),
            "password": data.get("password"),
            "role": data.get("role", "Cashier"),
            "status": data.get("status", "Active")
        }
        res = supabase.table("admins").insert(new_user).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200
    except Exception as e:
        print(f"🔥 ADD USER ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/users/<int:admin_id>', methods=['PUT'])
def update_user(admin_id):
    data = request.json
    try:
        update_data = {
            "admin_user": data.get("admin_user"),
            "email": data.get("email"),
            "password": data.get("password"),
            "role": data.get("role"),
            "status": data.get("status")
        }
        res = supabase.table("admins").update(update_data).eq("admin_id", admin_id).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200
    except Exception as e:
        print(f"🔥 UPDATE USER ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 6. [API] SUPPLIERS MANAGEMENT
# ==========================================
@app.route('/api/suppliers', methods=['POST'])
def add_supplier():
    data = request.json
    try:
        new_supplier = {
            "company_name": data.get("company_name"),
            "contact_person": data.get("contact_person"),
            "contact_number": data.get("contact_number"),
            "email_address": data.get("email_address"),
            "brand": data.get("brand"),
            "is_active": True
        }
        res = supabase.table("suppliers").insert(new_supplier).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200
    except Exception as e:
        print(f"🔥 SUPABASE INSERT ERROR: {e}") 
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/suppliers/<int:supplier_id>', methods=['PUT'])
def update_supplier(supplier_id):
    data = request.json
    try:
        updated_data = {
            "company_name": data.get("company_name"),
            "contact_person": data.get("contact_person"),
            "contact_number": data.get("contact_number"),
            "email_address": data.get("email_address"),
            "brand": data.get("brand")
        }
        res = supabase.table("suppliers").update(updated_data).eq("supplier_id", supplier_id).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200
    except Exception as e:
        print(f"🔥 SUPABASE UPDATE ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ==========================================
# 7. [API] PRODUCTS MANAGEMENT (With Image Upload)
# ==========================================
@app.route('/api/products', methods=['POST'])
def add_product():
    try:
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        supplier_id = request.form.get('supplier_id')
        unit = request.form.get('unit_of_measurement')
        price = request.form.get('price')
        stock = request.form.get('stock_quantity')
        low_stock = request.form.get('low_stock_threshold')

        new_product = {
            "name": name,
            "category_id": int(category_id) if category_id and category_id != 'null' else None,
            "supplier_id": int(supplier_id) if supplier_id and supplier_id != 'null' else None,
            "unit_of_measurement": unit,
            "price": float(price) if price else 0,
            "stock_quantity": int(stock) if stock else 0,
            "initial_inventory": int(stock) if stock else 0,
            "available_quantity": int(stock) if stock else 0,
            "final_cost": (float(price) if price else 0) * (int(stock) if stock else 0),
            "low_stock_threshold": int(low_stock) if low_stock else 10,
            "is_active": True
        }

        # Kung may inupload na picture, ipapasok sa Supabase Storage
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                file_ext = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_bytes = file.read()
                
                supabase.storage.from_("product-images").upload(path=unique_filename, file=file_bytes, file_options={"content-type": file.content_type})
                
                public_url_data = supabase.storage.from_("product-images").get_public_url(unique_filename)
                image_url = public_url_data if isinstance(public_url_data, str) else public_url_data.get('publicUrl')
                new_product["image_path"] = image_url

        res = supabase.table("products").insert(new_product).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200

    except Exception as e:
        print(f"🔥 ADD PRODUCT ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    try:
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        supplier_id = request.form.get('supplier_id')
        unit = request.form.get('unit_of_measurement')
        price = request.form.get('price')
        
        # 👇 INAYOS NATIN ITO: Kinukuha nang tama ang stock_quantity 
        stock = request.form.get('stock_quantity')
        low_stock = request.form.get('low_stock_threshold')

        update_data = {
            "name": name,
            "category_id": int(category_id) if category_id and category_id != 'null' else None,
            "supplier_id": int(supplier_id) if supplier_id and supplier_id != 'null' else None,
            "unit_of_measurement": unit,
            "price": float(price) if price else 0,
            
            # 👇 INAYOS NATIN ITO: Ginamit natin ang 'stock' variable
            "stock_quantity": int(stock) if stock is not None and stock != 'null' else 0,
            "available_quantity": int(stock) if stock is not None and stock != 'null' else 0,
            "final_cost": (float(price) if price else 0) * (int(stock) if stock is not None and stock != 'null' else 0),
            
            "low_stock_threshold": int(low_stock) if low_stock is not None and low_stock != 'null' else 10,
            
            "updated_at": "now()"
        }

        # Kung may bagong picture na inupload
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                file_ext = os.path.splitext(file.filename)[1]
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_bytes = file.read()
                
                supabase.storage.from_("product-images").upload(path=unique_filename, file=file_bytes, file_options={"content-type": file.content_type})
                
                public_url_data = supabase.storage.from_("product-images").get_public_url(unique_filename)
                image_url = public_url_data if isinstance(public_url_data, str) else public_url_data.get('publicUrl')
                update_data["image_path"] = image_url

        res = supabase.table("products").update(update_data).eq("product_id", product_id).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200

    except Exception as e:
        print(f"🔥 PRODUCT UPDATE ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
# ==========================================
# 8. [SOCKET] REAL-TIME STOCK ADJUSTMENT
# ==========================================
@socketio.on('adjust_stock')
def handle_adjust_stock(data):
    p_id = data.get('id')
    qty = int(data.get('qty'))
    a_type = data.get('type')
    
    try:
        prod = supabase.table("products").select("*").eq("product_id", p_id).single().execute().data
        
        curr_q = int(prod.get('stock_quantity', 0))
        new_q = (curr_q + qty) if a_type == 'Add' else max(0, curr_q - qty)
        
        # Ina-update pareho para walang maiwan
        supabase.table("products").update({
            "stock_quantity": new_q,
            "available_quantity": new_q
        }).eq("product_id", p_id).execute()
        
        supabase.table("stock_movements").insert({
            "product_id": p_id, 
            "movement_type": a_type, 
            "quantity_change": qty if a_type == 'Add' else -qty
        }).execute()
        
        emit('stock_updated', {"product_id": p_id, "stock_quantity": new_q, "available_quantity": new_q}, broadcast=True)
        
    except Exception as e:
        print(f"🔥 SOCKET ERROR: {e}")

# ==========================================
# 10. [API] CATEGORIES MANAGEMENT
# ==========================================
@app.route('/api/categories', methods=['POST', 'OPTIONS'])
def add_category():
    if request.method == 'OPTIONS': # Pinapadaan agad natin ang browser check
        return jsonify({"success": True}), 200
        
    data = request.json
    category_name = data.get('category_name')
    
    if not category_name:
        return jsonify({"success": False, "message": "Category name is required"}), 400
    
    try:
        new_category = {"category_name": category_name}
        res = supabase.table("categories").insert(new_category).execute()
        return jsonify({"success": True, "data": res.data[0]}), 200
    except Exception as e:
        print(f"🔥 ADD CATEGORY ERROR: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/categories/<int:category_id>', methods=['DELETE', 'OPTIONS'])
def delete_category(category_id):
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
        
    try:
        res = supabase.table("categories").delete().eq("category_id", category_id).execute()
        return jsonify({"success": True}), 200
    except Exception as e:
        print(f"🔥 DELETE CATEGORY ERROR: {e}")
        return jsonify({"success": False, "message": "Cannot delete. Category might be in use by a product."}), 

# ==========================================
# 11. [API] FORGOT PASSWORD (SIMULATION)
# ==========================================
@app.route('/api/verify-email', methods=['POST', 'OPTIONS'])
def verify_email():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    data = request.json
    email = data.get('email')
    
    try:
        # Iche-check kung may ganitong email sa admins table
        query = supabase.table("admins").select("*").eq("email", email).execute()
        if query.data:
            return jsonify({"success": True, "message": "Email found"}), 200
        return jsonify({"success": False, "message": "Email not found in our records."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/reset-password', methods=['POST', 'OPTIONS'])
def reset_password():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    
    data = request.json
    email = data.get('email')
    new_password = data.get('password')
    
    try:
        # Papalitan ang password sa database
        res = supabase.table("admins").update({"password": new_password}).eq("email", email).execute()
        return jsonify({"success": True, "message": "Password updated"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
# ==========================================
# 9. RUN SERVER
# ==========================================
if __name__ == '__main__':
    socketio.run(app, host='127.0.0.1', port=5000, debug=True)


