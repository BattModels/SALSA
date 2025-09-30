import sqlite3
import os

def read_from_sqlite(db_file, query):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_file)
    
    # Create a cursor object
    cursor = conn.cursor()
    
    try:
        # Execute the query
        cursor.execute(query)
        
        # Fetch all rows from the result
        rows = cursor.fetchall()
        if cursor.description is not None:
            columns = [description[0] for description in cursor.description]
            print("\t".join(columns))
            for row in rows:
                print("\t".join(map(str, row)))
        else:
            conn.commit()
    
    except sqlite3.Error as e:
        print(e)
    
    finally:
        # Close the cursor and connection
        cursor.close()
        conn.close()

# Example usage
current_file_path = os.path.abspath(__file__)
db_file = os.path.join(current_file_path, '..', '..', 'Db', "solubility_data.db") # Database file is called Database.db

while True:
    query = input("Enter your SQL query: ")
    if query == 'NA':
        exit()
    else:
        try: 
            read_from_sqlite(db_file, query)
        except Exception as e:
            print(e)