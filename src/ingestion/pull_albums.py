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

    # 1. Get the data_source_id (The correct modern API method you originally had!)
    db_info = notion.databases.retrieve(database_id=database_id)
    data_source_id = db_info["data_sources"][0]["id"]

    # 2. Get the raw data with Pagination to bypass the 100 limit
    results = []
    has_more = True
    next_cursor = None

    while has_more:
        # Prepare the query parameters using the data_source_id
        query_params = {"data_source_id": data_source_id}
        
        # If we have a cursor from a previous loop, pass it to get the next page
        if next_cursor:
            query_params["start_cursor"] = next_cursor
            
        # Query the data_source, NOT databases!
        response = notion.data_sources.query(**query_params)
        
        # Append this page's results to our master list
        results.extend(response.get("results", []))
        
        # Update pagination variables for the next loop iteration
        has_more = response.get("has_more", False)
        next_cursor = response.get("next_cursor", None)

    # 3. Parse the nested JSON into a simple list of dictionaries
    flattened_data = []
    
    for page in results:
        props = page["properties"]
        row = {}

        # Page-level metadata (not a property): Notion's own record of when
        # this entry was actually created/edited by Chris. This is what
        # "recently added/edited" should be based on — Supabase's own
        # created_at/updated_at only reflect when the pipeline happened to
        # process the row, which can lag well behind (or diverge from) the
        # real Notion edit history, especially for anything that took a
        # few retries to resolve.
        row['NotionCreatedAt'] = page.get('created_time')
        row['NotionEditedAt'] = page.get('last_edited_time')

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

    # 4. Create the DataFrame
    print(f"Notion Data Pulled Successfully! Total rows: {len(flattened_data)}") # sanity check
    return pd.DataFrame(flattened_data)