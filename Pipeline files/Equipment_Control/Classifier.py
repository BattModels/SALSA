from ultralytics import YOLO
import cv2
import os
import logging

# Load models
script_dir = os.path.dirname(os.path.abspath(__file__))
detect_model = YOLO(os.path.join(script_dir, "detect_best.pt"))         # Replace with your detect model path
classify_model = YOLO(os.path.join(script_dir, "classification_best.pt"))   # Replace with your classify model path
# Run detection


# Loop through detected boxes
def classify(img, log_file_name='Camera.py', threshold=0.5, bias='Sediment'):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename=log_file_name, filemode='w')
    try:
        detect_result = detect_model(img)[0]
        box = detect_result.boxes.xyxy.cpu().numpy()[0]
        x1, y1, x2, y2 = map(int, box)
        crop = img[y1:y2, x1:x2]
        print(x1, y1, x2, y2)
        # Run classification
        cls_result = classify_model(crop)[0]
        cls_id = cls_result.probs.top1
        cls_conf = cls_result.probs.top1conf
        cls_name = classify_model.names[cls_id]
        if cls_name != bias and cls_conf < threshold:
            cls_name = bias
            cls_conf = 1 - cls_conf
        logging.info(f"Image is classified as '{cls_name}' with confidence: {cls_conf:.2f}.")
        return {'result':cls_name, 'confidence':cls_conf}
    except IndexError as e:
        '''
        with open("output.txt", "a") as f:
            f.write(f"Image {img_dir} cannot be detected {e}\n")
            '''
        logging.error("Vile cannot be detected.")
        return "Vile cannot be detected."
