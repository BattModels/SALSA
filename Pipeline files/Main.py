import os
import io
from dash import Dash, dash_table, html, dcc, callback, Output, Input, State, callback_context
from dash.dependencies import ALL
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
import numpy as np
import dash_bootstrap_components as dbc
from dash.dash_table.Format import Format, Scheme
from Database.Pipeline import *
from io import StringIO
import datetime
import binascii
import sys
from dash.exceptions import PreventUpdate
import multiprocessing
from multiprocessing import Process, freeze_support, Queue
import logging
import shutil
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = current_dir
sys.path.insert(0, parent_dir)
from Equipment_Control.Run import *
selected_element = -1
app = Dash(__name__, suppress_callback_exceptions=True)
input_properties = ["CompositionID"]
GUID_LENGTH = 32
labels = []
MARGIN = 0.3
GRAPH_COLUMNS = 3
REINITIALIZE_LIMIT = 10
process = None
pio.templates.default = "plotly_white"
trial = 0
IMAGE_HEIGHT = 450
stored_figure = []



def update_message_after_solubility_measurement(compositionID, salt, experiment_status):
    experiment_status["trial"] = 1
    print('here')
    current_time = datetime.now()
    log_file_name = current_time.strftime("%Y-%m-%d %H-%M-%S") + ".log"
    log_file_name = os.path.join(current_dir, '..', 'Logs', log_file_name)
    experiment_status["log_file_name"] = log_file_name
    result = run_solubility(compositionID, salt, log_file_name, trial=experiment_status["trial"])
    experiment_status["previous"] = compositionID
    experiment_status["is_running"] = "Measurement complete, please cleanup before the next run"
    experiment_status["result"] = result

def update_message_after_experiment(compositionID, experiment_status):
    current_time = datetime.now()
    log_file_name = current_time.strftime("%Y-%m-%d %H-%M-%S") + ".log"
    experiment_status["log_file_name"] = log_file_name
    if experiment_status["previous"] != compositionID:
        experiment_status["trial"] = 1
    result = run(compositionID, log_file_name, experiment_status["trial"])
    experiment_status["previous"] = compositionID
    experiment_status["is_running"] = "No experiment is running"
    experiment_status["result"] = result
    if result == 'No errors':
        experiment_status["pop"] =  True
        experiment_status["trial"] += 1
        
def update_message_after_zero(experiment_status):
    current_time = datetime.now()
    log_file_name = current_time.strftime("%Y-%m-%d %H-%M-%S") + ".log"
    experiment_status["log_file_name"] = log_file_name
    result = zero(experiment_status["log_file_name"])
    
    experiment_status["is_running"] = "No experiment is running"
    if experiment_status["result"] != "Clio is locked" or result != "No errors":
        experiment_status["result"] = result
def update_message_after_agent(user_message, experiment_status):
    ai_response = experiment_status["agent"].conversation_with_agent(user_message)
    experiment_status["history"].append({'sender': 'Agent', 'text': ai_response})



