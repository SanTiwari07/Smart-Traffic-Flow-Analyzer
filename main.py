import numpy as np
from ultralytics import YOLO
import cv2 
import cvzone
import math
from sort import*
import time
import threading
try:
    import serial
except ImportError:
    serial = None

cap = cv2.VideoCapture("C:/Users/sansk/Desktop/CEP_Dynamic_Traffic_Signal/video.mp4")

model = YOLO("yolov8l.pt")

# Complete YOLO class names (COCO dataset)
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

vehicle_classes = ["car", "bus", "truck", "motorcycle"]

# -----------------------------
# Serial configuration (ESP32)
# -----------------------------
# Set the COM port for your ESP32 (check Device Manager). Example: 'COM3' on Windows, '/dev/ttyUSB0' on Linux
SERIAL_PORT = 'COM3'
SERIAL_BAUD = 115200
SERIAL_TIMEOUT = 0.1

def open_serial() -> "serial.Serial | None":
    if serial is None:
        print("pyserial not installed; skipping serial communication.")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=SERIAL_TIMEOUT)
        time.sleep(2.0)  # Allow ESP32 to reset after opening port
        print(f"Connected to ESP32 on {SERIAL_PORT} @ {SERIAL_BAUD}")
        return ser
    except Exception as e:
        print(f"Could not open serial port {SERIAL_PORT}: {e}")
        return None

def send_to_esp32(ser, green_s: int, red_s: int, yellow_s: int, saved_s: int):
    payload = f"GREEN:{green_s},RED:{red_s},YELLOW:{yellow_s},SAVED:{saved_s}\n"
    if ser is not None and ser.writable():
        try:
            ser.write(payload.encode('utf-8'))
        except Exception as e:
            print(f"Serial write error: {e}")
    # Also print for debugging/visibility
    print(f"-> ESP32 {payload.strip()}")

mask = cv2.imread("C:/Users/sansk/Desktop/CEP_Dynamic_Traffic_Signal/mask.png")

success, img = cap.read()
if not success:
    print("No video or input")
    exit()

mask = cv2.resize(mask, (img.shape[1], img.shape[0]))
if len(mask.shape) == 2:
    mask = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)

cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

tracker = Sort(max_age=20, min_hits=3, iou_threshold=0.3)

polygon_points = np.array([[589, 206], [417, 539], [1275, 539], [874, 209]], np.int32)

density_history = []
fps_estimate = 30 
frames_per_5_seconds = fps_estimate * 5

