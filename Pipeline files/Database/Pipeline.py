import binascii
import pandas as pd
import sqlite3
import matplotlib
import csv
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import os
import io
import base64
from io import BytesIO
from datetime import datetime
import base64
import hashlib
from collections import deque
try:
    from CustomTypes import CustomType
    from TypeFunctions import *
except Exception as e:
    from .CustomTypes import CustomType
    from .TypeFunctions import *
import json
from functools import reduce
from multiprocessing import Queue


DATE_FORMATS = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"] # Acceptible date formats in csv file

float_customtype = CustomType(getverifyNumberFunction(0, float('inf')), getNumberInput, selectstructure=getNumberFilter) # A custom type defined for inputs for most variables
inventory_types = {'CompositionID': CustomType(verifyCompositionID, getStringInput), 'Density (g/mL)': float_customtype, 'Volume (mL)': float_customtype}
# Dependent variables to record
PROPERTY = pd.DataFrame({'Property':['Density', 'Conductivity', 'Viscosity', 'Mass', 'Volume', 'Resistance'], 'Type':[float_customtype, float_customtype, float_customtype, float_customtype, float_customtype, float_customtype], 'Units':['g/cm^3', 'mS/cm', 'cP', 'g', 'cm^3', 'Ω']})
# Independent variables and process parameters to record
INPUT = pd.DataFrame({'Property':['Temperature', 'CompositionID', 'Date', 'Trial'], 
    'Type':[CustomType(getverifyNumberFunction(-273.15, float('inf')), getNumberInput, selectstructure=getNumberFilter), 
    CustomType(verifyCompositionID, getStringInput), 
    CustomType(getVerifyDateFunction(DATE_FORMATS), getDateInput, selectstructure=getDateFilter),
    CustomType(getverifyNumberFunction(0, float('inf'), integer=True), getNumberInput, selectstructure=getNumberFilter)], 
    'Units':['C', '', '', '#']})
ALL_INPUT = pd.concat([PROPERTY, INPUT])

SOLUBILITY_INPUT = pd.DataFrame({'Property':['Temperature', 'CompositionID', 'Date'], 
    'Type':[CustomType(getverifyNumberFunction(-273.15, float('inf')), getNumberInput, selectstructure=getNumberFilter), 
    CustomType(verifyCompositionID, getStringInput), 
    CustomType(getVerifyDateFunction(DATE_FORMATS), getDateInput, selectstructure=getDateFilter)], 
    'Units':['C', '', '']})

# There are three tables inside the database, the main table named experiments, and solvents and salts to record the respective compositions in each record, which will be joined with main table when being displayed
MAIN_NAME = 'experiments'
TABLE_NAMES = ['experiments', 'Solvent_mass_percentage', 'Salt_molality', 'Solvent_molar_ratio', 'Salt_molar_ratio']

# Constants to save as keys which would be useful in dictionaries
DEPENDENT_VARIABLE = "Dependent variables"
INDEPENDENT_VARIABLE = "Independent variables"
LOGIC = 'logic'

# SQL instruction to get all IDs, useful in outer joins
ALL_IDS = "SELECT ID FROM " + MAIN_NAME
current_file_path = os.path.abspath(__file__)
DEFAULT_DB = os.path.join(current_file_path, '..', '..', "Db", "Database.db") # Database file is called Database.db
SOLUBILITY_DB = os.path.join(current_file_path, '..', '..', "Db", "solubility_data.db")
table_column_map = {}


def get_data_from_database(query, db_file=DEFAULT_DB):
    # Connect to the SQLite database with the given query
    conn = sqlite3.connect(db_file)
    try:
        # Use pandas to execute the SQL query and return a DataFrame
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
    finally:
        # Close the database connection
        conn.close()

def edit_database(queries, db_file=DEFAULT_DB):
    # Connect to the SQLite database, but this time it can modify the data
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    for query in queries:
        cursor.execute(query[0], query[1])  # None is used to insert a NULL value
    conn.commit()
    conn.close()



