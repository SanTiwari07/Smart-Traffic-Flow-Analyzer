import pygame
import cv2
import numpy as np
import math
import random
import time

# --- Pygame Setup ---
pygame.init()
WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dynamic Traffic Simulation")
clock = pygame.time.Clock()
font = pygame.font.SysFont('Arial', 24, bold=True)
small_font = pygame.font.SysFont('Arial', 18)

# --- Colors ---
ASPHALT = '#4a5568'
BLACK = '#000000'
WHITE = '#FFFFFF'
DARK_GRAY = '#333333'
GREEN_BOX = '#22c55e'
WINDSHIELD_COLOR = '#a7e4f2'
LIGHT_HOUSING = '#2d3748'
RED_LIGHT_ON = '#ef4444'
RED_LIGHT_OFF = '#450a0a'
YELLOW_LIGHT_ON = '#facc15'
YELLOW_LIGHT_OFF = '#422006'
GREEN_LIGHT_ON = '#4ade80'
GREEN_LIGHT_OFF = '#14532d'

# --- Configuration ---
LANE_WIDTH = 35
YELLOW_LIGHT_DURATION = 3
VEHICLE_COUNT_PER_DIRECTION = 7

# --- Road & Intersection Geometry ---
h_road_top = HEIGHT // 2 - LANE_WIDTH * 2
h_road_bottom = HEIGHT // 2 + LANE_WIDTH * 2
v_road_left = WIDTH // 2 - LANE_WIDTH * 2
v_road_right = WIDTH // 2 + LANE_WIDTH * 2

lanes = {
    'E': [h_road_top + LANE_WIDTH * 0.5, h_road_top + LANE_WIDTH * 1.5],
    'W': [h_road_bottom - LANE_WIDTH * 0.5, h_road_bottom - LANE_WIDTH * 1.5],
    'S': [v_road_left + LANE_WIDTH * 0.5, v_road_left + LANE_WIDTH * 1.5],
    'N': [v_road_right - LANE_WIDTH * 0.5, v_road_right - LANE_WIDTH * 1.5]
}