# -----------------------------
# Dynamic timing controller
# -----------------------------
class DynamicTimingController:
    """Controls green/yellow/red durations based on ROI density.

    Rules:
    - Start with green = 90s
    - First 10s: no change
    - Every 5s afterwards: compute 5s sliding avg density and adjust remaining green time:
        * density < 0.3  -> reduce remaining by 40%
        * 0.4 <= d <= 0.6 -> reduce remaining by 25%
        * d >= 0.7 -> no reduction
      Values in (0.3-0.4) or (0.6-0.7) -> no change (unspecified)
    - Bounds: 30s <= green <= 90s
    - Track total time saved across cycles
    """

    def __init__(self, yellow_seconds: int = 5, red_seconds: int = 60):
        self.worst_case = 90
        self.best_case = 30
        self.green_total = float(self.worst_case)
        self.yellow_total = int(yellow_seconds)
        self.red_total = int(red_seconds)
        self.phase = 'GREEN'  # GREEN -> YELLOW -> RED
        self.phase_start_time = time.time()
        self.last_rule_time = self.phase_start_time
        self.total_saved = 0.0

    def reset_for_new_green(self):
        # When a new green phase begins, reset timers and green duration
        now = time.time()
        self.phase = 'GREEN'
        self.phase_start_time = now
        self.last_rule_time = now
        self.green_total = float(self.worst_case)

    def get_elapsed(self) -> float:
        return time.time() - self.phase_start_time

    def get_remaining_green(self) -> float:
        return max(0.0, self.green_total - self.get_elapsed())

    def maybe_apply_rules(self, five_sec_avg_density: float):
        if self.phase != 'GREEN':
            return False
        elapsed = self.get_elapsed()
        # Wait first 10s; apply every 5s
        if elapsed < 10:
            return False
        if (time.time() - self.last_rule_time) < 5:
            return False

        remaining = self.get_remaining_green()
        if remaining <= 0:
            return False

        old_green_total = self.green_total
        reduction_factor = 0.0
        if five_sec_avg_density < 0.3:
            reduction_factor = 0.40
        elif 0.4 <= five_sec_avg_density <= 0.6:
            reduction_factor = 0.25
        elif five_sec_avg_density >= 0.7:
            reduction_factor = 0.0
        else:
            reduction_factor = 0.0

        if reduction_factor > 0.0:
            # Reduce remaining time by factor, keeping elapsed the same
            reduced_remaining = remaining * (1.0 - reduction_factor)
            new_total = elapsed + reduced_remaining
            # Enforce bounds
            bounded_total = max(self.best_case, min(new_total, self.worst_case))
            self.green_total = bounded_total
            self.last_rule_time = time.time()
            return abs(old_green_total - self.green_total) > 1e-6
        else:
            self.last_rule_time = time.time()
            return False

    def advance_phase_if_due(self):
        now = time.time()
        if self.phase == 'GREEN':
            if now - self.phase_start_time >= self.green_total:
                self.phase = 'YELLOW'
                self.phase_start_time = now
        elif self.phase == 'YELLOW':
            if now - self.phase_start_time >= self.yellow_total:
                self.phase = 'RED'
                self.phase_start_time = now
        elif self.phase == 'RED':
            if now - self.phase_start_time >= self.red_total:
                # End of cycle; compute saved time for the last green
                saved = max(0.0, self.worst_case - self.green_total)
                self.total_saved += saved
                self.reset_for_new_green()

    def get_phase_and_times(self):
        # Return current phase and integer seconds for countdowns
        if self.phase == 'GREEN':
            remaining_green = int(round(self.get_remaining_green()))
        else:
            remaining_green = int(round(self.green_total))
        return {
            'phase': self.phase,
            'green_total': int(round(self.green_total)),
            'yellow_total': int(round(self.yellow_total)),
            'red_total': int(round(self.red_total)),
            'remaining_green': remaining_green,
            'total_saved': int(round(self.total_saved))
        }

def calculate_polygon_area(points):
    """Calculate area of polygon using Shoelace formula"""
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * np.abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))

def is_point_in_polygon(point, polygon):
    """Check if point is inside polygon"""
    return cv2.pointPolygonTest(polygon, point, False) >= 0

def calculate_bbox_polygon_intersection_area(bbox, polygon):
    """Calculate intersection area between bounding box and polygon"""
    x1, y1, x2, y2 = bbox
    
    mask_poly = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
    cv2.fillPoly(mask_poly, [polygon], 255)
    
    mask_bbox = np.zeros((img.shape[0], img.shape[1]), dtype=np.uint8)
    cv2.rectangle(mask_bbox, (int(x1), int(y1)), (int(x2), int(y2)), 255, -1)
    
    intersection = cv2.bitwise_and(mask_poly, mask_bbox)
    intersection_area = np.sum(intersection > 0)
    
    return intersection_area

total_polygon_area = calculate_polygon_area(polygon_points)

ser = open_serial()

# Initialize controller and inform ESP32 about the first cycle
controller = DynamicTimingController(yellow_seconds=5, red_seconds=60)
send_to_esp32(
    ser,
    green_s=int(round(controller.green_total)),
    red_s=int(round(controller.red_total)),
    yellow_s=int(round(controller.yellow_total)),
    saved_s=int(round(controller.total_saved))
)

last_sent_second = -1

