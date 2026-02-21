from pymongo import MongoClient
import os

client = MongoClient(os.getenv("MONGO_URI"))
db = client["mangobytes"]

def save_graph(graph_name, graph_dict, timestamp=None):
    db.graphs.insert_one({
        "graph_name": graph_name,
        "graph_data": graph_dict,
        "timestamp": timestamp
    })

def get_graph(graph_name):
    result = db.graphs.find_one({"graph_name": graph_name})
    # Convert MongoDB ObjectId to string for JSON serialization
    if result:
        result["_id"] = str(result["_id"])
    return result

def get_all_graphs():
    results = list(db.graphs.find({}))
    # Convert all ObjectIds to strings for JSON serialization
    for result in results:
        result["_id"] = str(result["_id"])
    return results