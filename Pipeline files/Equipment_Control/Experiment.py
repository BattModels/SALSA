from enum import Enum
import time
from datetime import datetime
import logging
import serial
import hid
import pandas as pd
import os
import winsound
import cv2
try:
    from Pump import terminate_pump, flow, Mode, State1, State2
    from Valve import switch_valve
    from Relay import State3Way, switch_3way_valve, close_all
    from Balance import measure_mass
    from Potentiostat import measure_conductivity, CELL_CONSTANT, check_connection
    from Thermometer import measure_temperature, is_logging
    from Viscometer import measure_viscosity, zero, stop
    from CandidateManager import *
    from MixingSolver import find_specific_components
    from Camera import take_picture
    from Classifier import classify
    from Utils import *
except Exception as e:
    from .Pump import terminate_pump, flow, Mode, State1, State2
    from .Valve import switch_valve
    from .Relay import State3Way, switch_3way_valve, close_all
    from .Balance import measure_mass
    from .Potentiostat import measure_conductivity, CELL_CONSTANT, check_connection
    from .Thermometer import measure_temperature, is_logging
    from .Viscometer import measure_viscosity, zero, stop
    from .CandidateManager import *
    from .MixingSolver import find_specific_components
    from .Camera import take_picture
    from .Classifier import classify
    from .Utils import *

time_adjust = -0.143
flow_rate_adjust = 1
# Get the directory of the inventory path, which will be modified during experiment.
INVENTORY_PATH = os.path.abspath(os.path.join(current_dir, "Inventory.csv"))
inventory_df = pd.read_csv(INVENTORY_PATH)
solvent_density = {}