if __name__ == '__main__':
    if multiprocessing.get_start_method(allow_none=True) != 'spawn':
        multiprocessing.set_start_method('spawn')
    manager = multiprocessing.Manager()
    experiment_status = manager.dict()
    experiment_status["is_running"] = "No experiment is running"
    experiment_status["result"] = "No errors"
    experiment_status["pop"] = False
    experiment_status["log_file_name"] = ''
    experiment_status["previous"] = ''
    experiment_status["trial"] = 1
    experiment_status["history"] = manager.list()
    experiment_status["history"].append({'sender': 'Agent', 'text': 'Start your conversation.'})
    experiment_status["queue"] = manager.list()


    # Define the layout of the app
    app.layout = html.Div([
            html.Div(children=[dcc.Location(id='url', refresh=False),
            dcc.Link('Data', href='/', className='link'),
            dcc.Link('Input data', href='/input-page', className='link'),
            dcc.Link('Run Clio', href='/run-page', className='link'),
            dcc.Link('Inventory', href='/inventory-page', className='link'),
            dcc.Link('Candidate', href='/candidate-page', className='link'),
            dcc.Link('Logs', href='/log-page', className='link'),
            dcc.Link('Solubility database', href='/solubility-database-page', className='link'),
            dcc.Link('Test solubility', href='/solubility-run-page', className='link'),
            dcc.Link('Chat with Agent', href='/agent-page', className='link')], className='top-menu-bar'),
            dcc.Interval(id="back-interval", interval=500, n_intervals=0),
        html.Div(id='page-content')
    ])

    # Elements for home page, which displays data
    home_content = [
        html.H1(children='Select Properties, solvents, and salts', style={'textAlign': 'center'}),
        html.Div(className='selection-container', children=
            [html.Div(id='container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
            html.Div([
                html.Button('Show Table', id='table-button', className="custom-button", n_clicks=0),
                html.Button('Show 2D Graphs', id='graph-button', className="custom-button", n_clicks=0),
                html.Button('Show 3D Graphs', id='graph-button-3d', className="custom-button", n_clicks=0)
            ], id='button-container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
            html.Div(id='plot-container', style={'overflowX': 'auto', 'display': 'flex', 'flex-direction': 'column'}),
            dcc.Store(id='form-options', data={}),
            dcc.Store(id='displayed-graphs', data={}),
            dcc.Store(id='displayed-form', data=None)])
        ]

    # Elements for input page, which allows us to manually upload new lab data
    inputs = [item for pair in zip([f"{ALL_INPUT['Property'].iloc[i]} {ALL_INPUT['Units'].iloc[i]}" for i in range(len(ALL_INPUT['Property']))], 
        [current[1]['Type'].inputstructure(current[1]['Property'] + '-input') for current in ALL_INPUT.iterrows()]) for item in pair]
    input_content = [html.H1('Please input new data'), 
                     html.Div(children=[
        html.H2('Please upload a csv file. Make sure it has all the columns specified below.'),
        dcc.Upload(
            id='upload-file',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            multiple=False,
            className='upload'
        ),
        dbc.Alert(id='file-alert', is_open=False, duration=4000),
        html.H2('Alternatively, you can manually enter the experiment data.'),
            html.Div(children=[html.Div(inputs[0:len(inputs) // 2], id='inputs',
            style={"display": "flex", "flexDirection": "column", "gap": "10px", "flexWrap": "wrap", "padding": "10px"}),
            html.Div(inputs[len(inputs) // 2:], id='inputs',
            style={"display": "flex", "flexDirection": "column", "gap": "10px", "flexWrap": "wrap", "padding": "10px"})],
        style={"display": "flex", "flexDirection": "row", "justifyContent": "center", "gap": "20%", "padding": "10px"}),
        dbc.Alert(id='alert', is_open=False, duration=4000),
        html.Button('Add Data', id='add-data-button', className="custom-button", n_clicks=0),
        html.H2('You can upload the CSV file with all the record ID (not CompositionID) to delete the data'),
        dcc.Upload(
            id='upload-delete-file',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            multiple=False,
            className='upload'
        ),
        dbc.Alert(id='delete-file-alert', is_open=False, duration=4000),
        html.H2('Alternatively, you can enter the record ID (not CompositionID) to delete the data'),
        dcc.Input(id='delete', type='text', className='custom-textfield', value=None),
        html.Button('Delete Record', id='delete-record', className="custom-button", n_clicks=0),
        dbc.Alert(id='delete-alert', is_open=False, duration=4000),
    ], className='selection-container')]

    # Page to control Clio
    run_content = [
        dcc.Store(id="experiment-state", data={"is_running": False, "result": None}),
        html.H1('Run experiment'),
        html.Div(children=[html.H2('Please upload a csv file. Make sure it contains a single column with compositionIDs.'),
            dcc.Upload(
            id='upload-file-experiment',
            children=html.Div([
                'Drag and Drop or ',
                html.A('Select Files')
            ]),
            multiple=False,
            className='upload',
            disabled=experiment_status['is_running'] != "No experiment is running"
        ),
            dbc.Alert(id='experiment-alert', is_open=False, duration=4000),
            html.H2('Alternatively, you can enter the compositionID you want to run.'),
            dcc.Input(id='compositionID-experiment', type='text', className='custom-textfield', value=None),
            html.Button("Add to queue", id="start-experiment", className="custom-button", n_clicks=0, disabled=experiment_status['is_running'] != "No experiment is running"),
            html.Button("Trouble resolved", id="trouble-button", className="custom-button", n_clicks=0, disabled=experiment_status['result']!='No errors'),
            dbc.Alert(id='run-input-alert', is_open=False, duration=4000),
            html.H3(children='Experiment Status:'),
            html.Div(id="Running-status", children=experiment_status['is_running']),
            html.H3(children='Error Status:'),
            html.Div(id="Error-message", children=experiment_status["result"]),
            html.Div(children=[html.Button("Stop and Lock", id="lock-clio", className="halt-button", n_clicks=0),
                               html.Button("Zero viscometer", id="zero", className="custom-button", n_clicks=0)]),
            dcc.Interval(id="polling-interval", interval=100, n_intervals=0),
            html.Div(children=[html.H2('Experiment Queue'),
                html.Div(id="Queue-length", children='0 experiments to be done'),
                html.Button("Delete", id="delete-button", className="custom-button", n_clicks=0),
                html.Div(id="queue-display", className='list-container')
            ], className='inside-container'),
        ], className='selection-container'),
        
        
        
    ]

    # Read the CSV files necessary for inventory page
    current_file_directory = os.path.dirname(os.path.abspath(__file__))
    inventory_path = os.path.join(current_file_directory, 'Equipment_control', 'Inventory.csv')
    inventory_df = read_csv(inventory_path)
    candidate_path = os.path.join(current_file_directory, 'Equipment_control', 'Candidate solutions.csv')
    candidate_df = read_csv(candidate_path)

    

    # Candidate page elements
    candidate_content = [html.Div([
        html.H1('Candidate solutions'),
        html.Div(children=[dash_table.DataTable(
            id="candidate-table",
            columns=[{"name": i, "id": i} for i in candidate_df.columns],
            data=candidate_df.to_dict("records"),
            style_table={'width': '50%', "justifyContent": "center", "alignItems": "center"},
            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
            style_cell={'textAlign': 'left', 'padding': '5px'},
        ), html.Button("Clear", id="clear-candidate-button", className="custom-button", n_clicks=0)],  className='selection-container', style={
                        "display": "flex",                # Use flexbox
                        "justifyContent": "center",       # Center table horizontally
                        "align-items": "center",
                        "flex-direction": "column"
                }), 
        dcc.Interval(
            id="candidate-interval",
            interval=100,  # Update every 0.1 second
            n_intervals=0
        )
    ])]

    log_content = [
        html.H1("Log Viewer", style={'textAlign': 'center'}), # File list
        html.Div(children=[
            html.H2("Log file list"),
            html.Div(id='file-list', className='list-container'), # File content display
             html.H2("File content"),
            html.Div(id='file-content', className='inside-container'),
            dcc.Interval(
                id="log-interval",
                interval= 25,
                n_intervals=0
            )
        ], className='selection-container'),
        dcc.Store("selected-file", storage_type='memory', data='NA')
    ]

    test_solubility_content = [html.H1("Measure Solubility", style={'textAlign': 'center'}), # File list
        html.Div(children=[
            html.H2("Solvent composition"),
            dcc.Input(id='solubility-solvent', type='text', className='custom-textfield', value=None),
            dbc.Alert(id='solubility-solvent-alert', is_open=False, duration=4000),
            html.H2("Salt composition"),
            dcc.Input(id='solubility-salt', type='text', className='custom-textfield', value=None),
            dbc.Alert(id='solubility-salt-alert', is_open=False, duration=4000),
            html.Button("Start", id="start-solubility-button", className="custom-button", n_clicks=0, style={'width': '100px'}),
            html.Button("Cleanup finished", id="trouble-button", className="custom-button", n_clicks=0, disabled=experiment_status['result']!='No errors', style={'width': '100px'}),
            html.H3(children='Experiment Status:'),
            html.Div(id="Running-status", children=experiment_status['is_running']),
            html.H3(children='Error Status:'),
            html.Div(id="Error-message", children=experiment_status["result"]),
            dcc.Interval(id="solubility-interval", interval=100, n_intervals=0)
        ], className='selection-container', style={
                        "display": "flex",                # Use flexbox
                        "justifyContent": "center",       # Center table horizontally
                        "align-items": "left",
                        "flex-direction": "column"
                })]
    
    solubility_database_content = [html.H1("Solubility database", style={'textAlign': 'center'}), # File list
        html.Div(children=[
            html.H2("Select solvents and salts"),
            html.Div(id='solubility-container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
            html.Div([
                html.Button('Show Table', id='table-solubility-button', className="custom-button", n_clicks=0),
                html.Button('Show 2D Graphs', id='graph-solubility-button', className="custom-button", n_clicks=0),
                html.Button('Show 3D Graphs', id='graph-solubility-button-3d', className="custom-button", n_clicks=0)
            ], id='button-container', style={'display': 'flex', 'padding': '10px', 'flex-direction': 'row'}),
            html.Div(id='plot-solubility-container', style={'overflowX': 'auto', 'display': 'flex', 'flex-direction': 'column'}),
            dcc.Store(id='displayed-form', data=None),
            dcc.Store(id='displayed-graphs', data={})
        ], className='selection-container', style={
                        "display": "flex",                # Use flexbox
                        "justifyContent": "center",       # Center table horizontally
                        "align-items": "left",
                        "flex-direction": "column"
                }),
        dcc.Store(id='form-options', data={})]
    

    @app.callback( 
        Input('back-interval', 'n_intervals')
    )
    def tester(n_intervals):
        global process

        
        if (experiment_status["is_running"] == "No experiment is running") and experiment_status["result"] == "No errors":
            if experiment_status["pop"]:
                id_queue.popleft()
                experiment_status["pop"] = False
            if len(id_queue) and experiment_status["result"] == "No errors":
                experiment_status["is_running"] = "Running experiments"
                process = Process(target=update_message_after_experiment, args=(id_queue[0], experiment_status))
                process.start()

    # Switch page function
    @app.callback(
        Output('page-content', 'children'), 
        Input('url', 'pathname')
    )
    def display_page(pathname):
        if pathname == '/input-page':
            return input_content
        elif pathname == '/run-page':
            return run_content
        elif pathname == '/inventory-page':
            # Inventory page elements
            inventory_content = [html.Div([
                html.H1('Inventory'),
                html.Div(children=[dash_table.DataTable(
                    id="inventory-table",
                    columns=[{"name": i, "id": i, "editable": False if i == 'Port' else experiment_status["is_running"] == "Editing inventory"} for i in inventory_df.columns],
                    data=inventory_df.to_dict("records"),
                    style_table={'width': '50%'},
                    style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'},
                    style_cell={'textAlign': 'left', 'padding': '5px'},
                ), 
                html.Button("Edit" if experiment_status["is_running"] != "Editing inventory" else "Save", id="edit-button", className="custom-button", n_clicks=0),
                dbc.Alert(id='inventory-alert', is_open=False, duration=4000)], className='selection-container', style={
                        "display": "flex",                # Use flexbox
                        "justifyContent": "center",       # Center table horizontally
                        "align-items": "center",
                        "flex-direction": "column"
                }), 
                
                dcc.Interval(
                    id="inventory-interval",
                    interval=5000,  # Update every 5 seconds
                    n_intervals=0,
                    disabled=experiment_status["is_running"] == "Editing inventory"
                )
            ])]
            return inventory_content
        elif pathname == '/candidate-page':
            return candidate_content
        elif pathname == '/log-page':
            return log_content
        elif pathname == '/solubility-run-page':
            return test_solubility_content
        elif pathname == '/solubility-database-page':
            return solubility_database_content
        else:
            return home_content



    
    # Functions for measure solubility page
    @callback([Output('solubility-solvent-alert', 'is_open'),
               Output('solubility-solvent-alert', 'children'),
               Output('solubility-salt-alert', 'is_open'),
               Output('solubility-salt-alert', 'children')],
            Input("start-solubility-button", 'n_clicks'), 
              [State('solubility-solvent', "value"), 
               State('solubility-salt', "value")],
              prevent_initial_call=True)
    def start_measure_solubility(n_clicks, value_solvent, value_salt):
        global process
        if n_clicks:
            
            result = verifyCompositionID(None, value_solvent)
            if isinstance(result, str):
                return True, result, False, ''
            contains_salt = result['Salt_molality']['salt'][0]
            if contains_salt != 'None':
                return True, 'Solvents cannot contain salt', False, ''
            check_salt_temp = result['Solvent_mass_percentage']['solvent'][0]
            check_salt = verifyCompositionID(None, f'{check_salt_temp}|100|{value_salt}|1')
            if isinstance(check_salt, str):
                return False, '', True, check_salt
            if experiment_status["is_running"] == "No experiment is running" and experiment_status['result'] == 'No errors':
                experiment_status["is_running"] = "Running experiments"
                process = Process(target=update_message_after_solubility_measurement, args=(value_solvent, value_salt, experiment_status))
                process.start()
            return False, '', False, ''
    
    @callback([Output("Running-status", 'children', allow_duplicate=True),
               Output("Error-message", 'children', allow_duplicate=True)],
            Input("solubility-interval", "n_intervals"),
              prevent_initial_call=True)
    def update_status_solubility(n_intervals):
        return experiment_status['is_running'], experiment_status['result']
    
    # Solubility data page call back functions
    # Read the data in the database and generate the options accordingly. Dynamic according to database
    @app.callback(
        Output('solubility-container', 'children'),
        Input('form-options', 'data')
    )
    def solubility_options(a):
        form_options = get_choices(db_file=SOLUBILITY_DB, dependent=None, independent=SOLUBILITY_INPUT)
        form_elements = []
        for category in form_options:
            column = [html.Label(category['Title'].replace("_", " "), className='custom-label'), 
            dcc.RadioItems(
                id=category['Title'] + '-radio',  # ID for callback reference
                options=[
                    {'label': 'and', 'value': 'and'},
                    {'label': 'or', 'value': 'or'},
                ],
                value='or'  # Default selected value
            )]
            variables = SOLUBILITY_INPUT
            if category['Title'] == 'Dependent variables' or category['Title'] == 'Independent variables':
                for index, row in variables.iterrows():
                    structure = row['Type'].selectstructure(row['Property'])
                    labels.append(row['Property'])
                    if structure:
                        column.append(structure)
                column = html.Form(id=category["Title"], className='column', style={'flex': '1', 'padding': '10px', 'flex-direction': 'row'}, children=column)
            else:
                for label in category['Options']:
                    labels.append(label)
                    checkbox = dcc.Checklist(id=label + '-checkbox', options=[label], labelStyle={"fontSize": "18px", "font-weight": "bold"}, className='custom-checklist', value=[])
                    min_input = dcc.Input(id=label + '-min', type='number', className='custom-textfield', disabled=False, value=None)
                    max_input = dcc.Input(id=label + '-max',type='number', className='custom-textfield', disabled=False, value=None)
                    column += [
                        html.Div([checkbox,

                            # Min input with label
                            dbc.Col([
                                dbc.Row([html.Label('Min:'), min_input])
                            ]),

                            # Max input with label
                            dbc.Col([
                                dbc.Row([html.Label('Max:'), max_input])
                            ]),
                        ])]
                column = html.Form(id=category["Title"], className='column', style={'display': 'flex', 'flex': '1', 'padding': '10px', 'flex-direction': 'column'}, children=column)
            form_elements.append(column)
        return form_elements
    
    @callback(
        [Output('plot-solubility-container', 'children'), Output('displayed-form', 'data', allow_duplicate=True)],
        Input('table-solubility-button', 'n_clicks'), 
        State('solubility-container', 'children'),
        prevent_initial_call=True
    )
    def show_solubility_table(n_clicks, form_elements):
        options, df = generate_options_df(form_elements, db_file=SOLUBILITY_DB)
        df = df.rename(columns=dict(zip(SOLUBILITY_INPUT['Property'], [f'{p} ({u})' for p, u in zip(SOLUBILITY_INPUT['Property'], SOLUBILITY_INPUT['Units']) if u != ''])))
        df.rename(columns={col: f"{col} (g/100mL)" for col in df.columns if "_Solubility" in col}, inplace=True)
        buffer = StringIO()
        df.to_csv(buffer, index=False)
        csv_string = buffer.getvalue()
        return [dash_table.DataTable(
            id='table',
            columns=[{"name": i, "id": i} for i in df.columns],
            data=df.to_dict('records'),
            style_table={'overflowX': 'auto'},
            sort_action="native",
            filter_action="native",
        ), dcc.Download(id="download-table"),
        html.Button('Download', id='download-table-button', className="custom-button", n_clicks=0)], csv_string
    
    # Display the graph with the given filtering criteria
    @app.callback(
        [Output('plot-solubility-container', 'children', allow_duplicate=True), Output('displayed-graphs', 'data', allow_duplicate=True)],
        Input('graph-solubility-button', 'n_clicks'),
        State('solubility-container', 'children'),
        prevent_initial_call=True
    )
    def show_graph_2d(n_clicks, form_elements=None):
        # Extract selected options from form_elements
        options, df = generate_options_df(form_elements, db_file=SOLUBILITY_DB)
        solubility_names = [col for col in df.columns if col.endswith('_Solubility')]
        variable_names = set(df.columns.tolist())
        variable_names.discard('ID')
        return generate_2d_graphs(df, set(solubility_names))
    
    # Display the graph with the given filtering criteria
    @app.callback(
        [Output('plot-solubility-container', 'children', allow_duplicate=True), Output('displayed-graphs', 'data', allow_duplicate=True)],
        Input('graph-solubility-button-3d', 'n_clicks'),
        State('solubility-container', 'children'),
        prevent_initial_call=True
    )
    def show_graph_3d(n_clicks, form_elements=None):
        # Extract selected options from form_elements
        options, df = generate_options_df(form_elements, db_file=SOLUBILITY_DB)
        solubility_names = [col for col in df.columns if col.endswith('_Solubility')]
        variable_names = set(df.columns.tolist())
        variable_names.discard('ID')
        return generate_3d_graphs(df, set(solubility_names))

    # Log page functions
    # The file list and (perhaps) the contents should be updated regularly
    @callback(
        [Output('file-list', 'children', allow_duplicate=True),
        Output('file-content', 'children', allow_duplicate=True),
        Output('log-interval', 'interval')],
        Input('log-interval', 'n_intervals'), 
        State("selected-file", "data"),
        prevent_initial_call=True
    )
    def update_log(n_intervals, selected_file):
        filepath = os.path.join(parent_dir, 'Logs', selected_file)
        file_content = ""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                file_content = f.read()
        children=[
            html.Div(id={'type': 'file_item', 'index': idx}, children=file, className='list-item-selected' if file==selected_file else 'list-item')
            for idx, file in enumerate(get_file_list(os.path.join(parent_dir, "Logs")))
        ]
        if len(children) == 0:
            children=html.Div(children="No log files", className='list-item-unselectable')
        return children, file_content, 1000
        
    # Show the selected file and its contents
    @callback(
        [Output('file-list', 'children', allow_duplicate=True),
        Output('file-content', 'children', allow_duplicate=True),
        Output("selected-file", "data")],
        Input({'type': 'file_item', 'index': ALL}, 'n_clicks'), 
        State('file-list', 'children'),
        prevent_initial_call=True
    )
    def show_file(n_clicks, file_items):
        # Check which div was clicked
        # Find the index of the clicked item
        if not any(n_clicks):
            raise PreventUpdate

        clicked_index = int(callback_context.triggered[0]['prop_id'][9:-29])
        item = file_items[clicked_index]
        filename = item['props']['children']
        selected_file = filename
        result = html.Div(id='file-list', children=[
            html.Div(id={'type': 'file_item', 'index': idx}, children=file, className='list-item-selected' if file==selected_file else 'list-item')
            for idx, file in enumerate(get_file_list(os.path.join(parent_dir, "Logs")))
        ])
        filepath = os.path.join(parent_dir, 'Logs', selected_file)
        file_content = ""
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                file_content = f.read()
        return result, file_content, selected_file

    # Inventory page functions
    # Update the inventory every 5 seconds. The tables will be updated
    @app.callback(
        Output("inventory-table", "data"),
        Input("inventory-interval", "n_intervals")
    )
    def update_table(n):
        # Read the CSV file and convert it to a dictionary format for DataTable
        inventory_df = pd.read_csv(inventory_path)
        return inventory_df.to_dict("records")
    
    # Edit the inventory page
    @app.callback(
        [Output("inventory-table", "columns"), Output("inventory-interval", "disabled"), Output("edit-button", "children"), Output("inventory-alert", "is_open"), Output("inventory-alert", "children")],
        Input("edit-button", "n_clicks"),
        [State("inventory-table", "columns"), State("inventory-table", "data")],
        prevent_initial_call=True
    )
    def update_table(n_clicks, columns, data):
        # Read the CSV file and convert it to a dictionary format for DataTable
        if n_clicks > 0:
            editing = columns[0]['editable']
            if not editing and experiment_status["is_running"] == "No experiment is running":
                experiment_status["is_running"] = "Editing inventory"
                return [{"name": col["name"], "id": col["id"], "editable": col["name"] != "Port"} for col in columns], True, 'Save', False, ''
            elif experiment_status["is_running"] == "Editing inventory":
                df = pd.DataFrame(data)  # Convert Dash Table data to DataFrame
                for current in inventory_types:
                    for i in range(len(df[current])):
                        current_item = df[current][i]
                        verify_result = inventory_types[current].verify(f"Column {current} row {i + 1}", current_item)
                        if isinstance(verify_result, str):
                            return [{"name": col["name"], "id": col["id"], "editable": col["name"] != "Port"} for col in columns], True, 'Save', True, verify_result
                df.to_csv(inventory_path, index=False)
                experiment_status["is_running"] = "No experiment is running"
            return [{"name": col["name"], "id": col["id"], "editable": False} for col in columns], False, 'Edit', False, ''
    
    # Candidate page functions
    # Update the candidate every 5 seconds. The tables will be updated
    @app.callback(
        Output("candidate-table", "data"),
        Input("candidate-interval", "n_intervals"),
        prevent_initial_call=True
    )
    def update_candidate_table(n):
        # Read the CSV file and convert it to a dictionary format for DataTable
        candidate_df = pd.read_csv(candidate_path)
        return candidate_df.to_dict("records")
    
    @app.callback(
        Input("clear-candidate-button", "n_clicks"),
        prevent_initial_call=True
    )
    def clear_candidate_table(n):
        candidate_df = pd.read_csv(candidate_path)
        candidate_df = candidate_df[:0]
        candidate_df.to_csv(candidate_path, index=False)

    # Run page callback functions.
    @app.callback(
        Input("lock-clio", "n_clicks"),
    )
    def lock_clio(n_clicks):
            # Update the message to "Running experiment"
            # Run the experiment in a separate thread to avoid blocking the UI
        global process
        
        if n_clicks and process:
            
            if process.is_alive():
                process.terminate()
                process.join()  # Ensure cleanup
                halt(experiment_status["log_file_name"])
        if experiment_status['is_running'] != "Editing inventory":
            experiment_status['is_running'] = "No experiment is running"
        experiment_status['result'] = 'Clio is locked'
    # Function to manually upload composition into queue. Will use the add-to-queue button and the textfield
    @app.callback(
        [Output('run-input-alert', "children", allow_duplicate=True),
        Output('run-input-alert', "is_open", allow_duplicate=True)],
        Input("start-experiment", "n_clicks"),
        State('compositionID-experiment', "value"), prevent_initial_call=True
    )
    def add_queue(n_clicks, compositionID):
            # Update the message to "Running experiment"
            # Run the experiment in a separate thread to avoid blocking the UI
        global selected_element
        update = 1 <= selected_element and get_queue_length() > selected_element
        result = add_to_queue(compositionID)
        if result == "No errors" and update:
            selected_element += 1
        if result == "No errors":
            return result, False
        return result, True

    # Function called in thread, which runs the experiment and update the status
    

    # Button to delete the selected composition inside the queue
    @app.callback(
        Input("delete-button", "n_clicks"),
        prevent_initial_call=True
    )
    def delete_button(n_clicks):
        if n_clicks:
            if get_queue_length() != selected_element or experiment_status["is_running"] != "Running experiments": # Cannot delete a composition which is in the middle of an experiment
                delete_ith_element(get_queue_length() - selected_element)

    # When Clio runs into an error, it will not continue running the experiment. Click on the button to indicate the error is resolved and Clio will continue doing experiments.
    @app.callback(
        Input("trouble-button", "n_clicks"),
        prevent_initial_call=True
    )
    def resolve_trouble(n_clicks):
            # Update the message to "Running experiment"
            # Run the experiment in a separate thread to avoid blocking the UI
        experiment_status["result"] = "No errors"
        experiment_status["is_running"] = "No experiment is running"

    # Main function to track the status of Clio. Updates every 0.1s. It should update the experiment status and the queue.
    @app.callback(
        [Output("Running-status", "children", allow_duplicate=True),
        Output("Error-message", "children", allow_duplicate=True),
        Output("queue-display", "children", allow_duplicate=True),
        Output("trouble-button", "disabled", allow_duplicate=True),
        Output("Queue-length", "children", allow_duplicate=True)],
        Input("polling-interval", "n_intervals"), 
        prevent_initial_call=True
    )
    def update_experiment_status(n_intervals):
        queue_items = []
        global process
        for i, item in enumerate(list(id_queue)):
            if i == get_queue_length() - selected_element:
                queue_items.append(html.Div(item, className='list-item-selected', id={"type": "item", "index": i}))

            else:
                queue_items.append(html.Div(item, className='list-item', id={"type": "item", "index": i}))
        if len(queue_items) == 0:
            queue_items.append(html.Div('Nothing in queue', className='list-item-unselectable', disable_n_clicks=True))
        if experiment_status["is_running"] != "No experiment is running":
            # Running experiments, no error encountered
            return experiment_status["is_running"], experiment_status["result"], queue_items, True, f'{get_queue_length()} experiments to be done'
        elif len(id_queue) and experiment_status["result"] == "No errors":
            return 'Running experiments', experiment_status["result"], queue_items, True, f'{get_queue_length()} experiments to be done'
        else:
            result_message = experiment_status["result"]
            return "No experiment is running", result_message, queue_items, result_message == "No errors", f'{get_queue_length()} experiments to be done'
    
    @app.callback(
        Output("Running-status", 'children'),
        Input("zero", 'n_clicks'),
        State("Running-status", 'children'),
    )
    def zero_viscometer(n_clicks, current_state):
        global process
        if n_clicks and experiment_status["is_running"] == "No experiment is running" and experiment_status["result"] == "No errors":
            experiment_status["is_running"] = "Zeroing viscometer"
            process = Process(target=update_message_after_zero, args=(experiment_status,))
            process.start()
            return experiment_status["is_running"]
        return current_state
                
    # Callback to select an item when clicked
    @app.callback(
        Input({"type": "item", "index": ALL}, "n_clicks"), 
        prevent_initial_call=True)
    def select_item(n_clicks):
        # Determine which item was clicked by checking n_clicks
        global selected_element
        if any(n_clicks):
            index = [i for i, click in enumerate(n_clicks) if click][0]
            selected_element = get_queue_length() - index # indicates the last but i-1 elements is selected. Why? Because when one ID leaves the queue, the number of compositions after the selected element in the queue will remain the same.
        
    # Upload multiple compositionIDs into the queue
    @app.callback([Output('run-input-alert', "children", allow_duplicate=True),
                Output('run-input-alert', "is_open", allow_duplicate=True),
                Output('upload-file-experiment', "contents")],
            Input('upload-file-experiment', 'contents'),
            State('upload-file-experiment', 'filename'),
            prevent_initial_call=True)
    def upload_experiment_ids(contents, filename):
        global selected_element
        if contents is not None:
            ids = parse_run_ids(contents, filename)
            update = 1 <= selected_element and get_queue_length() > selected_element
            result = add_bulk_to_queue(ids)
            if result == "No errors" and update:
                selected_element += len(ids)
                return result, False, None
            return result, result != "No errors", None

    # Input page callback functions.
    # Upload a piece of record through textfields and the button
    @app.callback(
        [Output('alert', 'children'), Output('alert', 'is_open')],
        Input('add-data-button', 'n_clicks'),
        [State(current[1]['Property'] + '-input', current[1]['Type'].getStructureValue()) for current in ALL_INPUT.iterrows()],
        prevent_initial_call=True
    )
    def input_data(n_clicks, *args):
        #Check the correctness of the input
        compositions = check_validity(args)
        if isinstance(compositions, str):
            return [compositions, True]
        insert_new_data(compositions)
        return ['Data submitted successfully', True]

    # Upload multiple data records into the database.
    @app.callback([Output('file-alert', 'children'), Output('file-alert', 'is_open')],
                Input('upload-file', 'contents'),
                State('upload-file', 'filename'),
                prevent_initial_call=True)
    def update_output(contents, filename):
        if contents is not None:
            children = parse_contents(contents, filename)
            return [children, True]
        
    # Delete a piece of record with given ID
    @app.callback([Output('delete-alert', 'is_open'), Output('delete-alert', 'children')],
                Input('delete-record', 'n_clicks'),
                State('delete', 'value'),
                prevent_initial_call=True)
    def delete_record(n_clicks, value):
        try:
            if len(value) != 64:
                return True, 'Please enter a valid data ID'
            bytes.fromhex(value)
            delete_data(value)
            return True, 'Data deleted successfully'
        except Exception as e:
            return True, 'Please enter a valid data ID'
        
    # Delete multiple data record.
    @app.callback([Output('delete-file-alert', 'is_open'), Output('delete-file-alert', 'children')],
                Input('upload-delete-file', 'contents'),
                State('upload-delete-file', 'filename'),
                prevent_initial_call=True)
    def delete_records(contents, filename):
        if contents is not None:
            children = parse_contents_delete(contents, filename)
            return [True, children]

    # Home page call back functions
    # Read the data in the database and generate the options accordingly. Dynamic according to database
    @app.callback(
        Output('container', 'children'),
        Input('form-options', 'data')
    )
    def generate_options(a):
        form_options = get_choices()
        form_elements = []
        for category in form_options:
            column = [html.Label(category['Title'].replace("_", " "), className='custom-label'), 
            dcc.RadioItems(
                id=category['Title'] + '-radio',  # ID for callback reference
                options=[
                    {'label': 'and', 'value': 'and'},
                    {'label': 'or', 'value': 'or'},
                ],
                value='or'  # Default selected value
            )]
            variables = PROPERTY if category['Title'] == 'Dependent variables' else INPUT
            if category['Title'] == 'Dependent variables' or category['Title'] == 'Independent variables':
                for index, row in variables.iterrows():
                    structure = row['Type'].selectstructure(row['Property'])
                    labels.append(row['Property'])
                    if structure:
                        column.append(structure)
                column = html.Form(id=category["Title"], className='column', style={'flex': '1', 'padding': '10px', 'flex-direction': 'row'}, children=column)
            else:
                for label in category['Options']:
                    labels.append(label)
                    checkbox = dcc.Checklist(id=label + '-checkbox', options=[label], labelStyle={"fontSize": "18px", "font-weight": "bold"}, className='custom-checklist', value=[])
                    min_input = dcc.Input(id=label + '-min', type='number', className='custom-textfield', disabled=False, value=None)
                    max_input = dcc.Input(id=label + '-max',type='number', className='custom-textfield', disabled=False, value=None)
                    column += [
                        html.Div([checkbox,

                            # Min input with label
                            dbc.Col([
                                dbc.Row([html.Label('Min:'), min_input])
                            ]),

                            # Max input with label
                            dbc.Col([
                                dbc.Row([html.Label('Max:'), max_input])
                            ]),
                        ])]
                column = html.Form(id=category["Title"], className='column', style={'display': 'flex', 'flex': '1', 'padding': '10px', 'flex-direction': 'column'}, children=column)
            form_elements.append(column)
        return form_elements

    # Read the selected options
    def generate_options_df(form_elements, db_file=DEFAULT_DB):
        options = {}
        for current in form_elements:
            # Logic to extract the eselected elements within the given structure
            current_column = current['props']['children']
            column_name = current_column[0]['props']['children']
            options[column_name] = {LOGIC:current_column[1]['props']['value']}
            for i in range(2, len(current_column)):
                current_variable = current_column[i]
                current_structure = current_variable['props']['children']
                if current_structure[0]['props']['value']:
                    current_label = current_structure[0]['props']['value'][0]
                    options[column_name][current_label] = {}

                    if len( ALL_INPUT.loc[ALL_INPUT['Property'] == current_label, 'Type'].values) > 0:
                        current_type = ALL_INPUT.loc[ALL_INPUT['Property'] == current_label, 'Type'].values[0]
                        min_value = current_type.verify(current_label, current_structure[1]['props']['children'][1]['props'][current_type.structureValue])
                        options[column_name][current_label]['min'] = None if isinstance(min_value, str) else min_value
                        max_value = current_type.verify(current_label, current_structure[1]['props']['children'][3]['props'][current_type.structureValue])
                        options[column_name][current_label]['max'] = None if isinstance(max_value, str) else max_value
                    else:
                        options[column_name][current_label]['min'] = current_structure[1]['props']['children'][0]['props']['children'][1]['props']['value']
                        options[column_name][current_label]['max'] = current_structure[2]['props']['children'][0]['props']['children'][1]['props']['value']
        df = generate_df(options, db_file)
        return options, df

    # Display table with the given filter criteria
    @app.callback(
        [Output('plot-container', 'children', allow_duplicate=True), Output('displayed-form', 'data', allow_duplicate=True)],
        Input('table-button', 'n_clicks'),
        [State('container', 'children')],
        prevent_initial_call=True
    )
    def show_table(n_clicks, form_elements):
        # Extract selected options from form_elements
        options, df = generate_options_df(form_elements)
        if 'ExperimentID' in df.columns:
            df['ExperimentID'] = df['ExperimentID'].apply(lambda x: binascii.hexlify(x).decode('utf-8'))
        buffer = StringIO()
        def merge(property, unit):
            return f'{property} ({unit})'
        df = df.rename(columns=dict(zip(ALL_INPUT['Property'], [f'{p} ({u})' for p, u in zip(ALL_INPUT['Property'], ALL_INPUT['Units']) if u != ''])))
        df.to_csv(buffer, index=False)
        csv_string = buffer.getvalue()
        columns = []
        for current in df.columns:
            if pd.api.types.is_numeric_dtype(df[current]):
                # numeric → format with 2 decimals (you can switch to 3 sig figs if needed)
                columns.append({
                    "name": current,
                    "id": current,
                    "type": "numeric",
                    "format": Format(precision=2, scheme=Scheme.fixed)
                })
            else:
                # non-numeric → no formatting
                columns.append({"name": current, "id": current})
        return [html.Div(children=[dash_table.DataTable(
            id='table',
            columns=columns,
            data=df.to_dict('records'),
            sort_action="native",  # Enable native sorting
            filter_action="native",  # Enable native filtering
            style_table={"overflowX": "auto", 'margin':'auto'}), 
        dcc.Download(id="download-table"),
        html.Button('Download', id='download-table-button', className="custom-button", n_clicks=0)]), csv_string]

    # Function to download the table
    @app.callback(
        Output("download-table", "data"),
        Input('download-table-button', "n_clicks"),
        State('displayed-form', 'data'),
        prevent_initial_call=True
    )
    def download_table(n_clicks, data):
        csv_bytes = io.BytesIO(data.encode())
        return dcc.send_bytes(csv_bytes.getvalue(), "exported_data.csv")
    
    def replace_last(input_string, last, subsistute):
        # Find the index of the last occurrence of '_'
        last_index = input_string.rfind(last)
        
        # If '_' is found, replace it with '<br>'
        if last_index != -1:
            input_string = input_string[:last_index] + subsistute + input_string[last_index+1:]
        
        return input_string

    # Display the graph with the given filtering criteria
    @app.callback(
        [Output('plot-container', 'children', allow_duplicate=True), Output('displayed-graphs', 'data', allow_duplicate=True)],
        Input('graph-button', 'n_clicks'),
        State('container', 'children'),
        prevent_initial_call=True
    )
    def show_graph(n_clicks, form_elements=None):
        # Extract selected options from form_elements
        options, df = generate_options_df(form_elements)
        return generate_2d_graphs(df, set(PROPERTY['Property']))

    def generate_2d_graphs(df, dependent_variables, discard={'ID'}):
        variable_names = set(df.columns.tolist())
        for current in discard:
            variable_names.discard(current)
        properties = set()
        for current in variable_names:
            if current in set(dependent_variables):
                properties.add(current)
        for current in properties:
            variable_names.discard(current)
        variable_names = list(variable_names)
        properties = list(properties)
        if len(variable_names) < 1:
            return html.Div('Please select at least one independent variables.'), []
        result = []
        hover_template_parts = [f"{current}: %{{customdata[{i}]}}" for i, current in enumerate(properties)]
        hover_template = '<br>'.join(hover_template_parts) + '<extra></extra>'
        property_minmax = {}
        for current in properties:
            for variable_name in variable_names:
                if len(df[current]) > 1:
                    property_minmax[current] = [min(df[current]), max(df[current])]
                elif len(df[current]) == 1:
                    property_minmax[current] = [min(df[current]) - 1, max(df[current]) + 1]
                else:
                    property_minmax[current] = [0, 1]
                property_minmax[current].append(property_minmax[current][1] - property_minmax[current][0])
                result += [px.scatter(df, x=variable_name, y=current)]
        for current in result:
            property = current.layout.yaxis.title.text
            variable_name = current.layout.xaxis.title.text
            current.update_traces(customdata=df[properties].to_numpy(), 
                    hovertemplate=
                        variable_name + ': %{x}<br>' +
                         hover_template
                    )
            current.update_layout(
                        title=dict(
                            text=f"2D Scatter Plot of<br>{property} vs {variable_name}",
                            font=dict(size=18),  # Adjust font size
                            x=0.5,  # Center horizontally
                            xanchor="center"  # Ensure proper centering
                        ),
                        scene=dict(
                            yaxis=dict(range=[property_minmax[property][0] - MARGIN * property_minmax[property][2], 
                            property_minmax[property][1] + MARGIN * property_minmax[property][2]])
                        ),
                        height=IMAGE_HEIGHT,
                    )
        sliced_result = [[] for _ in range(GRAPH_COLUMNS)]
        for i in range(len(result)):
            sliced_result[i % GRAPH_COLUMNS].append(result[i])
            
        return [html.Div([html.Div(children=[html.Div(children=dcc.Graph(figure=i), className='graph-container') for i in j], 
                style={'display': 'flex', 'flex-direction': 'column', 'width': f'{100 / GRAPH_COLUMNS}%', 'height':'auto'})
                for j in sliced_result], style={'overflowX': 'auto', 'display': 'flex', 'flex-direction': 'row'}), 
                html.Button('Download All', id='download-graph-button', className="custom-button", style={"width": "150px"}, n_clicks=0)], [fig.to_plotly_json() for fig in result]
    
    # Display the graph with the given filtering criteria
    @app.callback(
        [Output('plot-container', 'children', allow_duplicate=True), Output('displayed-graphs', 'data', allow_duplicate=True)],
        Input('graph-button-3d', 'n_clicks'),
        State('container', 'children'),
        prevent_initial_call=True
    )
    def show_graph_3d(n_clicks, form_elements=None):
        # Extract selected options from form_elements
        options, df = generate_options_df(form_elements)
        return generate_3d_graphs(df, set(PROPERTY['Property']))
            
    def generate_3d_graphs(df, dependent_variables, discard={'ID'}):
        variable_names = set(df.columns.tolist())
        for current in discard:
            variable_names.discard(current)
        properties = set()
        for current in variable_names:
            #if current in set(PROPERTY['Property']):
            if current in set(dependent_variables):
                properties.add(current)
        for current in properties:
            variable_names.discard(current)
        variable_names = list(variable_names)
        properties = list(properties)
        if len(variable_names) < 2:
            return html.Div('Please select at least two independent variables.'), []
        result = []
        hover_template_parts = [f"{current}: %{{customdata[{i}]}}" for i, current in enumerate(properties)]
        hover_template = '<br>'.join(hover_template_parts) + '<extra></extra>'
        property_minmax = {}
        for current in properties:
            if len(df[current]) > 1:
                    property_minmax[current] = [min(df[current]), max(df[current])]
            elif len(df[current]) == 1:
                property_minmax[current] = [min(df[current]) - 1, max(df[current]) + 1]
            else:
                property_minmax[current] = [0, 1]
            property_minmax[current].append(property_minmax[current][1] - property_minmax[current][0])
        for i in range(len(variable_names)):
            for j in range(i + 1, len(variable_names)):
                new = [px.scatter_3d(df, x=df[variable_names[i]], y=df[variable_names[j]], z=k) for k in properties]
                for current, property in zip(new, properties):
                    title_text = f"3D Scatter Plot of {property} vs<br>{variable_names[i]} vs {variable_names[j]}"
                    current.update_traces(customdata=df[properties].to_numpy(), 
                    hovertemplate=
                        variable_names[i] + ': %{x}<br>' +
                        variable_names[j] + ': %{y}<br>' +
                        hover_template,
                    marker=dict(size=5, opacity=0.8),
                    )
                    current.update_layout(
                        title=dict(
                            text=title_text,
                            font=dict(size=18),  # Adjust font size
                            x=0.5,  # Center horizontally
                            y= 0.85,
                            xanchor="center"  # Ensure proper centering
                        ),
                        scene=dict(
                            xaxis=dict(title=replace_last(variable_names[i], '_', '<br>')),
                            yaxis=dict(title=replace_last(variable_names[j], '_', '<br>')),
                            zaxis=dict(range=[property_minmax[property][0] - MARGIN * property_minmax[property][2], 
                            property_minmax[property][1] + MARGIN * property_minmax[property][2]], tickmode='array',
                            tickvals=np.linspace(np.round(property_minmax[property][0], 1), 
                                               np.round(property_minmax[property][1], 1), 6))
                        ),
                        scene_camera=dict(eye=dict(x=1.7, y=1.7, z=2)),
                        margin=dict(l=10, r=10, t=30, b=10),
                        height=IMAGE_HEIGHT,
                    )
                    # current.write_image(title_text.replace('<br>', ' ') + '.png', scale=6)
                result += new
        sliced_result = [[] for _ in range(GRAPH_COLUMNS)]
        for i in range(len(result)):
            sliced_result[i % GRAPH_COLUMNS].append(result[i])
            
        return [html.Div([html.Div(children=[html.Div(children=dcc.Graph(figure=i), className='graph-container') for i in j], 
                style={'display': 'flex', 'flex-direction': 'column', 'width': f'{100 / GRAPH_COLUMNS}%', 'height':'auto'})
                for j in sliced_result], style={'overflowX': 'auto', 'display': 'flex', 'flex-direction': 'row'}), 
                html.Button('Download All', id='download-graph-button', className="custom-button", style={"width": "150px"}, n_clicks=0)], [fig.to_plotly_json() for fig in result]

                

    @app.callback(
        Input('download-graph-button', "n_clicks"),
        State('displayed-graphs', 'data'),
        prevent_initial_call=True
    )
    def download_graph(n_clicks, data):
        home_directory = os.path.expanduser("~")
        downloads_folder = os.path.join(home_directory, "Downloads")
        for current in data:
            fig = go.Figure(current)
            path = os.path.join(downloads_folder, fig.layout.title.text.replace('<br>', ' ') + '.png')
            fig.write_image(path, scale=6)

    if __name__ == '__main__':
        app.run(debug=True, dev_tools_props_check=False)