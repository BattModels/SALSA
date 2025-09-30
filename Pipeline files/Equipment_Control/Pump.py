import logging
import serial
import time
from enum import Enum
import array
try:
    from Utils import RETRY_LIMIT
except Exception as e:
    from .Utils import RETRY_LIMIT

path = "Inventory.csv"
# Temporary, will be replaced by new valves which will not use device_path
device_path = b'\\\\?\\HID#VID_16C0&PID_05DF#8&28e61420&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
# Configure logging


# Enumerates
class Mode(Enum):
    SET_ROTATION_SPEED = 0
    READ_ROTATION_SPEED = 1
    SET_FLOW_RATE = 2
    READ_FLOW_RATE = 3
    FLOW_CALIBRATION = 4

class State1(Enum):
    STOP_PUMP = 0
    START_PUMP = 1
    PRIME_PUMP = 17

class State2(Enum):
    COUNTER_CLOCKWISE = 1
    CLOCKWISE = 0

# Mappings to map baud rates into instructions
baud_rate = {1200:1, 2400:2, 4800:3, 9600:4, 19200:5, 38400:6}

class Parity(Enum):
    NO_PARITY = 1
    ODD_PARITY = 2
    EVEN_PARITY = 3

# Hardcoded instructions to give based on modes
def get_pdu(mode):
    if mode == Mode.SET_ROTATION_SPEED:
        return [6, 87, 74]
    if mode == Mode.READ_ROTATION_SPEED:
        return [2, 82, 74]
    if mode == Mode.SET_FLOW_RATE:
        return [8, 87, 76]
    if mode == Mode.READ_FLOW_RATE:
        return [2, 82, 76]
    if mode == Mode.FLOW_CALIBRATION:
        return [8, 87, 73, 68, 13, 0]

# The last byte of instruction is computated by X-oring all the previous bytes to check whether a command is valid
def xor_bytes(int_list):
    result = 0
    for num in int_list:
        result ^= int(num) & 0xFF
    return result

# If a number is too large, it needs multiple bytes to store
def generate_bytes(num, n):
    result = []
    for i in range(n):
        result.append(num % 256)
        num = num // 256
    result.reverse()
    return result

# Main function to generate commands
def generate_command(*args):
    log = isinstance(args[-1], str)
    if log:
        logging.info(f"Generating command with arguments: {args}")
    mode = args[0]
    pdu = get_pdu(mode)
    command = [233, args[1]]
    
    if mode == Mode.SET_ROTATION_SPEED:
        rotation_speed = args[4]
        state1 = args[2].name
        state2 = args[3].name
        
        pdu += generate_bytes(rotation_speed, 2) + [args[2].value, args[3].value]
        if log:
            logging.info(f"Setting rotation speed to {rotation_speed} with State1: {state1}, State2: {state2}")
    
    elif mode == Mode.SET_FLOW_RATE:
        flow_rate = args[4]
        state1 = args[2].name
        state2 = args[3].name
        
        pdu += generate_bytes(flow_rate, 4) + [args[2].value, args[3].value]
        if log:
            logging.info(f"Setting flow rate to {flow_rate} with State1: {state1}, State2: {state2}")
    
    elif mode == Mode.FLOW_CALIBRATION:
        baud = args[2]
        parity = args[3].name
        stop_bit = args[4]
        
        pdu += [baud_rate[baud], args[3].value, stop_bit]
        if log:
            logging.info(f"Calibrating flow with Baud rate: {baud}, Parity: {parity}, Stop bit: {stop_bit}")
    
    fcs = xor_bytes([args[1]] + pdu)
    byte_array = array.array('B', list(map(int, [233, args[1]] + pdu + [fcs])))
    if log:
        logging.info(f"Generated command: {byte_array}")
    return bytearray(byte_array)

# Pipeline to generate and control the valves pased on the provided arguments
def flow(*args):
    for retry in range(RETRY_LIMIT):
        try:
            if args[3] == State1.START_PUMP:
                if args and isinstance(args[-1], str):
                    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=args[-1], filemode='a')
                else:
                    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='pump_control.log', filemode='a')
            ser = serial.Serial('COM' + str(args[1]), 9600, parity=serial.PARITY_NONE, bytesize=8, stopbits=1, timeout=None, xonxoff=0, rtscts=0)
            command = generate_command(*args)
            ser.write(command)
            ser.close()
            if args[3] == State1.STOP_PUMP:
                if args and isinstance(args[-1], str):
                    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=args[-1], filemode='a')
                else:
                    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='pump_control.log', filemode='a')
            return
        except Exception as e:
            logging.error(f'Error with device: {e}')
            time.sleep(1)

    raise BufferError('Error occured in pump')
    
def terminate_pump(pumppos):
    ser = serial.Serial('COM' + str(pumppos), 9600, parity=serial.PARITY_NONE, bytesize=8, stopbits=1, timeout=None, xonxoff=0, rtscts=0)
    command = generate_command(Mode.SET_FLOW_RATE, pumppos, State1.STOP_PUMP, State2.CLOCKWISE, 0)
    ser.write(command)
    ser.close()
    return

if __name__ == '__main__':
    flow(Mode.SET_FLOW_RATE, 12, State1.STOP_PUMP, State2.CLOCKWISE,  1.6E5, 'Measurement.log')