'''Main method to conduct experiment. 
# An experiment has three major components: priming, experimenting, and rinsing. 
# Experiments start by priming all electrolyte required into the whole system before entering the sonicator, which will be into the waste.
# Then, it will actually pump the electrolytes into the sonicator.
# After that, prime some mixed electrolytes from the sonicator into the meausring the system. Primed electrolytes goes into waste.
# Then, pump the electrolytes into the potentiostat, balance, and viscometer, respectively.
# Finally, rinse the whole system (before and after the sonicator) with ACN'''
def experiment(composition, bottles, candidate_pos, log_file_name, trial_num=1, zero_viscometer=False, close=False):
    global inventory_df
    
    result = {'Volume':BALANCE_VOLUME}
    logger = logging.getLogger()
    
    # Remove any existing handlers (close the previous log file)
    try:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()
    except Exception as e:
        pass
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=os.path.join(current_dir, '..', 'Logs', log_file_name), filemode='a')
    # Priming, and mixing
    check_connection()
    check_serial(serial_array)
    check_hid([path_3way, path_2way, path_thermometer])
    logging.info(f"Starting priming and mixing composition {composition}:")
    prime_rate = FLOW_RATE * 1E6
    balance_prime_rate = BALANCE_FLOW_RATE * 1E6
    if not is_logging(path_thermometer):
        logging.error('Thermometer is not logging')
        raise BufferError('Thermometer is not logging')
    if trial_num <= 0:
        acn_port = find_specific_components("ACN|100|None|0", RINSE_VOLUME)
        switch_valve_by_num(acn_port, log_file_name)
        logging.info(f"Pumping {RINSE_VOLUME}mL from bottle {acn_port}")
        pump_control(Pumppos.VALVE, RINSE_VOLUME, prime_rate, log_file_name, bottle_pos=acn_port)
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.POTENTIOSTAT)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, POTENTIOSTAT_RINSE_VOLUME, prime_rate, log_file_name)
        pump_control(Pumppos.SONICATOR, POTENTIOSTAT_RINSE_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, TOTAL_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name)

    make_solvent(bottles, prime_rate, log_file_name)
    time.sleep(REST_TIME)    
    
    # Measure the mass before liquid dropped into the balance
    
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.BALANCE)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, BALANCE_PRIME_VOLUME, balance_prime_rate, log_file_name)
    mass1 = measure_mass(balance_port, 9600, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, BALANCE_VOLUME, balance_prime_rate, log_file_name)

    # Balance should be stablized.
    time.sleep(2)
    mass2 = measure_mass(balance_port, 9600, log_file_name=log_file_name)
    logging.info(f"Total mass: {mass2 - mass1}g")
    result['Mass'] = mass2 - mass1
    result['Density'] = result['Mass'] / result['Volume']
    if result['Density'] < DENSITY_TOLERANCE_FACTOR[0] * TOTAL_VOLUME or result['Density'] > DENSITY_TOLERANCE_FACTOR[1] * TOTAL_VOLUME:
        raise BufferError(f'Dubious density measurement result: {result["Density"]}g/ml.')
    pump_control(Pumppos.SONICATOR, BALANCE_PRIME_VOLUME, prime_rate, log_file_name, counterclockwise=True)

    # Measure conductivity, find the line for best fit
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.POTENTIOSTAT)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, POTENTIOSTAT_VOLUME, prime_rate, log_file_name)
    logging.info(f"Starting measuring:")
    result['Resistance'] = measure_conductivity_multiple(5, log_file_name)
    logging.info(f"Measured resistance: {result['Resistance']}ohm.")
    result['Conductivity'] = 1000 * CELL_CONSTANT / (result['Resistance'] - CELL_BIAS)
    pump_control(Pumppos.SONICATOR, POTENTIOSTAT_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)

     # Measure the viscosity
    if zero_viscometer:
        zero(viscometer_port, log_file_name=log_file_name)
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.VISCOMETER)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, VISCOMETER_VOLUME + PRIME_VOLUME_SONICATOR, prime_rate, log_file_name)
    result['Viscosity'] = measure_viscosity(VISCOMETER_RPM, VISCOSITY_STABLE, viscometer_port, log_file_name=log_file_name)[0]
    pump_control(Pumppos.SONICATOR, (VISCOMETER_VOLUME + PRIME_VOLUME_SONICATOR) * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)

    result['Temperature'] = measure_temperature(path_thermometer, log_file_name=log_file_name)
    # Finished, drop the sample, either into bottles or waste.
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)

    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, TOTAL_VOLUME + PRIME_VOLUME_SONICATOR, prime_rate, log_file_name)
    
    '''
    #Rinse the system before sonicator
    logging.info(f"Starting rinsing:")
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.SONICATOR)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    logging.info(f"Rinsing {RINSE_VOLUME}mL from bottle {ACN}")
    switch_valve_by_num(ACN, log_file_name)
    pump_control(Pumppos.VALVE, RINSE_VOLUME, prime_rate, log_file_name, bottle_pos=ACN)

    

    # Rinse the system after the sonicator
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.SONICATOR)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
    valve_instructions += generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.VISCOMETER)
    pump_control(Pumppos.SONICATOR, RINSE_VOLUME, prime_rate, log_file_name)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    switch_valve(end_valve_port, baud_rate, NUM_END, log_file_name)
    pump_control(Pumppos.SONICATOR, RINSE_VOLUME, prime_rate, log_file_name, counterclockwise=True)
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    pump_control(Pumppos.SONICATOR, RINSE_VOLUME, prime_rate, log_file_name)
    '''

    # Close all valves
    if close:
        close_all(path_3way, log_file_name=log_file_name)
    
    logging.info(f"Making composition {composition} has completed!")
    #raise BufferError('Please ignore this email.')
    return result

