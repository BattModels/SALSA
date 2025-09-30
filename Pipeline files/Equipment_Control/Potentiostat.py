import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from pspython import pspyinstruments, pspymethods, pspyfiles
except Exception as e:
    from ..pspython import pspyinstruments, pspymethods, pspyfiles
    
try:
    from .Utils import *
except Exception as e:
    from Utils import *

    


    
import numpy as np
import pandas as pd
import logging
import time
CWD = os.path.abspath(__file__)
NAME = "PalmSens4"
SIGNIFICANT_DIGITS = 8
FREQ_THRESHOLD = 1.5E5

def check_connection():
    #logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
    def new_data_callback(new_data):
        for type, value in new_data.items():
            logging.info(type + ' = ' + str(value))
        return

    manager = pspyinstruments.InstrumentManager(new_data_callback=new_data_callback)
    available_instruments = pspyinstruments.discover_instruments()
    instrument = None
    for current in available_instruments:
        if current.name.startswith(NAME):
            instrument = current
    if not instrument:
        raise RuntimeError('cannot find potentiostat')

def measure_conductivity(path, log_file_name='Measurement.log'):
    for retry in range(RETRY_LIMIT):
        try:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
            def new_data_callback(new_data):
                for type, value in new_data.items():
                    logging.info(type + ' = ' + str(value))
                return

            manager = pspyinstruments.InstrumentManager(new_data_callback=new_data_callback)
            available_instruments = pspyinstruments.discover_instruments()
            instrument = None
            for current in available_instruments:
                if current.name.startswith(NAME):
                    instrument = current
            if not instrument:
                raise RuntimeError('cannot find potentiostat')
            logging.info('connecting to ' + instrument.name)
            success = manager.connect(instrument)
            # #Chronoamperometry measurement using helper class
            # method = pspymethods.chronoamperometry(interval_time=0.5, e=1.0, run_time=5.0)

            # EIS measurement using helper class
            method = pspymethods.electrochemical_impedance_spectroscopy()
            #Loading exiting cv method and changing its paramters

            scriptDir = os.path.dirname(os.path.realpath(__file__))
            method = pspyfiles.load_method_file(path)
            #method = pspyfiles.load_method_file(scriptDir + '\\cv.psmethod')
            #method.Scanrate = 1
            #method.StepPotential = 0.02

            if success == 1:
                logging.info('connection established')

                measurement = manager.measure(method)
                if measurement is not None and not isinstance(measurement, str):
                    logging.info('measurement finished')
                else:
                    raise RuntimeError(measurement)

                success = manager.disconnect()

                if success == 1:
                    logging.info('disconnected')
                    return process_measurement(measurement)
                else:
                    raise RuntimeError('error while disconnecting')
            else:
                raise RuntimeError('connection failed')
        except Exception as e:
            logging.error(str(e))
            time.sleep(1)
    raise BufferError('Error occured in measuring conductivity')

def process_measurement(measurement):
    real_arrays = []
    img_arrays = []
    for i in range(len(measurement.freq_arrays[0])):
        # Only keep the measurements with a low frequency
        if measurement.freq_arrays[0][i] < FREQ_THRESHOLD:
            real_arrays.append(measurement.zre_arrays[0][i])
            img_arrays.append(abs(measurement.zim_arrays[0][i]))
    # Fit a line with least squares
    slope, intercept = np.polyfit(real_arrays, img_arrays, 1)

    # The Slope should > 0, and the intercept should < 0
    '''
    if slope < 0:
        raise ValueError(f"Invalid slope={slope}")
    elif intercept > 0:
        raise ValueError(f"Invalid intercept={intercept}")
    else:
        # Solve the equation'
    '''
    result = intercept / slope * -1
    logging.info(f"Calculated Intercept: {result}")
    if result < 0:
        #raise ValueError(f"Dubious measurement: resistance={result}Ω")
        result = abs(result)
    return result

def round_to_significant_figures(num, sig_digits):
    if num == 0:
        return 0
    return round(num, sig_digits - len(str(int(abs(num)))))

# Method used for testing, not used in actual implementation
def save_to_json(measure):
    time_string = sanitize_filename(measure.timestamp) + '.json'
    path = os.path.join(CWD, '..', 'Results', 'Potentiostat', time_string)
    save_dict_to_json(vars(measure), path)

def save_to_csv(measure):
    time_string = sanitize_filename(measure.timestamp) + '.csv'
    path = os.path.join(CWD, '..', 'Results', 'Potentiostat', time_string)
    measure = vars(measure)
    df = {}
    for current in measure:
        if isinstance(measure[current], list) and len(measure[current]) > 0 and isinstance(measure[current][0], list):
            
            df[current] = [round_to_significant_figures(x, SIGNIFICANT_DIGITS) for x in measure[current][0]]
    df = pd.DataFrame(df)
    
    # Write the DataFrame to a CSV file
    df.to_csv(path, index=False)
if __name__ == '__main__':
    measure_conductivity("C:\\Users\\MUSE_V2\\Documents\\PSData\\CLIO methods\\ScriptVerified\\PSmethod\\COND_Ch=2.psmethod", log_file_name='Measurement.log')