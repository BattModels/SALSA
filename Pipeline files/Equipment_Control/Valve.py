import serial
import time
import logging
try:
    from Utils import RETRY_LIMIT
except Exception as e:
    from .Utils import RETRY_LIMIT


def switch_valve(port_num, baud_rate, dest, log_file_name='Valve.log'):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='Valve.log', filemode='a')
        
    for retry in range(RETRY_LIMIT):
        try:
            ser = serial.Serial(port_num, baud_rate, timeout=1)
            logging.info(f'Successfully opened serial port {port_num} at baud rate {baud_rate}.')
            for retry2 in range(RETRY_LIMIT):
                # Get the current position
                command = "CP\r"
                ser.write(command.encode())
                r = str(ser.read(5).decode('utf-8').strip())
                response = int(r[2:4]) # Response would be like CPXX\r, where XX indicates two digits
                if response != dest:
                    # Go to target destination
                    command = f"GO{dest}\r"   
                    logging.info(f'Valve moving from position: {response}')
                    ser.write(command.encode())
                else:
                    logging.info(f'Valve moved to position: {response}')
                    ser.close()
                    return
        except Exception as e:
            logging.error(f"Error reading command: {e}")
            time.sleep(1)
    raise BufferError('Error occured in 10-port valve')

if __name__ == '__main__':
    switch_valve("COM4", 9600, 2, log_file_name='Measurement.log')