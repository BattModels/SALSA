import hid
import subprocess
import time
import logging
import os
try:
    from Utils import RETRY_LIMIT, current_dir
except Exception as e:
    from .Utils import RETRY_LIMIT, current_dir
adjustment = -6.1
software_location = os.path.join(current_dir, '..', '..', 'ElitechLogWin', 'DL.exe')

def read_record_by_num(path, i):
    result = 0
    while not result:
        try:
            device = hid.device()
            device.open_path(path)
            device.set_nonblocking(True)
            command = [0, 51, 204, 0, 12, 1, 0, 0, i // 256 , i % 256, 0, 1, (13 + i // 256 + i) % 256]
            device.write(bytes(command))
            result = device.read(20)[12:18]
            temperature = (result[4] * 8 + result[3] // 32) / 10
            device.close()
            result = temperature
        except IndexError:
            pass
    return result

def total_records(path):
    maximum = 0
    for i in range(5):
        device = hid.device()
        device.open_path(path)
        command = [0, 51, 204, 0, 12, 3, 0, 0, 0, 72, 0, 2, 88]
        device.write(bytes(command))
        result = device.read(14)
        device.close()
        value = result[-3] * 256 + result[-2]
        maximum = max(value, maximum)
    return value

def is_logging(path):
    device = hid.device()
    device.open_path(path)
    for i in range(2):
        command = [0, 51, 204, 0, 12, 3, 0, 0, 0, 36, 0, 2, 52]
        device.write(bytes(command))
        result = device.read(14)
    device.close()
    value = result[-2]
    return value == 7
    
def measure_temperature(path, log_file_name='Measurement.log'):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='a')
    for retry in range(RETRY_LIMIT):
        try:
            if not is_logging(path):
                logging.error('Thermometer is not logging')
                raise BufferError('Thermometer is not logging')
            device = hid.device()
            device.open_path(path)
            #device.set_nonblocking(True)
            command = [0, 51, 204, 0, 12, 5, 0, 0, 0, 128, 0, 48, 192]
            device.write(bytes(command))
            device.close()
            time.sleep(5)
            num_records = total_records(path)
            logging.info(f'Number of records: {num_records}')
            result = read_record_by_num(path, num_records - 2) + adjustment
            logging.info(f'Measured temperature: {result}')
            return result
        except Exception as e:
            logging.error(f'Error with device: {e}')
            time.sleep(1)
    raise BufferError('Error in measuring temperature')