# --- Vehicle Class ---
class Vehicle:
    """Represents a single vehicle that moves straight."""
    def __init__(self, direction):
        self.original_direction = direction
        self.base_speed = random.uniform(1.2, 1.8)
        self.speed = self.base_speed
        self.is_stopped = False
        self.reset(direction)

    def reset(self, direction):
        """Resets the vehicle's state and position."""
        self.direction = direction
        self.width, self.height = 32, 16
        self.color = pygame.Color(random.randint(60, 200), random.randint(120, 220), 255)

        spawn_offset = 150 + random.uniform(0, 400)
        if direction == 'E': self.x, self.y, self.angle = -spawn_offset, random.choice(lanes['E']), 0
        elif direction == 'W': self.x, self.y, self.angle = WIDTH + spawn_offset, random.choice(lanes['W']), 180
        elif direction == 'S': self.x, self.y, self.angle = random.choice(lanes['S']), -spawn_offset, 270
        elif direction == 'N': self.x, self.y, self.angle = random.choice(lanes['N']), HEIGHT + spawn_offset, 90

    def update(self, all_vehicles, traffic_manager):
        """Updates the vehicle's position and state."""
        stopped_by_light = self.check_traffic_light(traffic_manager)
        stopped_by_traffic = self.check_collision(all_vehicles)
        
        self.is_stopped = stopped_by_light or stopped_by_traffic
        self.speed = 0 if self.is_stopped else self.base_speed

        if not self.is_stopped:
            rad = math.radians(self.angle)
            self.x += math.cos(rad) * self.speed
            self.y -= math.sin(rad) * self.speed 

        if not (-250 < self.x < WIDTH + 250 and -250 < self.y < HEIGHT + 250):
            self.reset(self.original_direction)

    def check_traffic_light(self, traffic_manager):
        """Checks if the vehicle needs to stop for a traffic light."""
        active_dir = traffic_manager.get_active_direction()
        is_yellow = traffic_manager.is_yellow()
        is_red = not (self.direction == active_dir and not is_yellow)
        
        stop_distance = 70
        approaching = False
        if self.direction == 'E' and v_road_left - stop_distance < self.x < v_road_left: approaching = True
        elif self.direction == 'W' and v_road_right < self.x < v_road_right + stop_distance: approaching = True
        elif self.direction == 'S' and h_road_top - stop_distance < self.y < h_road_top: approaching = True
        elif self.direction == 'N' and h_road_bottom < self.y < h_road_bottom + stop_distance: approaching = True
            
        return approaching and is_red

    def check_collision(self, all_vehicles):
        """Checks for collisions with other vehicles."""
        safe_distance = 45
        for other in all_vehicles:
            if other is self or other.direction != self.direction: continue
            
            distance = math.hypot(self.x - other.x, self.y - other.y)
            if distance < safe_distance:
                is_in_front = ((self.direction == 'E' and other.x > self.x) or
                               (self.direction == 'W' and other.x < self.x) or
                               (self.direction == 'S' and other.y > self.y) or
                               (self.direction == 'N' and other.y < self.y))
                if is_in_front: return True
        return False

    def draw(self, surface):
        """Draws the vehicle on the screen with an improved shape."""
        half_w, half_h = self.width / 2, self.height / 2
        body_points = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
        
        cabin_w, cabin_h, cabin_offset = half_w * 0.8, half_h * 0.9, half_w * 0.1
        cabin_points = [(-cabin_w + cabin_offset, -cabin_h), (cabin_w + cabin_offset, -cabin_h),
                        (cabin_w*0.8 + cabin_offset, cabin_h), (-cabin_w*0.8 + cabin_offset, cabin_h)]

        rad = math.radians(-self.angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        
        def rotate_point(p):
            x, y = p
            return ((x * cos_a - y * sin_a) + self.x, (x * sin_a + y * cos_a) + self.y)

        rotated_body = [rotate_point(p) for p in body_points]
        rotated_cabin = [rotate_point(p) for p in cabin_points]
        
        pygame.draw.polygon(surface, self.color, rotated_body)
        pygame.draw.polygon(surface, WINDSHIELD_COLOR, rotated_cabin)
        pygame.draw.polygon(surface, self.color.lerp(BLACK, 0.4), rotated_body, 2)

# --- OpenCV Detector and Controller ---
class OpenCVDensityDetector:
    """Handles vehicle detection using the vision-based 'percent concept'."""
    def __init__(self):
        self.masks = self._create_road_masks()
        self.density_history = {'N': [], 'S': [], 'E': [], 'W': []}
        
    def _create_road_masks(self):
        """Creates masks for each direction to focus detection."""
        masks = {}
        mask_canvas = np.zeros((HEIGHT, WIDTH), dtype=np.uint8)
        masks['N'] = cv2.rectangle(mask_canvas.copy(), (v_road_left, h_road_bottom), (v_road_right, HEIGHT), 255, -1)
        masks['S'] = cv2.rectangle(mask_canvas.copy(), (v_road_left, 0), (v_road_right, h_road_top), 255, -1)
        masks['E'] = cv2.rectangle(mask_canvas.copy(), (0, h_road_top), (v_road_left, h_road_bottom), 255, -1)
        masks['W'] = cv2.rectangle(mask_canvas.copy(), (v_road_right, h_road_top), (WIDTH, h_road_bottom), 255, -1)
        return masks

    def calculate_all_densities(self, frame):
        """Calculates density for all directions from a given frame using pixel analysis."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Threshold to isolate vehicles from the dark road
        _, vehicle_binary = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY)
        
        densities = {}
        for direction, mask in self.masks.items():
            total_mask_area = np.sum(mask > 0)
            # Count pixels that are both vehicles (white) and within the mask
            vehicle_area = np.sum(cv2.bitwise_and(vehicle_binary, vehicle_binary, mask=mask) > 0)
            
            density = (vehicle_area / total_mask_area) if total_mask_area > 0 else 0.0
            densities[direction] = min(density * 4, 1.0) # Scaling factor for sensitivity
            
            self.density_history[direction].append(densities[direction])
            if len(self.density_history[direction]) > 15:
                self.density_history[direction].pop(0)
        return densities

    def get_sliding_average(self, direction, window_size=5):
        """Calculates a smoothed density value over a time window."""
        history = self.density_history.get(direction, [])
        if not history: return 0.0
        actual_window = min(window_size, len(history))
        return np.mean(history[-actual_window:])

class DynamicTrafficController:
    """Implements the N-E-S-W clockwise traffic logic with dynamic timing."""
    def __init__(self, detector):
        self.detector = detector
        self.directions = ['N', 'E', 'S', 'W']
        self.current_index = 0
        
        self.signal_start_time = time.time()
        self.current_duration = 90.0
        self.is_in_yellow = False
        self.yellow_start_time = 0
        
        # Parameters from your logic
        self.static_duration = 90
        self.best_case = 30
        self.worst_case = 90
        self.stable_period = 10
        self.decision_interval = 5
        self.last_decision_time = 0
        self.low_density_start_time = None

    def update(self, densities):
        """Main update loop for the controller."""
        current_time = time.time()
        elapsed_since_switch = current_time - self.signal_start_time

        if self.is_in_yellow:
            if current_time - self.yellow_start_time >= YELLOW_LIGHT_DURATION:
                self._switch_to_next_direction()
            return
        
        if elapsed_since_switch >= (self.current_duration - YELLOW_LIGHT_DURATION):
            self.is_in_yellow = True
            self.yellow_start_time = current_time
            return

        # Start applying rules after the stable period
        if elapsed_since_switch > self.stable_period and \
           current_time - self.last_decision_time > self.decision_interval:
            self._apply_dynamic_logic(densities, elapsed_since_switch)
            self.last_decision_time = current_time

    def _apply_dynamic_logic(self, densities, elapsed_time):
        """Applies the density-based rules to adjust the light duration."""
        active_dir = self.get_active_direction()
        current_density = self.detector.get_sliding_average(active_dir, 5)
        
        print(f"\n--- Decision Check at {elapsed_time:.1f}s for {active_dir} (Density: {current_density:.3f}) ---")
        
        old_duration = self.current_duration
        new_duration = old_duration

        # --- YOUR DYNAMIC LOGIC, CORRECTLY IMPLEMENTED ---
        if current_density < 0.3:
            if self.low_density_start_time is None:
                self.low_density_start_time = elapsed_time
                print("Low density detected. Starting 5s timer.")
            
            # Rule 6: If density < 0.3 for more than 5 seconds
            if elapsed_time - self.low_density_start_time >= 5:
                time_left = old_duration - elapsed_time
                reduction = time_left * 0.40
                new_duration = old_duration - reduction
                print(f"Rule 6: Low density for >5s -> Reducing total duration by {reduction:.1f}s")
                self.low_density_start_time = None # Reset timer after it fires
        else:
            self.low_density_start_time = None # Reset timer if density goes up
            # Rule 7: If density is between 0.4 and 0.6
            if 0.4 <= current_density <= 0.6:
                time_left = old_duration - elapsed_time
                reduction = time_left * 0.25
                new_duration = old_duration - reduction
                print(f"Rule 7: Medium density -> Reducing total duration by {reduction:.1f}s")
            else: # Rule 7 (cont.): Density >= 0.7
                print("Rule 7: High density -> No change.")
            
        # Enforce best/worst case bounds
        self.current_duration = max(self.best_case, min(new_duration, self.worst_case))
        
        if old_duration != self.current_duration:
            print(f"Duration adjusted: {old_duration:.1f}s -> {self.current_duration:.1f}s")

    def _switch_to_next_direction(self):
        """Switches the signal to the next direction in the clockwise sequence."""
        old_dir = self.get_active_direction()
        self.current_index = (self.current_index + 1) % len(self.directions)
        new_dir = self.get_active_direction()

        # Reset state for the new signal
        self.signal_start_time = time.time()
        self.is_in_yellow = False
        self.last_decision_time = self.signal_start_time
        self.current_duration = self.static_duration # Reset to 90s
        self.low_density_start_time = None

        print(f"\n{'='*15} SIGNAL SWITCH {'='*15}")
        print(f"From: {old_dir} -> To: {new_dir}")
        print(f"Resetting duration to: {self.current_duration}s")
        print(f"{'='*47}\n")

    def get_active_direction(self):
        return self.directions[self.current_index]

    def is_yellow(self):
        return self.is_in_yellow

    def get_remaining_time(self):
        if self.is_in_yellow:
            return max(0, YELLOW_LIGHT_DURATION - (time.time() - self.yellow_start_time))
        return max(0, self.current_duration - (time.time() - self.signal_start_time))

# --- Drawing Functions ---
def draw_road_and_crossings(surface):
    surface.fill(ASPHALT)
    pygame.draw.rect(surface, DARK_GRAY, (0, h_road_top, WIDTH, h_road_bottom - h_road_top))
    pygame.draw.rect(surface, DARK_GRAY, (v_road_left, 0, v_road_right - v_road_left, HEIGHT))
    
    dash_length = 20
    for y in [h_road_top + LANE_WIDTH, h_road_bottom - LANE_WIDTH]:
        for x in range(0, WIDTH, dash_length * 2):
            if not v_road_left < x < v_road_right:
                pygame.draw.line(surface, WHITE, (x, y), (x + dash_length, y), 3)
    
    for x in [v_road_left + LANE_WIDTH, v_road_right - LANE_WIDTH]:
        for y in range(0, HEIGHT, dash_length * 2):
            if not h_road_top < y < h_road_bottom:
                pygame.draw.line(surface, WHITE, (x, y), (x, y + dash_length), 3)

    stripe_width, stripe_gap, box_size = 8, 6, 40
    for x in range(v_road_left, v_road_right, stripe_width + stripe_gap):
        pygame.draw.rect(surface, WHITE, (x, h_road_top - 20, stripe_width, 20))
        pygame.draw.rect(surface, WHITE, (x, h_road_bottom, stripe_width, 20))
    pygame.draw.rect(surface, GREEN_BOX, (v_road_left - box_size - 5, h_road_top - box_size - 5, box_size, box_size))
    pygame.draw.rect(surface, GREEN_BOX, (v_road_right + 5, h_road_bottom + 5, box_size, box_size))

    for y in range(h_road_top, h_road_bottom, stripe_width + stripe_gap):
        pygame.draw.rect(surface, WHITE, (v_road_left - 20, y, 20, stripe_width))
        pygame.draw.rect(surface, WHITE, (v_road_right, y, 20, stripe_width))
    pygame.draw.rect(surface, GREEN_BOX, (v_road_right + 5, h_road_top - box_size - 5, box_size, box_size))
    pygame.draw.rect(surface, GREEN_BOX, (v_road_left - box_size - 5, h_road_bottom + 5, box_size, box_size))

def draw_traffic_light_housing(surface, x, y, is_vertical):
    width, height = (25, 65) if is_vertical else (65, 25)
    housing_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(surface, LIGHT_HOUSING, housing_rect, border_radius=5)
    return housing_rect

def draw_traffic_lights(surface, traffic_manager):
    active_dir = traffic_manager.get_active_direction()
    is_yellow = traffic_manager.is_yellow()

    light_configs = {
        'S': {'pos': (v_road_right + 10, h_road_top - 75), 'vertical': True},
        'W': {'pos': (v_road_right + 35, h_road_bottom + 10), 'vertical': False},
        'N': {'pos': (v_road_left - 35, h_road_bottom + 10), 'vertical': True},
        'E': {'pos': (v_road_left - 100, h_road_top - 35), 'vertical': False}
    }

    for direction, cfg in light_configs.items():
        rect = draw_traffic_light_housing(surface, cfg['pos'][0], cfg['pos'][1], cfg['vertical'])
        
        is_active = (direction == active_dir)
        red_on = not is_active
        yellow_on = is_active and is_yellow
        green_on = is_active and not is_yellow

        if cfg['vertical']:
            pygame.draw.circle(surface, RED_LIGHT_ON if red_on else RED_LIGHT_OFF, (rect.centerx, rect.top + 12), 8)
            pygame.draw.circle(surface, YELLOW_LIGHT_ON if yellow_on else YELLOW_LIGHT_OFF, (rect.centerx, rect.centery), 8)
            pygame.draw.circle(surface, GREEN_LIGHT_ON if green_on else GREEN_LIGHT_OFF, (rect.centerx, rect.bottom - 12), 8)
        else:
            pygame.draw.circle(surface, RED_LIGHT_ON if red_on else RED_LIGHT_OFF, (rect.left + 12, rect.centery), 8)
            pygame.draw.circle(surface, YELLOW_LIGHT_ON if yellow_on else YELLOW_LIGHT_OFF, (rect.centerx, rect.centery), 8)
            pygame.draw.circle(surface, GREEN_LIGHT_ON if green_on else GREEN_LIGHT_OFF, (rect.right - 12, rect.centery), 8)

def draw_info_panel(surface, traffic_manager, densities):
    active_dir = traffic_manager.get_active_direction()
    remaining_time = traffic_manager.get_remaining_time()
    
    info_texts = [
        f"Active Signal: {active_dir}",
        f"Time Left: {remaining_time:.1f}s",
        f"Total Duration: {traffic_manager.current_duration:.1f}s",
        "--- Densities ---"
    ]
    for d in ['N', 'E', 'S', 'W']:
        is_active = (d == active_dir)
        info_texts.append(f"{'>>' if is_active else ''} {d}: {densities.get(d, 0):.2f}")
    
    for i, text in enumerate(info_texts):
        text_surface = small_font.render(text, True, WHITE)
        surface.blit(text_surface, (10, 10 + i * 22))

# --- Main Simulation Loop ---
def main():
    print("--- DYNAMIC TRAFFIC SIMULATION (USER LOGIC IMPLEMENTED) ---")
    
    detector = OpenCVDensityDetector()
    traffic_controller = DynamicTrafficController(detector)
    
    vehicles = [Vehicle(d) for d in ['N', 'E', 'S', 'W'] for _ in range(VEHICLE_COUNT_PER_DIRECTION)]
    
    running = True
    frame_count = 0
    densities = {}

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False
        
        # OpenCV processing happens every few frames for performance
        if frame_count % 3 == 0:
            pygame_array = pygame.surfarray.array3d(screen)
            frame = np.transpose(pygame_array, (1, 0, 2))
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            densities = detector.calculate_all_densities(frame)
        
        # Update controller and vehicles every frame
        traffic_controller.update(densities)
        for vehicle in vehicles:
            vehicle.update(vehicles, traffic_controller)
        
        # Drawing
        draw_road_and_crossings(screen)
        for vehicle in vehicles:
            vehicle.draw(screen)
        draw_traffic_lights(screen, traffic_controller)
        draw_info_panel(screen, traffic_controller, densities)
        
        pygame.display.flip()
        clock.tick(60)
        frame_count += 1
    
    pygame.quit()
    print("Simulation ended.")

if __name__ == '__main__':
    main()
