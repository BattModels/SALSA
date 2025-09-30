import cv2
import os

# Path to your image folder
file_path = os.path.dirname(os.path.abspath(__file__))
input_folder = os.path.join(file_path, 'val', 'Sediment')
output_folder = os.path.join(file_path, 'val', 'Sediment')
# Create output folder if it doesn't exist
#os.makedirs(output_folder, exist_ok=True)
dir_list = os.listdir(input_folder)
# Loop through all image files
for filename in dir_list:
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        img_path = os.path.join(input_folder, filename)
        image = cv2.imread(img_path)

        if image is not None:
            # Mirror the image (flip horizontally)
            mirrored = cv2.flip(image, 1)

            # Save the mirrored image
            save_path = os.path.join(output_folder, f"mirrored_{filename}")
            cv2.imwrite(save_path, mirrored)

print("✅ All images mirrored and saved.")