# Encapsulation to delete data, works like the method below
def delete_data(id):
    delete_data_bulk([id])

# Encapsulation to delete a list of data
def delete_data_bulk(id):
    queries = []
    for i in range(len(id)):
        current = id[i]
        result = verifyID(current)
        if isinstance(result, str):
            return f'Error on line {i + 2}: {result}'
        for table_name in TABLE_NAMES:
            queries.append((f"DELETE FROM {table_name} WHERE id = ?", (result,)))
    edit_database(queries, DEFAULT_DB)

# Encapsulation to insert a new data, works like the method below
def insert_new_data(compositions, database=DEFAULT_DB):
    queries = generate_edit_queries([compositions])
    edit_database(queries, database)

# Encapsulation to insert a new list of data
def insert_new_data_bulk(compositions, database=DEFAULT_DB):
    queries = generate_edit_queries(compositions)
    edit_database(queries, database)

# Helper method to generate queries for editing the database
def generate_edit_queries(compositions):
    queries = []
    for current in compositions[0]:
        table_name = current
        columns = ', '.join(compositions[0][current].keys())

        # Generate SQL query to create table
        if table_name == MAIN_NAME:
            create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (ID INTEGER(32) PRIMARY KEY, {', '.join(compositions[0][current].keys())})"
        else:
            create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} (ID INTEGER(32), {', '.join(compositions[0][current].keys())})"
        queries.append((create_table_query, ""))
    for current_composition in compositions:
        GUID = hash_datapoint(current_composition[MAIN_NAME])
        for current_table in current_composition.keys():
            new_df = 0
            try:
                new_df = pd.DataFrame(current_composition[current_table])
            except ValueError:
                new_df = pd.DataFrame(current_composition[current_table], index=['row1'])
            query = f"DELETE FROM {current_table} WHERE ID = ?"
            queries.append((query, (GUID,)))
            for index, row in new_df.iterrows():
                columns = ', '.join(new_df.columns)
                placeholders = ', '.join(["?" for _ in row])
                if current_table == MAIN_NAME:
                    query = f"INSERT OR REPLACE INTO {current_table} (ID, {columns}) VALUES (?, {placeholders})"
                else:
                    
                    query = f"INSERT INTO {current_table} (ID, {columns}) VALUES (?, {placeholders})"
                    
                queries.append((query, (GUID,) + tuple(row)))
    return queries

# Helper method to generate queries for fetching from the database
def generate_query(table_name, variable, minimum=None, maximum=None):
    if minimum and not isinstance(minimum, (int, float)):
        minimum = f"'{minimum}'"
    if maximum and not isinstance(maximum, (int, float)):
        maximum = f"'{maximum}'"
    if table_name != MAIN_NAME:
        table_name = table_name.replace(' ', '_')
        query = f'SELECT ID, {table_column_map[table_name][2]} as {variable}_{table_column_map[table_name][2]} FROM {table_name} WHERE {table_column_map[table_name][1]} = "{variable}"'
        if minimum and maximum:
            query += f" AND {table_column_map[table_name][2]} BETWEEN {minimum} AND {maximum}"
        elif minimum:
            query += f" AND {table_column_map[table_name][2]} >= {minimum}"
        elif maximum:
            query += f" AND {table_column_map[table_name][2]} <= {maximum}"
        return query
    else:
        query = f"SELECT ID, {variable} FROM {table_name}"
        if minimum and maximum:
            query += f" WHERE {variable} BETWEEN {minimum} AND {maximum}"
        elif minimum:
            query += f" WHERE {variable} >= {minimum}"
        elif maximum:
            query += f" WHERE {variable} <= {maximum}"
        return query
    
