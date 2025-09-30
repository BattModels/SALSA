import json
import re
import os
from enum import Enum

# All the public variables and dependencies should be here
current_dir = os.path.dirname(os.path.abspath(__file__))
method_file = os.path.join(current_dir, '..', 'pspython', 'COND_Ch=2.psmethod')
valve_ports = ["COM6", "COM4"]
end_valve_port = "COM5"
balance_port = "COM9"
viscometer_port = "COM7"
serial_array = [4, 5, 6, 7, 9, 12, 14]
path_3way = b'\\\\?\\HID#VID_16C0&PID_05DF#8&20d8742f&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
path_2way = b'\\\\?\\HID#VID_16C0&PID_05DF#8&be40740&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
path_2way2 = b'\\\\?\\HID#VID_16C0&PID_05DF#6&2e11b7e6&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
path_thermometer = b'\\\\?\\HID#VID_464D&PID_0402&MI_01#9&b2d5f67&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}'
baud_rate = 9600
ACN = 1 # ACN is in bottle 1. It will be moved to bottle 19
WASTE = 10
NUM_VALVES = 2
NUM_BOTTLES = 10
VISCOMETER_RPM = 200 # Should be converted to rotations per 100 minute when using. In this case it would be 6000
VISCOSITY_STABLE = 10 #seconds
PRIME_VOLUME_VALVE = 1.15 # Amount of liquid to prime before using
PRIME_VOLUME_SONICATOR = 2 # Amount of liquid to prime before using
FLOW_RATE = 5 # In ml/minute. Should be converted to nL per minute
BALANCE_FLOW_RATE = 4 # In ml/minute. Should be converted to nL per minute
POTENTIOSTAT_VOLUME = 0.8
POTENTIOSTAT_RINSE_VOLUME = 0.7
BALANCE_VOLUME = 0.5
BALANCE_TUBE_VOLUME = 0.4826
BALANCE_PRIME_VOLUME = 0.5
SONICATOR_TUBE_VOLUME = 0.08
CELL_CONSTANT = 10.0236965757
CELL_BIAS = 0
DENSITY_TOLERANCE_FACTOR = (-0.2, 5)
RINSE_VOLUME = 1
VISCOMETER_VOLUME = 1.1
RETRY_LIMIT = 10 # Occasionally, the equipments would run into an error for a short time, which can be resolved by retrying. Therefore, we should allow some errors if it is able to self-fix
# Thresholds for a good candidate
SOLUBILITY_STEP_VOLUME = 0.1
SOLUBILITY_BURN_IN_VOLUME = 0.8
TOTAL_VOLUME = 1.5
CONDUCTIVITY_CUTOFF = 150 # Larger values are considered good
VISCOSITY_CUTOFF = 50 # Smaller values are considered good
BACK_DIRECTION_FACTOR = 1.3

PRE_MIX_TIME = 20 #Time for stirrer to operate right after dispensing the salts to get rid of the contacting salts on the stirrer
MIX_TIME = 10
SOLUBILITY_MIX_TIME = 60 #Time for the stirrer to stir the liquid and solid
REST_TIME = 60 
DISPENSE_TIME = 1 #Controls the amount of solid to be dozed each time
MIN_SOLID_MASS = 0.4 #Minimum amount of solid in each measurements
CAMERA_FOCUS = 60

class Valve3Waypos(Enum):
    SONICATOR = 4
    POTENTIOSTAT = 2
    BALANCE = 1
    VISCOMETER = 3

class RelayPos(Enum):
    SOLIDOZER = 4
    SONICATOR = 2
    MIX_MOTOR = 3
    SOLID_VALVE = 1


class Pumppos(Enum):
    VALVE = 12
    SONICATOR = 14

# Methods used for testing and callibration purposes, not used in actual running
def sanitize_filename(filename):
    # Replace invalid characters with a hyphen or remove them
    return re.sub(r'[\/:*?"<>|]', '-', filename)

def save_dict_to_json(data_dict, file_name):
    with open(file_name, 'w') as json_file:
        json.dump(data_dict, json_file, indent=4)