def measure_solubility(bottles, solvent_compositionID, log_file_name, step_volume = 0.5):
    inventory_df = pd.read_csv(INVENTORY_PATH)
    prev2 = 1
    prev1 = 1
    prime_rate = FLOW_RATE * 1E6
    dissolved = False
    solid_mass = 0
    total_solvent = 0
    volume_limit = TOTAL_VOLUME * 0.8
    mass_temp = None
    solvent_mass = 0
    total_mass = 0
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.BALANCE)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    retry_limit = 5
    
    while retry_limit > 0:
        make_solvent(bottles, prime_rate, log_file_name)
        if solid_mass < MIN_SOLID_MASS:
            while solid_mass < MIN_SOLID_MASS:
            #Doze solid
                if mass_temp is None:
                    mass_temp = measure_mass(balance_port, 9600, log_file_name=log_file_name)
                valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, RelayPos.SOLIDOZER)
                switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
                time.sleep(DISPENSE_TIME)
                valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, RelayPos.SOLIDOZER)
                switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
                # Maybe another balance is required.
                total_mass = measure_mass(balance_port, 9600, log_file_name=log_file_name)
                solid_mass = total_mass - mass_temp
                logging.info(f'Total solid: {solid_mass}g.')

            pump_control(Pumppos.SONICATOR, BALANCE_TUBE_VOLUME, 5E6, log_file_name, counterclockwise=True)
            pump_control(Pumppos.SONICATOR,SOLUBILITY_BURN_IN_VOLUME, 5E6, log_file_name)
            total_solvent += SOLUBILITY_BURN_IN_VOLUME
            solvent_mass = measure_mass(balance_port, 9600, log_file_name=log_file_name) - total_mass
            logging.info(f'Total solvent mass: {solvent_mass}g.')
        pump_control(Pumppos.SONICATOR, BALANCE_TUBE_VOLUME, 5E6, log_file_name)
        solvent_mass = measure_mass(balance_port, 9600, log_file_name=log_file_name) - total_mass
        logging.info(f'Total solvent mass: {solvent_mass}g.')
        while total_solvent < volume_limit:
            print(f'Total solvent: {total_solvent}, volume limit: {volume_limit}')
            pump_control(Pumppos.SONICATOR, step_volume, prime_rate, log_file_name, counterclockwise=False)
            solvent_mass = measure_mass(balance_port, 9600, log_file_name=log_file_name) - total_mass
            logging.info(f'Total solvent mass: {solvent_mass}g.')
            '''
            valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, RelayPos.MIX_MOTOR)
            switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
            time.sleep(SOLUBILITY_MIX_TIME)
            valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, RelayPos.MIX_MOTOR)
            switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
            time.sleep(REST_TIME)
            '''
            for i in range(SOLUBILITY_STIR_ITERATIONS):
                valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, RelayPos.MIX_MOTOR)
                switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
                time.sleep(5)
                valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, RelayPos.MIX_MOTOR)
                switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
                time.sleep(0.5)
            time.sleep(2.5)
            # Capture photos
            take_picture(log_file_name) # Burn in first image
            frame = take_picture(log_file_name)
            classify_result = classify(frame, log_file_name, threshold=1.1, bias='Sediment')
            if isinstance(classify_result, str):
                return classify_result
            class_result = classify_result['result']
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            cv2.imwrite(f'{timestamp}-{class_result}.jpg', frame)
            dissolved = classify_result['result'] == 'Clear'
            if classify_result['confidence'] < 0.5:
                dissolved = True
                total_solvent -= step_volume * 2
            else:
                prev2 = prev1
                prev1 = classify_result['confidence']
            total_solvent += step_volume
            temperature = measure_temperature(path_thermometer, log_file_name)
            if dissolved:
                valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
                mask = inventory_df['CompositionID'].str.contains(solvent_compositionID, case=False, na=False)
                # If any match found, get the first one
                if mask.any():
                    first_match = inventory_df[mask].iloc[0]
                    density = first_match['Density (g/mL)']
                    total_solvent = solvent_mass / density
                switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
                logging.info(f"Measured temperature: {temperature} C.")
                logging.info(f"Measured solubility: {solid_mass * 100 / total_solvent} g/100mL.")
                return {'Temperature': temperature, 'Solubility': solid_mass * 100 / total_solvent, 'Dissolved': 1}
        pump_control(Pumppos.SONICATOR, BALANCE_TUBE_VOLUME, 5E6, log_file_name, counterclockwise=True)
        retry_limit -= 1
        volume_limit += TOTAL_VOLUME * 0.8
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
    switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
    logging.info(f"Measured temperature: {temperature} C.")
    logging.info(f"Cannot fully dissolve with {total_solvent}mL.")
    return {'Temperature': temperature, 'Solubility': solid_mass * 100 / total_solvent, 'Dissolved': 0}
    


