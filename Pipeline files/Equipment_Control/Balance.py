import serial
import time
import logging
import re
try:
    from Utils import RETRY_LIMIT
except Exception as e:
    from .Utils import RETRY_LIMIT
# Set up logging

STABLE_COUNT = 15  # Define your stable count threshold here
tolerance = 0.0005


def measure_mass(port_num, baud_rate, period=0.1, log_file_name="Measurement.log"):
    time.sleep(5)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='w')
    stable_count = 0
    previous = 1e-5
    for retry in range(RETRY_LIMIT):
        try:
            ser = serial.Serial(port_num, baud_rate, timeout=1)
            logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
            while True:
                data = ser.readline().decode()
                
                if data:
                    try:
                        number = re.search(r"\d+\.\d+", data)
                        measurement = float(number.group())
                        logging.info(f'Received measurement: {measurement}')
                    except ValueError:
                        logging.warning(f"Invalid data received: {data}")
                        continue
                    
                    # Let the balance return the result after it is stablized in the last 10 measurements
                    if '?' not in data:
                    # if abs(measurement - previous) < tolerance:
                        # Measurement stablized
                        stable_count += 1
                        logging.info(f'Measurement stable count: {stable_count}')
                    else:
                        # Measurement not stablized
                        stable_count = 0
                    if stable_count >= STABLE_COUNT:
                        logging.info(f'Measurement stabilized: {measurement}')
                        ser.close()
                        return measurement
                    previous = measurement
                    # Wait for a 0.1 second before starting the next measurement
                    time.sleep(period)
                    
        except Exception as e:
            logging.error(f"Error reading from serial port: {e}")
            time.sleep(1)
    raise BufferError('Error occured in measuring mass')

if __name__ == '__main__':
    measure_mass("COM9", 9600, period=0.1, log_file_name="Measurement.log")