while True:
    success, img = cap.read()
    if not success:
        break
    
    imgRegion = cv2.bitwise_and(img, mask)
    
    results = model(imgRegion, stream=True)
    
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
            
            if currentClass in vehicle_classes and conf > 0.3:
                currentArray = np.array([x1, y1, x2, y2, conf])
                detections = np.vstack((detections, currentArray))
    
    resultsTracker = tracker.update(detections)
    

    cv2.polylines(img, [polygon_points], True, (0, 255, 0), 3)
    

    total_vehicle_area_in_polygon = 0
    vehicles_in_polygon = 0
    
    for result in resultsTracker:
        x1, y1, x2, y2, id = result
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        w, h = x2 - x1, y2 - y1
        
        cvzone.cornerRect(img, (x1, y1, w, h), l=9, rt=2, colorR=(255, 0, 255))
        cvzone.putTextRect(img, f' {int(id)}', (max(0, x1), max(35, y1)),
                          scale=2, thickness=3, offset=10)
        
        cx, cy = x1 + w // 2, y1 + h // 2
        cv2.circle(img, (cx, cy), 5, (255, 0, 255), cv2.FILLED)
        
    
        if is_point_in_polygon((cx, cy), polygon_points):
            vehicles_in_polygon += 1
        
            intersection_area = calculate_bbox_polygon_intersection_area([x1, y1, x2, y2], polygon_points)
            total_vehicle_area_in_polygon += intersection_area
            
    
            cvzone.cornerRect(img, (x1, y1, w, h), l=9, rt=2, colorR=(0, 255, 0))
    

    if total_polygon_area > 0:
        density = total_vehicle_area_in_polygon / total_polygon_area
    else:
        density = 0
    
    density_history.append(density)
    if len(density_history) > frames_per_5_seconds:
        density_history.pop(0)  
    

    avg_density = sum(density_history) / len(density_history) if density_history else 0

    # -----------------------------
    # Dynamic timing + Serial sync
    # -----------------------------
    # Apply rules only during GREEN phase
    if controller.phase == 'GREEN':
        changed = controller.maybe_apply_rules(avg_density)
        if changed:
            # Send updated remaining durations to ESP32 so it can adjust countdown
            send_to_esp32(
                ser,
                green_s=int(round(controller.get_remaining_green())),
                red_s=int(round(controller.red_total)),
                yellow_s=int(round(controller.yellow_total)),
                saved_s=int(round(controller.total_saved))
            )

    # Advance phases as time elapses
    prev_phase = controller.phase
    controller.advance_phase_if_due()
    if controller.phase != prev_phase:
        # On phase changes, notify ESP32 of the upcoming durations
        info = controller.get_phase_and_times()
        if controller.phase == 'GREEN':
            # New cycle begins; include accumulated saved time
            send_to_esp32(
                ser,
                green_s=int(round(controller.green_total)),
                red_s=int(round(controller.red_total)),
                yellow_s=int(round(controller.yellow_total)),
                saved_s=int(round(controller.total_saved))
            )
        elif controller.phase == 'YELLOW':
            send_to_esp32(
                ser,
                green_s=int(round(controller.get_remaining_green())),
                red_s=int(round(controller.red_total)),
                yellow_s=int(round(controller.yellow_total)),
                saved_s=int(round(controller.total_saved))
            )
        elif controller.phase == 'RED':
            send_to_esp32(
                ser,
                green_s=0,
                red_s=int(round(controller.red_total)),
                yellow_s=0,
                saved_s=int(round(controller.total_saved))
            )
    

    y_offset = 30
    line_height = 35
    
    cars_text = f"Cars in Region: {vehicles_in_polygon}"
    text_size = cv2.getTextSize(cars_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, cars_text, (img.shape[1] - text_size[0] - 20, y_offset), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
    
    density_text = f"Density: {density:.2f}"
    text_size = cv2.getTextSize(density_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, density_text, (img.shape[1] - text_size[0] - 20, y_offset + line_height), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    

    avg_density_text = f"Avg Density (5s): {avg_density:.2f}"
    text_size = cv2.getTextSize(avg_density_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, avg_density_text, (img.shape[1] - text_size[0] - 20, y_offset + 2*line_height), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

    # Overlay current phase and remaining time
    phase_info = controller.get_phase_and_times()
    phase_text = f"Phase: {phase_info['phase']} | GreenLeft: {phase_info['remaining_green']}s | Saved: {phase_info['total_saved']}s"
    text_size = cv2.getTextSize(phase_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
    cv2.putText(img, phase_text, (img.shape[1] - text_size[0] - 20, y_offset + 3*line_height), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 165, 255), 2)
    
    cv2.imshow("Image", img)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()