def make_solvent(bottles, prime_rate, log_file_name):
    for j in range(0, len(bottles)):
        current = bottles[j]
        amount = current[2]
        i = current[1] + 1
        if amount > 0:
            valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.SONICATOR)
            switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
            logging.info(f"Priming {PRIME_VOLUME_VALVE}mL from bottle {i}")
            switch_valve_by_num(i, log_file_name)
            # Valve code
            pump_control(Pumppos.VALVE, PRIME_VOLUME_VALVE, prime_rate, log_file_name, bottle_pos=i)
            logging.info(f"Pumping {amount}mL from bottle {i}")
            valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.SONICATOR)
            switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
            
            if j >= len(bottles):
                amount += SONICATOR_TUBE_VOLUME
                
            pump_control(Pumppos.VALVE, amount, prime_rate, log_file_name, bottle_pos=i)
    
    switch_valve_by_num(WASTE, log_file_name)
    pump_control(Pumppos.VALVE, SONICATOR_TUBE_VOLUME * 12, prime_rate, log_file_name, counterclockwise=True)

    valve_instructions = generate_switch_valve_3way_instructions(State3Way.ON, RelayPos.SONICATOR)
    switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
    time.sleep(MIX_TIME)
    valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, RelayPos.SONICATOR)
    switch_3way_valve(path_2way, valve_instructions, log_file_name=log_file_name)
    
    
# Helper method to initialize, including zeroing the viscometer
def initialize(log_file_name):
    try:
        close_all(path_3way, log_file_name=log_file_name)
    except Exception as e:
        pass
    try:
        close_all(path_2way, log_file_name=log_file_name)
    except Exception as e:
        pass

def zeroVis(log_file_name):
    try:
        zero(viscometer_port, baud_rate=9600, log_file_name=log_file_name)
    except Exception as e:
        print(str(e))

def clean_up(log_file_name):
    try:
        prime_rate = FLOW_RATE * 1E6
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.SONICATOR)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.BALANCE)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, BALANCE_PRIME_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.BALANCE)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.POTENTIOSTAT)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, POTENTIOSTAT_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.ON, Valve3Waypos.VISCOMETER)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, VISCOMETER_VOLUME * BACK_DIRECTION_FACTOR, prime_rate, log_file_name, counterclockwise=True)
        valve_instructions = generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.SONICATOR)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.POTENTIOSTAT)
        valve_instructions += generate_switch_valve_3way_instructions(State3Way.OFF, Valve3Waypos.VISCOMETER)
        switch_3way_valve(path_3way, valve_instructions, log_file_name=log_file_name)
        pump_control(Pumppos.SONICATOR, TOTAL_VOLUME, prime_rate, log_file_name)
    except Exception as e:
        print(str(e))

def measure_conductivity_multiple(n, log_file_name):
    result = []
    for i in range(n):
        result.append(measure_conductivity(method_file, log_file_name))
        '''
    total = sum(result)
    if n > 2:
        total -= max(result) + min(result)
        return total / (n - 2)
    else:
        return total / n'''
    return min(result)

# Helper method to switch 10-port valves to the correct position with the given bottle number
def switch_valve_by_num(bottle_num, log_file_name):
    instructions = []
    current = 0
    while bottle_num >= NUM_BOTTLES and len(instructions) < NUM_VALVES:
        instructions.append((valve_ports[current], baud_rate, NUM_BOTTLES, current))
        bottle_num -= NUM_BOTTLES - 1
        current += 1
    if current < len(valve_ports):
        instructions.append((valve_ports[current], baud_rate, bottle_num, current))
    else:
        instructions.append((valve_ports[current - 1], baud_rate, NUM_BOTTLES, current))
    for current_instruction in instructions:
        logging.info(f"Connecting to 10-port valve {current_instruction[3]}")
        switch_valve(current_instruction[0], current_instruction[1], current_instruction[2], log_file_name)