# Run clio page helper functions
# Read the CSV file uploaded from users in run clio page
def parse_run_ids(contents, filename):
    content_type, content_string = contents.split(',')
    if 'csv' in filename:
            # Assume that the user uploaded a CSV file
        decoded = base64.b64decode(content_string)
        decoded_csv_data = decoded.decode('utf-8-sig')  # Use utf-8-sig to handle BOM
        csv_reader = csv.reader(io.StringIO(decoded_csv_data), delimiter='\\')
        result = []
        while True:
            try:
                # Attempt to read the next row
                row = next(csv_reader)[0]
                result.append(row)
            except StopIteration:
                # End of CSV reached
                break
        
        return result

# Input page helper functions
def check_validity(args):
    store_dict = {}
    result = {}
    for i in range(len(args)):
        current_type = ALL_INPUT['Type'].iloc[i]
        verify_result = current_type.verify(ALL_INPUT['Property'].iloc[i], args[i])
        if type(verify_result) == str:
            return verify_result
        elif type(verify_result) == dict:
            result.update(verify_result)
        else:
            store_dict[ALL_INPUT['Property'].iloc[i]] = verify_result
    
    result[MAIN_NAME] = store_dict
    return result
        

def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    #try:
    if 'csv' in filename:
            # Assume that the user uploaded a CSV file
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))[ALL_INPUT['Property']]
        compositions = []
        for index, row in df.iterrows():
            try:
                composition = check_validity(tuple(row))
            except KeyError as e:
                return 'Your CSV file must have a ' + e.args[0] + ' column!'
            if isinstance(composition, str):
                return 'Error on line ' + str(index + 2) + ': ' + composition
            compositions.append(composition)
        insert_new_data_bulk(compositions)
        return 'Data uploaded successfully.'
    else:
        return 'You must upload a CSV file'
    
