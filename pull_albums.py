import os
import pandas as pd
from dotenv import load_dotenv
from notion_client import Client

# Function that returns the database
def fetch_notion_dataframe():

    # 0. Get the Keys
    load_dotenv()
    notion = Client(auth=os.getenv("notion_key"))
    database_id = os.getenv("database_id")

    # 1. Get the raw data
    db_info = notion.databases.retrieve(database_id=database_id)
    data_source_id = db_info["data_sources"][0]["id"]
    response = notion.data_sources.query(data_source_id=data_source_id)
    results = response.get("results")

    # 2. Parse the nested JSON into a simple list of dictionaries
    flattened_data = []
    
    for page in results:
        props = page["properties"]
        row = {}
        
        for col_name, col_data in props.items():
            type = col_data["type"]
            
            # Extract content based on Notion's specific data types
            if type == "title":
                row[col_name] = col_data["title"][0]["text"]["content"] if col_data["title"] else None
            elif type == "rich_text":
                row[col_name] = col_data["rich_text"][0]["text"]["content"] if col_data["rich_text"] else None
            elif type == "select":
                row[col_name] = col_data["select"]["name"] if col_data["select"] else None
            elif type == "multi_select":
                row[col_name] = [item["name"] for item in col_data["multi_select"]]
            elif type == "number":
                row[col_name] = col_data["number"]
            elif type == "checkbox":
                row[col_name] = col_data["checkbox"]
            elif type == "date":
                row[col_name] = col_data["date"]["start"] if col_data["date"] else None
            # Add more types (url, email, etc.) as needed
            
        flattened_data.append(row)


    # 3. Create the DataFrame
    print("Notion Data Pulled Succesfully!") #sanity check
    return pd.DataFrame(flattened_data)