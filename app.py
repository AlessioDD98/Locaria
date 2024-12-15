import time
import requests
import json
from flask import Flask, Response, render_template

app = Flask(__name__)

# Configuration
FINANCERO_BASE_URL = "https://financero.api.com/v1"
FINANCERO_INVOICES_URL = "https://financero.mockapi.com/v3-1"
ODERINO_BASE_URL = "https://oderino.mockapi.com/v1"
ODERINO_ORDERS_V2_URL = "https://oderino.api.com/v2"
ODERINO_DELIVERY_V1_URL = "https://oderino.api.com/v1"

CACHE_TTL_SECONDS = 60  # cache TTL

# In-memory cache
cache = {}

def is_cache_valid(customer_id):
    if customer_id not in cache:
        return False
    entry = cache[customer_id]
    if (time.time() - entry["timestamp"]) > CACHE_TTL_SECONDS:
        return False
    return True

# --- Helper functions to call external endpoints ---
def fetch_financero_address(customer_id):
    url = f"{FINANCERO_BASE_URL}/customers/{customer_id}/address"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_financero_billing_info(customer_id):
    url = f"{FINANCERO_BASE_URL}/customers/{customer_id}/billing-info"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_financero_invoices(customer_id):
    url = f"{FINANCERO_INVOICES_URL}/customers/{customer_id}/invoices"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_oderino_orders(customer_id):
    url = f"{ODERINO_BASE_URL}/customers/{customer_id}/orders"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_oderino_order_details(order_id):
    url = f"{ODERINO_ORDERS_V2_URL}/orders/{order_id}"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_oderino_jobs_for_order(order_id):
    url = f"{ODERINO_ORDERS_V2_URL}/orders/{order_id}/jobs"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def fetch_oderino_delivery_details(order_id):
    url = f"{ODERINO_DELIVERY_V1_URL}/orders/{order_id}/delivery"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            return None, resp.json()
    except requests.exceptions.RequestException as e:
        return None, str(e)

def aggregate_order_details(order_list):
    orders_aggregated = []
    warnings = []
    aggregated_order = {}
    for order_item in order_list.get("orders", []):
        order_id = order_item["order_id"]
        
        # Order Details
        order_details, err_order_details = fetch_oderino_order_details(order_id)
        if order_details:
            aggregated_order = order_details
        elif  isinstance(err_order_details, str):
            return Response("Unable to reach API. \n Exception raised: \n"+err_order_details, status=400, mimetype='text/plain')    
        else:
            warnings.append(err_order_details["error"])

        # Jobs
        jobs_response, err_jobs = fetch_oderino_jobs_for_order(order_id)
        if jobs_response:
            del jobs_response["order_id"]
            aggregated_order["jobs"]=(jobs_response)
        elif  isinstance(err_jobs, str):
            return Response("Unable to reach API. \n Exception raised: \n"+err_jobs, status=400, mimetype='text/plain')   
        else:
            warnings.append(err_jobs["error"])

        # Delivery
        delivery_details, err_delivery = fetch_oderino_delivery_details(order_id)
        if delivery_details:
            del delivery_details["order_id"]
            aggregated_order["delivery"]=(delivery_details["delivery"])
        elif  isinstance(err_delivery, str):
            return Response("Unable to reach API. \n Exception raised: \n"+err_delivery, status=400, mimetype='text/plain')   
        else:
            warnings.append(err_delivery["error"])

        orders_aggregated.append(aggregated_order)

    return orders_aggregated, warnings

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/customers/<customer_id>/summary", methods=["GET"])
def get_customer_summary(customer_id):
    if is_cache_valid(customer_id):
        json_str = json.dumps(cache[customer_id]["data"], sort_keys=False)
        return Response(json_str, status=200, mimetype='application/json')

    aggregated_data = {
        "customer_id": customer_id,
        "company_name": None,
        "address": None,
        "billing_info": None,
        "invoices": None,
        "orders": None,
        "warnings": []
    }

    # FINANCERO
    # Address
    address_data, err_address = fetch_financero_address(customer_id)
    if address_data:
        aggregated_data["company_name"] = address_data["company_name"]
        aggregated_data["address"] = address_data["address"]
    elif  isinstance(err_address, str):
        return Response("Unable to reach API. \n Exception raised: \n"+err_address, status=400, mimetype='text/plain')
    else:
        aggregated_data["warnings"].append(err_address["error"])
    # Billing info
    billing_data, err_billing = fetch_financero_billing_info(customer_id)
    if billing_data:
        del billing_data["customer_id"]
        aggregated_data["billing_info"] = billing_data
    elif  isinstance(err_billing, str):
        return Response("Unable to reach API. \n Exception raised: \n"+err_billing, status=400, mimetype='text/plain')
    else:
        aggregated_data["warnings"].append(err_billing["error"])
    # Invoices
    invoices_data, err_invoices = fetch_financero_invoices(customer_id)
    if invoices_data:
        del invoices_data["customer_id"]
        aggregated_data["invoices"] = invoices_data["invoices"]
    elif  isinstance(err_invoices, str):
        return Response("Unable to reach API. \n Exception raised: \n"+err_invoices, status=400, mimetype='text/plain')
    else:
        aggregated_data["warnings"].append(err_invoices["error"])

    # ODERINO
    orders_data, err_orders = fetch_oderino_orders(customer_id)
    if orders_data:
        del orders_data["customer_id"]
        orders_aggregated, order_warnings = aggregate_order_details(orders_data)
        aggregated_data["orders"] = orders_aggregated
        aggregated_data["warnings"].extend(order_warnings)
    elif  isinstance(err_orders, str):
        return Response("Unable to reach API. \n Exception raised: \n"+err_orders, status=400, mimetype='text/plain')
    else:
        aggregated_data["warnings"].append(err_orders["error"])

    cache[customer_id] = {
        "timestamp": time.time(),
        "data": aggregated_data
    }

    json_str = json.dumps(aggregated_data, sort_keys=False)
    return Response(json_str, status=200, mimetype='application/json')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
