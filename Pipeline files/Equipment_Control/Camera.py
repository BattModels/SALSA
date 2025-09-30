import cv2
import os
from datetime import datetime
import time
import logging
try:
    from Utils import CAMERA_FOCUS
except Exception as e:
    from .Utils import CAMERA_FOCUS

# Create a folder to save images if it doesn't exist
save_folder = "captured_images"
os.makedirs(save_folder, exist_ok=True)
# Open the camera (0 is usually the default camera)
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
cap.set(cv2.CAP_PROP_FOCUS, CAMERA_FOCUS)
def take_picture(log_file_name='Camera.py'):
    if not cap.isOpened():
        logging.error("Error: Could not open the camera.")
        exit()

    time.sleep(2)
    ret, frame = cap.read()  # Capture frame
    if not ret:
        logging.error("Error: Could not read the frame.")
        return None
    logging.info('Successfully took the image.')
    return frame