def parse_contents_delete(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    #try:
    if 'csv' in filename:
            # Assume that the user uploaded a CSV file
        df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        try:
            to_delete = df['ID']
            return delete_data_bulk(to_delete)
        except KeyError as e:
            return 'Your CSV file must have an ID column!'
            
    else:
        return 'You must upload a CSV file'
    
def verifyID(value):
    if len(value) != 64:
        return 'Please enter a valid data ID'
    try:
        raw_bytes = bytes.fromhex(value)
        return raw_bytes
    except Exception as e:
        return 'Please enter a valid data ID'

# Home page helper functions
def generate_graph(df, file_name, c, x, y, z=None):
    fig = plt.figure()
    ax = None
    if z is not None:
        ax = fig.add_subplot(111, projection='3d')
        scatter = ax.scatter(df[x], df[y], df[z], c=df[c], marker='o')
        ax.set_zlabel(z)
    else:
        ax = fig.add_subplot(111)
        scatter = ax.scatter(df[x], df[y], c=df[c], marker='o')


    color_bar = fig.colorbar(scatter, ax=ax, pad=0.1, shrink=0.7, aspect=10)
    color_bar.set_label(c)
    #plt.subplots_adjust(left=0.1, right=1.5, top=0.9, bottom=0.1)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    plt.savefig(file_name)
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    buffer.close()

    return img_base64

def generate_df(options, db_file=DEFAULT_DB):
    dfs = []
    all_ids = get_data_from_database(ALL_IDS, db_file)
    merged_ids = []
    for current in options:
        ids = []
        how = 'outer'
        for current_variable in options[current]:
            options[current][current_variable]
            if (current == DEPENDENT_VARIABLE or current == INDEPENDENT_VARIABLE) and current_variable != LOGIC:
                dfs.append(get_data_from_database(generate_query(MAIN_NAME, current_variable), db_file=db_file))
                ids.append(get_data_from_database(generate_query(MAIN_NAME, current_variable, options[current][current_variable]['min'], options[current][current_variable]['max']), db_file=db_file)['ID'])
            elif current_variable != LOGIC:
                dfs.append(get_data_from_database(generate_query(current, current_variable), db_file=db_file))
                ids.append(get_data_from_database(generate_query(current, current_variable, options[current][current_variable]['min'], options[current][current_variable]['max']), db_file=db_file)['ID'])
            elif options[current][current_variable] == 'and':
                how = 'inner'
        
        if len(ids) > 0:
            merged_id = reduce(lambda left, right: pd.merge(left, right, on='ID', how=how), ids)
            merged_ids.append(merged_id)
    final_ids =  reduce(lambda left, right: pd.merge(left, right, on='ID', how='inner'), merged_ids, all_ids)
    
    df = reduce(lambda left, right: pd.merge(left, right, on='ID', how='left'), dfs, final_ids)
    df['ID'] = df['ID'].apply(lambda x: binascii.hexlify(x).decode('utf-8'))
    column_names = set(df.columns)
    for index, row in ALL_INPUT.iterrows():
        if row['Property'] in column_names:
            current_type = row['Type']
            df[row['Property']] = df[row['Property']].apply(current_type.displayMethod)
    df = df.fillna(0)
    return df

    

def graphs(properties, solvents, salts):
    df = generate_df(properties, solvents, salts)
    cwd = os.getcwd()
    file_dir = os.path.join(cwd, 'Saved Plots')
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + '-'

    for i in range(len(solvents)):
        solvents[i] += '_Percentage'
    for i in range(len(salts)):
        salts[i] += '_Molality'

    interest = solvents + salts
    if len(interest) < 2:
        return {'base_64':-1}
    x = interest[0]
    y = interest[1]
    z = None
    if len(interest) >= 3:
        z = interest[2]

    base64_list = []
    for i in range(len(properties)):
        file_name = now + str(i) + '.png'
        base64_list.append(generate_graph(df, os.path.join(file_dir, file_name), properties[i], x, y, z))
    return {'base_64':base64_list}

def get_choices(db_file=DEFAULT_DB, dependent=PROPERTY, independent=INPUT):
    form_names = get_data_from_database("SELECT name FROM sqlite_master WHERE type = 'table'", db_file=db_file)['name'].tolist()
    title_variable_map = {}
    for current in form_names:
        if current != MAIN_NAME:
            query = f"PRAGMA table_info({current})"
            columns = get_data_from_database(query, db_file=db_file)
            table_column_map[current] = list(columns['name'])
            column_query = f"SELECT DISTINCT {table_column_map[current][1]} FROM {current}"
            column_items = get_data_from_database(column_query, db_file=db_file)
            title_variable_map[current] = list(column_items[table_column_map[current][1]])
    
    options = []
    if dependent is not None:
        options.append({"Title":DEPENDENT_VARIABLE, "Options":sorted(dependent['Property'], key=str.lower)})
    if independent is not None:
        options.append({"Title":INDEPENDENT_VARIABLE, "Options":sorted(independent['Property'], key=str.lower)})
    options += [{"Title":title, "Options":sorted(options, key=str.lower)} for title, options in title_variable_map.items()]
    return options

def convert_date(date_string):
    for input_format in DATE_FORMATS:
        try:
            # Parse the date string according to the given input format
            date_obj = datetime.strptime(date_string, input_format)
            # Convert the date object to "MM/DD/YYYY" format
            formatted_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            return formatted_date
        except ValueError as e:
            pass
    return 'Your date must be in MM/DD/YY format!'

def hash_datapoint(experiment_data):
    # Convert the components into strings
    if 'Date' in experiment_data:
        experiment_data['Date'] = str(experiment_data['Date'])
    dict_str = json.dumps(experiment_data, sort_keys=True)
    hash_object = hashlib.sha256(dict_str.encode('utf-8'))
    hash_bytes = hash_object.digest()
    return hash_bytes

def read_csv(csv_path):
    df = pd.read_csv(csv_path)
    return df





# List all files in the folder
def get_file_list(folder_path):
    try:
        return os.listdir(folder_path)[::-1]
    except Exception as e:
        return [f"Error: {str(e)}"]
