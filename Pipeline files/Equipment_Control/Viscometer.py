import serial
from time import sleep
from enum import Enum
import logging
import numpy as np
import time
import os
try:
    from Utils import *
except Exception as e:
    from .Utils import *
class Mode(Enum):
    ENABLE = 0
    READ = 1
    ZERO = 2
    START = 3
    STOP = 4

stablization = 10
rpm = 150
UPPER_LIMIT = 20
TEMP_LIMIT = 320
FAULT_TOLERANCE = 1

def measure_viscosity(rpm, stablization_time, port_num, data_points=10, baud_rate=9600, period=1, log_file_name="Measurement.log"):
    for retry in range(RETRY_LIMIT):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
        try:
            instrument = serial.Serial(port_num, baud_rate, timeout=1)
            logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
            instrument.flushOutput()
            instrument.flushInput() # Write command to the instrument
            try:
                command = generate_command(Mode.ENABLE)  # Ensure the command ends with a carriage return
                instrument.write(command.encode('utf-8'))  # Write command to the instrument
                sleep(0.1)  # Give the viscometer time to respond
                data_bytes = instrument.read(7)[-4:]
                # b'E0D\r' indicates no errors. b'D8'\r indicates errors
                if data_bytes != b'E0D\r' and data_bytes != '':
                    raise BufferError("Error enabling the viscometer.")
                else:
                    logging.info(f'Successfully enabled the viscometer.')
            except Exception as e:
                # No need to reenable the viscometer if it is already enabled. Otherwise it would raise an error
                pass
                
            command = generate_command(Mode.START, rpm=rpm)  # Ensure the command ends with a carriage return
            instrument.write(command.encode('utf-8'))  # Write command to the instrument
            sleep(stablization_time)
            logging.info(f'Starting measurement with rpm={rpm} and stablization time={stablization_time}.')
            cp_array = []
            temp_array = []

            cp_fault = 0
            temp_fault = 0
            for i in range(data_points):
                command = generate_command(Mode.READ)
                instrument.write(command.encode('utf-8'))  # Write command to the instrument
                data_bytes = str(instrument.read(100).decode('utf-8'))

                last_r_index = data_bytes.rfind('R')
                data_bytes = data_bytes[last_r_index + 1:] if last_r_index != -1 else ""
                tor_str = data_bytes[0:4]
                temp_bytes = data_bytes[4:8]

                # Calibrate the readings
                raw_torque = int(tor_str, 16) / 100
                temp = (int(temp_bytes, 16) - 4000) / 40
                cp = raw_torque / rpm * 6

                # Catch the faulty measurement values 
                # Viscosity cannot be negative, and it usually cannot exceed 20 cP
                if cp < 0:
                    cp_fault += 1
                    logging.error(f'Viscosity value too small: {cp}cp')
                elif cp > UPPER_LIMIT:
                    cp_fault += 1
                    logging.error(f'Viscosity value too large: {cp}cp')

                # Temperature is in Kelvin, also cannot be negative, and it usually cannot exceed room temperature (like 116F, which is already very high)
                elif temp < 0:
                    temp_fault += 1
                    logging.error(f'Temperature too low: {temp}')
                elif temp > TEMP_LIMIT:
                    temp_fault += 1
                    logging.error(f'Temperature too high: {temp}')
                else:
                    cp_array.append(cp)
                    temp_array.append(temp)
                    logging.info(f'Measured viscosity {cp}cp and temperature {temp}.')
                if cp_fault > FAULT_TOLERANCE or temp_fault > FAULT_TOLERANCE:
                    # Allow one faulty value. But if there are two, viscometer should raise an error
                    raise ValueError('Too many fault values')
                sleep(period)
            cp_mean = np.round(sum(cp_array) / len(cp_array), 4)
            temp_mean = np.round(sum(temp_array) / len(temp_array), 4)
            logging.info(f'Average viscosity {cp_mean}cp and temperature {temp_mean}.')
            command = generate_command(Mode.STOP)
            instrument.write(command.encode('utf-8'))
            instrument.close()
            return cp_mean, temp_mean
        except Exception as e:
            logging.error(e)
            time.sleep(1)
    raise BufferError('Error occured in measuring viscosity')

# Zero out the torques of the viscometer
def zero(port_num, baud_rate=9600, log_file_name="..\\Measurement.log"):
    for retry in range(RETRY_LIMIT):
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=os.path.join(current_dir, '..', 'Logs', log_file_name), filemode='a')
        try:
            instrument = serial.Serial(port_num, baud_rate, timeout=1)
            logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
            instrument.flushOutput()
            instrument.flushInput()# Clear buffer
            command = generate_command(Mode.ZERO)
            instrument.write(command.encode('utf-8')) # Write command to the instrument
            #sleep(5)
            #command = generate_command(Mode.STOP)
            #instrument.write(command.encode('utf-8'))
            instrument.close()
            logging.info(f'Successfully zeroed the viscometer')
            return
        except Exception as e:
            logging.error(e)
    raise BufferError('Error occured in zeroing viscometer')

# Stop the viscometer
def stop(port_num, baud_rate=9600, log_file_name=None):
    for retry in range(RETRY_LIMIT):
        if log_file_name:
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='Logs\\' + log_file_name, filemode='a')
        try:
            instrument = serial.Serial(port_num, baud_rate, timeout=1)
            if log_file_name:
                logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
            instrument.flushOutput()
            instrument.flushInput()# Clear buffer
            command = generate_command(Mode.STOP)
            instrument.write(command.encode('utf-8')) # Write command to the instrument
            instrument.close()
            if log_file_name:
                logging.info(f'Successfully stopped the viscometer')
            return
        except Exception as e:
            if log_file_name:
                logging.error(e)
    raise BufferError('Error occured in stopping viscometer')

def generate_command(mode, rpm=0):
    if mode == Mode.ENABLE:
        return "E\r"
    if mode == Mode.READ:
        return "R\r"
    if mode == Mode.ZERO:
        return "Z\r"
    if mode == Mode.STOP:
        return "V00000\r"
    # Start mode, which converts the rpm * 100 into hex value
    return f"V{format(rpm * 100, '05X')}\r"

if __name__ == '__main__':
    #zero("COM7", baud_rate=9600)
    
    measure_viscosity(200, 15, "COM7", data_points=30, baud_rate=9600, period=1, log_file_name="Measurement.log")
        