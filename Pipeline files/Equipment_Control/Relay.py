# Find Device Info
import hid
from enum import Enum
import logging
from time import sleep
try:
    from Utils import RETRY_LIMIT
except Exception as e:
    from .Utils import RETRY_LIMIT
num_ports = (1, 8)
class State3Way(Enum):
    OFF = 0
    ON = 1
# List all HID devices
PATH = b'\\\\?\\HID#VID_16C0&PID_05DF#8&d39fb6d&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
def switch_3way_valve(path, instructions, log_file_name='device_log.log'):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
    for retry in range(RETRY_LIMIT):
        try:
            # Open the HID device
            device = hid.device()
            device.open_path(path)
            logging.info(f'Device successfully opened: {path}')
            # Instructions are in this format: (State3Way, switch_number)
            for current in instructions:
                cmd = [0x00, 0xFD if current[0] == State3Way.OFF else 0xFF, current[1]]
                device.send_feature_report(cmd)
                logging.info(f'Command sent: {cmd} for valve state: {current[0].name}, valve number: {current[1]}')
            
            # Close the device
            device.close()
            logging.info(f'Device successfully closed: {path}')
            return
        
        except Exception as e:
            logging.error(f'Error with device: {e}')
            sleep(1)
    raise BufferError('Error occured in 3way valve')
    
def close_all(path, log_file_name=None):
    if log_file_name:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
    for retry in range(RETRY_LIMIT):
        try:
            device = hid.device()
            device.open_path(path)
            if log_file_name:
                logging.info(f'Device successfully opened: {path}')
            # Command to close all the switches
            for i in range(1, 9):
                cmd = [0x00, 0xFD, i]
                device.send_feature_report(cmd)
            if log_file_name:
                logging.info(f'Successfully closed all valves')
            device.close()
            return
        except Exception as e:
            if log_file_name:
                logging.error(f'Error with device: {e}')
    raise BufferError('Error occured in 3way valve')

if __name__ == '__main__':
    device = hid.device()
    device.open_path(PATH)
    for i in range(1, 9):
        cmd = [0x00, 0xFF, i]
        device.send_feature_report(cmd)
        sleep(2)
        cmd = [0x00, 0xFD, i]
        device.send_feature_report(cmd)