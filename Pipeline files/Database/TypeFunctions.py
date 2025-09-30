import datetime
import pandas as pd
import numpy as np
from dash import Dash, dash_table, html, dcc
import dash_bootstrap_components as dbc
import os

current_file_dir = os.path.dirname(os.path.abspath(__file__))
solvent_molar_mass_table = pd.read_csv(os.path.join(current_file_dir, 'Solvent Molar mass.csv'))
salt_molar_mass_table = pd.read_csv(os.path.join(current_file_dir, 'Salt Molar mass.csv'), na_values=[], keep_default_na=False)
solvent_molar_mass = {}
for index, row in solvent_molar_mass_table.iterrows():
    solvent_molar_mass[row['Solvent']] = row['Molar_mass']
salt_molar_mass = {}
for index, row in salt_molar_mass_table.iterrows():
    salt_molar_mass[row['Salt']] = row['Molar_mass']

def getverifyNumberFunction(min, max, integer=False):
    def result(property, number):
        if number == None:
            return None
        try:
            number = int(number) if integer else float(number)
        except ValueError:
            return f'{property} must be a number!'
        if number < min:
            return f'{property} must be greater than {min}!'
        elif number > max:
            return f'{property} must be less than {max}!'
        elif integer and not isinstance(number, int):
            return f'{property} must be integer!'
        return number
    return result

def verifyCompositionID(property, str):
    # Check compositionID
    error_comp_id = 'Please enter a valid composition ID.'
    if str==None:
        return error_comp_id
    splitted_string = str.split('|')
    if len(splitted_string) != 4:
        return error_comp_id
    solvents = splitted_string[0].split('_')
    percentage = splitted_string[1].split('_')
    if len(solvents) != len(percentage):
        return error_comp_id
    
    molar_ratio = []
    for i in range(len(percentage)):
        if solvents[i] not in solvent_molar_mass:
            return f"No solvents named {solvents[i]} is found."
        try:
            percentage[i] = float(percentage[i])
        except ValueError:
            return error_comp_id
        if percentage[i] <= 0:
            return error_comp_id
        molar_ratio.append(percentage[i] / solvent_molar_mass[solvents[i]])
    if abs(sum(percentage) - 100) > 1E-10:
           return 'Percentages of solvents must sum up to 100.'
    salts = splitted_string[2].split('_')
    molality = splitted_string[3].split('_')
    if len(salts) != len(molality):
        return error_comp_id
    for i in range(len(molality)):
        if salts[i] not in salt_molar_mass:
            return f"No salts named {salts[i]} is found."
        molar_ratio.append(float(molality[i]) / 10)
        try:
            molality[i] = float(molality[i])
        except ValueError:
            return error_comp_id
        if percentage[i] <= 0:
            return error_comp_id
    
    molar_ratio = np.array(molar_ratio) / sum(molar_ratio)
    return {'Solvent_mass_percentage': {'solvent':solvents, 'mass_percentage':percentage}, 'Salt_molality': {'salt':salts, 'molality':molality}, 
    'Solvent_molar_ratio':{'solvent':solvents, 'molar_ratio':molar_ratio[0:len(solvents)]},
    'Salt_molar_ratio':{'salt':salts, 'molar_ratio':molar_ratio[len(solvents):]}}

def getVerifyDateFunction(allowed_formats):
    def verifyDate(property, date_string):
        #epoch = datetime.datetime(1970, 1, 1, 0, 0, 0)
        for input_format in allowed_formats:
            try:
                date_obj = datetime.datetime.strptime(date_string.split(" ")[0], input_format)
                return date_obj
            except ValueError as e:
                pass
        return f'{property} must be in MM/DD/YY format!'
    return verifyDate

def getNumberInput(id):
    return dcc.Input(id=id, type='number', className='custom-textfield', value=None), 'value'

def getStringInput(id):
    return dcc.Input(id=id, type='text', className='custom-textfield', value=None), 'value'

def getDateInput(id):
    return dcc.Input(id=id, type='datetime-local', className='custom-textfield', value=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), step="1"), 'value'

def getNumberFilter(id):
    return html.Div([
        # Checkbox
        dcc.Checklist(
            id=id + '-checkbox',
            options=[id],
            labelStyle={"fontSize": "18px", "font-weight": "bold"},
            value=[],
        ),

        # Input with label
        dbc.Col([
            html.Label('Min:'),
            dcc.Input(
                id=id + '-min',
                type='number',
                disabled=False,
                className='custom-textfield', 
                value=None
            ),
            html.Label('Max:'), dcc.Input(
                id=id + '-max',
                type='number',
                disabled=False,
                className='custom-textfield', 
                value=None
            )
        ]),
    ])

def getDateFilter(id):
    return html.Div([
        # Checkbox
        dcc.Checklist(
            id=id + '-checkbox',
            options=[id],
            labelStyle={"fontSize": "18px", "font-weight": "bold"},
            value=[],
        ),

        # Input with label
        html.Div(children=[html.Label('From:'), dcc.Input(id=id + '-min', type='datetime-local', className='custom-textfield', step="1", value=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')),
            html.Label('To:'), dcc.Input(id=id + '-max', type='datetime-local', className='custom-textfield', step="1", value=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'))
            ], style={'display':'flex', 'flex-direction': 'column'})

    ])

def displayDate(day):
    return day.replace(microsecond=0)