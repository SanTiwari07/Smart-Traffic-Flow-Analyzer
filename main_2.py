import numpy as np
from ultralytics import YOLO
import cv2 
import cvzone
import math
from sort import*  # SORT tracker for object tracking

# -----------------------------
# 1. Load video and model
# -----------------------------
cap = cv2.VideoCapture("C:/Users/sansk/Desktop/CEP_Dynamic_Traffic_Signal/video.mp4")
model = YOLO("yolov8l.pt")  # YOLOv8 model

# -----------------------------
# 2. Class names (COCO dataset)
# -----------------------------
classNames = ["person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
              "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
              "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
              "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite", "baseball bat",
              "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
              "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli",
              "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant", "bed",
              "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard", "cell phone",
              "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
              "teddy bear", "hair drier", "toothbrush"]

# Only detect these vehicle classes
vehicle_classes = ["car", "bus", "truck", "motorcycle"]

# -----------------------------
# 3. Load mask and prepare frame
# -----------------------------
mask = cv2.imread("C:/Users/sansk/Desktop/CEP_Dynamic_Traffic_Signal/mask.png")

success, img = cap.read()
if not success:
    print("No video or input")
    exit()

# Resize mask to match video frame
mask = cv2.resize(mask, (img.shape[1], img.shape[0]))
if len(mask.shape) == 2:
    mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

# -----------------------------
# 4. Initialize tracker
# -----------------------------
tracker = Sort(max_age=20, min_hits=3, iou_threshold=0.3)

# Define polygon region for density calculation
polygon_points = np.array([[589, 206], [417, 539], [1275, 539], [874, 209]], np.int32)

# History for averaging density over 5 seconds
density_history = []
fps_estimate = 30 
frames_per_5_seconds = fps_estimate * 5

# -----------------------------
# 5. Utility functions
# -----------------------------
def calculate_polygon_area(points):
    """Calculate the area of a polygon using Shoelace formula"""
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def is_point_in_polygon(point, polygon):
    """Check if a point is inside a polygon"""
    return cv2.pointPolygonTest(polygon, point, False) >= 0

def calculate_bbox_polygon_intersection_area(bbox, polygon):
    """Calculate intersection area between a bounding box and polygon"""
    x1, y1, x2, y2 = bbox
    
    # Create mask for polygon
    mask_poly = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
    cv2.fillPoly(mask_poly, [polygon], 255)
    
    # Create mask for bounding box
    mask_bbox = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
    cv2.rectangle(mask_bbox, (int(x1), int(y1)), (int(x2), int(y2)), 255, -1)
    
    # Calculate intersection
    intersection = cv2.bitwise_and(mask_poly, mask_bbox)
    intersection_area = np.sum(intersection > 0)
    
    return intersection_area

# Total area of polygon for density calculation
total_polygon_area = calculate_polygon_area(polygon_points)

# -----------------------------
# 6. Main loop
# -----------------------------
while True:
    success, img = cap.read()
    if not success:
        break
    
    # Apply mask to focus on region of interest
    imgRegion = cv2.bitwise_and(img, mask)
    
    # Run YOLO detection
    results = model(imgRegion, stream=True)
    
    # Store detections in format [x1, y1, x2, y2, confidence]
    detections = np.empty((0, 5))
    
    for r in results:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            w, h = x2 - x1, y2 - y1
            
            conf = math.ceil((box.conf[0] * 100)) / 100
            cls = int(box.cls[0])
            currentClass = classNames[cls]
            
            # Keep only vehicles above confidence threshold
            if currentClass in vehicle_classes and conf > 0.3:
                currentArray = np.array([x1, y1, x2, y2, conf])
                detections = np.vstack((detections, currentArray))
    
    # Update tracker with detections
    resultsTracker = tracker.update(detections)
    
    # Draw polygon region
    cv2.polylines(img, [polygon_points], True, (0, 255, 0), 3)
    
    total_vehicle_area_in_polygon = 0
    vehicles_in_polygon = 0
    
    for result in resultsTracker:
        x1, y1, x2, y2, id = result
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        w, h = x2 - x1, y2 - y1
        
        # Draw bounding box and ID
        cvzone.cornerRect(img, (x1, y1, w, h), l=9, rt=2, colorR=(255, 0, 255))
        cvzone.putTextRect(img, f' {int(id)}', (max(0, x1), max(35, y1)),
                          scale=2, thickness=3, offset=10)
        
        # Draw center of bounding box
        cx, cy = x1 + w // 2, y1 + h // 2
        cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        
        # Check if vehicle is inside polygon
        if is_point_in_polygon((cx, cy), polygon_points):
            vehicles_in_polygon += 1
            intersection_area = calculate_bbox_polygon_intersection_area([x1, y1, x2, y2], polygon_points)
            total_vehicle_area_in_polygon += intersection_area
            
            # Highlight vehicles inside polygon
            cvzone.cornerRect(img, (x1, y1, w, h), l=9, rt=2, colorR=(0, 255, 0))
    
    # Calculate density (vehicle area / polygon area)
    if total_polygon_area > 0:
        density = total_vehicle_area_in_polygon / total_polygon_area
    else:
        density = 0
    
    # Keep history for average over 5 seconds
    density_history.append(density)
    if len(density_history) > frames_per_5_seconds:
        density_history.pop(0)  
    avg_density = sum(density_history) / len(density_history) if density_history else 0
    
    # Display info text on frame
    y_offset = 30
    line_height = 35
    
    # Number of vehicles
    cars_text = f"Cars in Region: {vehicles_in_polygon}"
    text_size = cv2.getTextSize(cars_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, cars_text, (img.shape[1] - text_size[0] - 20, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    # Current density
    density_text = f"Density: {density:.2f}"
    text_size = cv2.getTextSize(density_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, density_text, (img.shape[1] - text_size[0] - 20, y_offset + line_height), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    
    # Average density over 5 seconds
    avg_density_text = f"Avg Density (5s): {avg_density:.2f}"
    text_size = cv2.getTextSize(avg_density_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, avg_density_text, (img.shape[1] - text_size[0] - 20, y_offset + 2*line_height), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
    
    # Show frame
    cv2.imshow("Image", img)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
