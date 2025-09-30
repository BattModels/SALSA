from ultralytics import YOLO

# Load YOLO model
model = YOLO("yolov8n.pt")

# Train the model
model.train(data="dataset/data.yaml", epochs=50, imgsz=640)