# Helper method to control the pump prime with the given volume and speed. Starting and stopping the pump should be in one method
def pump_control(pumppos, volume, prime_rate, log_file_name, bottle_pos=0, counterclockwise=False):
    logging.info(f"Pumping {volume}mL from {pumppos.name} takes {volume / (prime_rate / 1E6) * 60} seconds")
    inventory_df = pd.read_csv(INVENTORY_PATH)
    state2 = State2.COUNTER_CLOCKWISE
    if counterclockwise:
        state2 = State2.CLOCKWISE
    if bottle_pos:
        new_inventory = inventory_df.loc[inventory_df['Port'] == bottle_pos, 'Volume (mL)'] - volume
        inventory_df.loc[inventory_df['Port'] == bottle_pos, 'Volume (mL)'] = new_inventory
        inventory_df.to_csv(INVENTORY_PATH, index=False)
    time_to_sleep = max((volume / (prime_rate / 1E6) * 60 + time_adjust) * flow_rate_adjust, 0)
    start_time = time.time()
    flow(Mode.SET_FLOW_RATE, pumppos.value, State1.START_PUMP, state2,  prime_rate, log_file_name)
    time.sleep(time_to_sleep)
    elapsed_time = time.time() - start_time
    flow(Mode.SET_FLOW_RATE, pumppos.value, State1.STOP_PUMP, state2,  prime_rate, log_file_name)
    return elapsed_time

# Helper method to generate a list of 3-way valve instructions to control the 24-V valve in one connection
def generate_switch_valve_3way_instructions(state, pos):
    return [(state, pos.value * 2 - 1), (state, pos.value * 2)]

def check_serial(ports, baud_rate=9600):
    for current in ports:
        port_str = 'COM' + str(current) 
        try:
            ser = serial.Serial(port_str, baud_rate)
            ser.close()
        except Exception as e:
            error_equip = ''
            if port_str == viscometer_port:
                error_equip = 'viscometer'
            elif port_str == balance_port:
                error_equip = 'balance'
            elif current == Pumppos.VALVE.value or current == Pumppos.SONICATOR.value:
                error_equip = 'pump'
            elif port_str in valve_ports or port_str == end_valve_port:
                error_equip = '10-port valve'
            logging.error(f"Cannot find: {error_equip} at {port_str}")
            raise BufferError(f"Cannot find: {error_equip} at {port_str}")
    
def check_hid(paths):
    try:
        for current in paths:
            device = hid.device()
            device.open_path(current)
            device.close()
    except Exception as e:
        logging.error((f"Error in connecting hid device: {str(e)}"))
        raise BufferError(f"Error in connecting hid device: {str(e)}")


def terminate():
    try:
        close_all(path_3way)
    except Exception as e:
        pass
    try:
        close_all(path_2way)
    except Exception as e:
        pass
    try:
        stop(viscometer_port, baud_rate=9600)
    except Exception as e:
        pass
    try:
        terminate_pump(Pumppos.VALVE.value)
    except Exception as e:
        pass
    try:
        terminate_pump(Pumppos.SONICATOR.value)
    except Exception as e:
        pass
    
    



#experiment("EC_EMC|50_50|LiPF6|1", [0.1, 0, 0, 0.5, 0.2, 0, 0, 0, 0.1, 1, 0.1, 0, 0, 0, 0.3, 0, 0, 0.1, 0.4], close=True)

#{'Solvents': {'solvent': ['EMC', 'DMC'], 'percentage': [50.0, 50.0]}, 'Salts': {'salt': ['LiPF6'], 'molality': [1.0]}, 'experiments': {'Density': 1, 'Conductivity': 2, 'Viscosity': 3, 'Mass': 4, 'Volume': 5, 'Temperature': 6, 'Date': 20032, 'Trial': 1}}