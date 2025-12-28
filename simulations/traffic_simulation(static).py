import pygame
import math
import random
import time

# --- Pygame Setup ---
pygame.init()
WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Realistic Driving Simulation")
clock = pygame.time.Clock()
font = pygame.font.SysFont('Inter', 30, bold=True)
small_font = pygame.font.SysFont('Inter', 24, bold=True)


# --- Colors ---
ASPHALT = '#4a5568'
BLACK = '#000000'
WHITE = '#FFFFFF'
FAINT_WHITE = (255, 255, 255, 100) # For zebra crossing
DARK_GRAY = '#333333'
POLE_GRAY = '#666666'
OFF_LIGHT = '#444444'

# --- Configuration ---
LANE_WIDTH = 35
CYCLE_PER_DIRECTION_SECONDS = 90
YELLOW_LIGHT_DURATION = 5

# --- Vehicle Definitions ---
vehicle_types = {
    'car': {'width': 30, 'height': 15, 'color': lambda: pygame.Color(random.randint(50, 150), random.randint(100, 200), 255)},
    'truck': {'width': 50, 'height': 18, 'color': lambda: pygame.Color(random.randint(150, 200), random.randint(100, 150), 50)},
    'bike': {'width': 15, 'height': 8, 'color': lambda: pygame.Color(random.randint(220, 255), random.randint(50, 150), 50)},
    'ambulance': {'width': 35, 'height': 16, 'color': lambda: pygame.Color('white')}
}

# --- Lane & Intersection Definitions ---
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

intersection_rect = pygame.Rect(v_road_left, h_road_top, v_road_right - v_road_left, h_road_bottom - h_road_top)

# --- Traffic Light Management ---
class TrafficLightManager:
    def __init__(self):
        self.directions = ['N', 'E', 'S', 'W']
        self.current_index = 0
        self.last_switch_time = time.time()

    def update(self):
        elapsed_time = time.time() - self.last_switch_time
        if elapsed_time > CYCLE_PER_DIRECTION_SECONDS:
            self.current_index = (self.current_index + 1) % len(self.directions)
            self.last_switch_time = time.time()

    def get_active_direction(self):
        return self.directions[self.current_index]

    def is_yellow(self):
        elapsed_time = time.time() - self.last_switch_time
        return elapsed_time > (CYCLE_PER_DIRECTION_SECONDS - YELLOW_LIGHT_DURATION)

traffic_light_manager = TrafficLightManager()

# --- Vehicle Class ---
class Vehicle:
    def __init__(self, direction):
        self.original_direction = direction
        self.base_speed = random.uniform(0.9, 1.3)
        self.speed = self.base_speed
        self.steer_speed = random.uniform(1.0, 2.0)
        self.is_stopped = False
        self.flash_timer = 0
        self.is_turning_left = False
        self.is_inside_intersection = False
        self.intersection_entry_time = 0
        self.turn_decision_made = False # U-TURN BUG FIX
        self.reset(direction)

    def reset(self, direction):
        self.direction = direction
        self.is_turning_left = False
        self.is_inside_intersection = False
        self.intersection_entry_time = 0
        self.turn_decision_made = False # U-TURN BUG FIX
        self.speed = self.base_speed
        
        self.type = random.choice(list(vehicle_types.keys()))
        self.width = vehicle_types[self.type]['width']
        self.height = vehicle_types[self.type]['height']
        self.color = vehicle_types[self.type]['color']()

        spawn_offset = 100 + random.uniform(0, 400)
        if direction == 'E':
            self.x, self.lane = -spawn_offset, random.choice(lanes['E'])
            self.y, self.angle = self.lane, 0
        elif direction == 'W':
            self.x, self.lane = WIDTH + spawn_offset, random.choice(lanes['W'])
            self.y, self.angle = self.lane, 180
        elif direction == 'S':
            self.y, self.lane = -spawn_offset, random.choice(lanes['S'])
            self.x, self.angle = self.lane, -90
        elif direction == 'N':
            self.y, self.lane = HEIGHT + spawn_offset, random.choice(lanes['N'])
            self.x, self.angle = self.lane, 90
        
        self.rect = pygame.Rect(self.x - self.width/2, self.y - self.height/2, self.width, self.height)


    def update(self, all_vehicles):
        if self.type == 'ambulance':
            self.flash_timer = (self.flash_timer + 1) % 30

        was_outside = not self.is_inside_intersection
        self.is_inside_intersection = intersection_rect.collidepoint(self.x, self.y)
        if self.is_inside_intersection and was_outside:
            self.intersection_entry_time = time.time()

        stopped_by_light = self.check_traffic_light()
        stopped_by_traffic = self.check_for_collision(all_vehicles)
        yielding_for_turn = self.is_turning_left and self.check_oncoming_traffic(all_vehicles)
        stopped_in_intersection = self.is_inside_intersection and self.check_intersection_collision(all_vehicles)

        self.is_stopped = stopped_by_light or stopped_by_traffic or yielding_for_turn or stopped_in_intersection
        self.speed = 0 if self.is_stopped else self.base_speed

        if not self.is_stopped:
            self.handle_intersection()

        # Steering
        target_x, target_y = self.x, self.y
        if self.direction in ['E', 'W']:
            target_y = self.lane
            target_x += 100 if self.direction == 'E' else -100
        else:
            target_x = self.lane
            target_y += 100 if self.direction == 'S' else -100
        
        angle_to_target = math.degrees(math.atan2(-(target_y - self.y), target_x - self.x))
        angle_diff = (angle_to_target - self.angle + 180) % 360 - 180
        turn = max(-self.steer_speed, min(self.steer_speed, angle_diff))
        self.angle += turn

        # Movement
        rad = math.radians(self.angle)
        self.x += math.cos(rad) * self.speed
        self.y -= math.sin(rad) * self.speed

        reset_buffer = 500
        if not (-reset_buffer < self.x < WIDTH + reset_buffer and -reset_buffer < self.y < HEIGHT + reset_buffer):
            self.reset(self.original_direction)

    def check_for_collision(self, all_vehicles):
        safe_dist = self.width * 1.5 + 5
        for other in all_vehicles:
            if other is self or other.direction != self.direction or other.lane != self.lane:
                continue
            dist = math.hypot(self.x - other.x, self.y - other.y)
            if dist < safe_dist:
                if (self.direction == 'E' and other.x > self.x) or \
                   (self.direction == 'W' and other.x < self.x) or \
                   (self.direction == 'S' and other.y > self.y) or \
                   (self.direction == 'N' and other.y < self.y):
                    return True
        return False

    def check_intersection_collision(self, all_vehicles):
        safe_dist = self.width * 0.8 # Tighter distance for intersection checks
        for other in all_vehicles:
            if other is self or not other.is_inside_intersection:
                continue
            dist = math.hypot(self.x - other.x, self.y - other.y)
            if dist < safe_dist + other.width * 0.8:
                # Priority rule: the vehicle that entered later must yield
                if self.intersection_entry_time > other.intersection_entry_time:
                    return True
        return False

    def check_oncoming_traffic(self, all_vehicles):
        oncoming_map = {'E': 'W', 'W': 'E', 'N': 'S', 'S': 'N'}
        oncoming_dir = oncoming_map[self.original_direction]
        danger_zone = 2.5

        for other in all_vehicles:
            if other.direction != oncoming_dir:
                continue
            
            threat = False
            if self.original_direction == 'E' and other.x < v_road_right + other.width and other.x > self.x - other.width * danger_zone:
                threat = True
            elif self.original_direction == 'W' and other.x > v_road_left - other.width and other.x < self.x + other.width * danger_zone:
                threat = True
            elif self.original_direction == 'S' and other.y < h_road_bottom + other.height and other.y > self.y - other.height * danger_zone:
                threat = True
            elif self.original_direction == 'N' and other.y > h_road_top - other.height and other.y < self.y + other.height * danger_zone:
                threat = True
            
            if threat and not other.is_stopped:
                return True
        return False

    def check_traffic_light(self):
        if self.is_inside_intersection:
            return False

        active_dir = traffic_light_manager.get_active_direction()
        is_yellow = traffic_light_manager.is_yellow()
        is_red = not (self.direction == active_dir and not is_yellow)

        stop_buffer = 35 + 45 # Zebra crossing width
        stop_lines = {
            'E': v_road_left - stop_buffer, 'W': v_road_right + stop_buffer,
            'S': h_road_top - stop_buffer, 'N': h_road_bottom + stop_buffer
        }
        
        is_approaching = False
        if self.direction == 'E' and stop_lines['E'] - self.width < self.x < stop_lines['E'] + 35:
            is_approaching = True
        elif self.direction == 'W' and stop_lines['W'] + self.width > self.x > stop_lines['W'] - 35:
            is_approaching = True
        elif self.direction == 'S' and stop_lines['S'] - self.height < self.y < stop_lines['S'] + 35:
            is_approaching = True
        elif self.direction == 'N' and stop_lines['N'] + self.height > self.y > stop_lines['N'] - 35:
            is_approaching = True

        return is_approaching and is_red

    def handle_intersection(self):
        # U-TURN BUG FIX: A turn decision is now made only ONCE upon entering the intersection.
        if self.is_inside_intersection and not self.turn_decision_made:
            self.turn_decision_made = True
            decision = random.random()
            if decision < 0.4: self.turn_right()
            elif decision < 0.6: self.turn_left()
        elif not self.is_inside_intersection:
            # Reset flags once the vehicle is clear of the intersection
            self.turn_decision_made = False
            self.is_turning_left = False

    def turn_right(self):
        turn_map = {'E': 'S', 'W': 'N', 'S': 'W', 'N': 'E'}
        self.direction = turn_map[self.direction]
        self.lane = lanes[self.direction][0]

    def turn_left(self):
        self.is_turning_left = True
        turn_map = {'E': 'N', 'W': 'S', 'S': 'E', 'N': 'W'}
        self.direction = turn_map[self.direction]
        self.lane = lanes[self.direction][1]

    def draw(self, surface):
        vehicle_surf = pygame.Surface((self.width + 4, self.height + 4), pygame.SRCALPHA)
        pygame.draw.rect(vehicle_surf, (0,0,0,50), (2, 2, self.width, self.height))
        pygame.draw.rect(vehicle_surf, self.color, (0, 0, self.width, self.height))
        if self.type != 'bike':
            cabin_width = self.width * 0.6
            cabin_height = self.height * 0.9
            cabin_x = self.width * 0.2 if self.type != 'truck' else self.width * 0.1
            cabin_color = (150, 200, 255, 200) if self.type == 'ambulance' else (0,0,0,80)
            pygame.draw.rect(vehicle_surf, cabin_color, (cabin_x, (self.height - cabin_height)/2, cabin_width, cabin_height))
        wheel_width, wheel_height = self.width * 0.2, 2
        pygame.draw.rect(vehicle_surf, BLACK, (self.width * 0.2, -wheel_height, wheel_width, wheel_height))
        pygame.draw.rect(vehicle_surf, BLACK, (self.width * 0.7, -wheel_height, wheel_width, wheel_height))
        pygame.draw.rect(vehicle_surf, BLACK, (self.width * 0.2, self.height, wheel_width, wheel_height))
        pygame.draw.rect(vehicle_surf, BLACK, (self.width * 0.7, self.height, wheel_width, wheel_height))
        pygame.draw.rect(vehicle_surf, 'yellow', (self.width - 2, self.height * 0.2, 2, 2))
        pygame.draw.rect(vehicle_surf, 'yellow', (self.width - 2, self.height * 0.8 - 2, 2, 2))
        pygame.draw.rect(vehicle_surf, 'red', (0, self.height * 0.2, 2, 2))
        pygame.draw.rect(vehicle_surf, 'red', (0, self.height * 0.8 - 2, 2, 2))
        if self.type == 'ambulance' and self.flash_timer > 15:
            pygame.draw.rect(vehicle_surf, 'blue', (self.width/2 - 3, -4, 6, 4))
        rotated_surf = pygame.transform.rotate(vehicle_surf, self.angle)
        new_rect = rotated_surf.get_rect(center=(self.x, self.y))
        surface.blit(rotated_surf, new_rect)


def draw_road(surface):
    surface.fill(ASPHALT)
    pygame.draw.rect(surface, DARK_GRAY, (0, h_road_top, WIDTH, h_road_bottom - h_road_top))
    pygame.draw.rect(surface, DARK_GRAY, (v_road_left, 0, v_road_right - v_road_left, HEIGHT))
    dash_len = 15
    for y in [h_road_top + LANE_WIDTH, h_road_bottom - LANE_WIDTH, HEIGHT // 2]:
        for x in range(0, WIDTH, dash_len * 2):
            if (y == HEIGHT // 2 and v_road_left < x < v_road_right): continue
            pygame.draw.line(surface, WHITE, (x, y), (x + dash_len, y), 3)
    for x in [v_road_left + LANE_WIDTH, v_road_right - LANE_WIDTH, WIDTH // 2]:
        for y in range(0, HEIGHT, dash_len * 2):
            if (x == WIDTH // 2 and h_road_top < y < h_road_bottom): continue
            pygame.draw.line(surface, WHITE, (x, y), (x, y + dash_len), 3)
    stop_offset = 35
    crossing_width = 45
    stripe_width = 8
    zebra_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for i in range(0, LANE_WIDTH * 4, stripe_width * 2):
        pygame.draw.rect(zebra_surface, FAINT_WHITE, (v_road_left - stop_offset - crossing_width, h_road_top + i, crossing_width, stripe_width))
        pygame.draw.rect(zebra_surface, FAINT_WHITE, (v_road_right + stop_offset, h_road_top + i, crossing_width, stripe_width))
    for i in range(0, LANE_WIDTH * 4, stripe_width * 2):
        pygame.draw.rect(zebra_surface, FAINT_WHITE, (v_road_left + i, h_road_top - stop_offset - crossing_width, stripe_width, crossing_width))
        pygame.draw.rect(zebra_surface, FAINT_WHITE, (v_road_left + i, h_road_bottom + stop_offset, stripe_width, crossing_width))
    surface.blit(zebra_surface, (0,0))


def draw_traffic_lights(surface):
    active_dir = traffic_light_manager.get_active_direction()
    is_yellow = traffic_light_manager.is_yellow()
    
    def get_color(direction):
        is_active = direction == active_dir
        if is_yellow and is_active: return 'yellow'
        if not is_yellow and is_active: return 'lime'
        return 'red'

    def draw_signal(x, y, direction, orientation):
        is_vertical = orientation == 'vertical'
        w, h = (18, 48) if is_vertical else (48, 18)
        radius = 6
        
        is_bottom = y > HEIGHT / 2
        housing_y = y + (25 if is_bottom else -25 - h)

        pygame.draw.rect(surface, BLACK, (x - w/2, housing_y, w, h))

        lights = [
            {'color': 'red', 'pos': (0, -h/2 + radius + 6) if is_vertical else (-w/2 + radius + 6, 0)},
            {'color': 'yellow', 'pos': (0, 0) if is_vertical else (0, 0)},
            {'color': 'lime', 'pos': (0, h/2 - radius - 6) if is_vertical else (w/2 - radius - 6, 0)}
        ]
        
        for light in lights:
            color = light['color'] if get_color(direction) == light['color'] else OFF_LIGHT
            pygame.draw.circle(surface, color, (x + light['pos'][0], housing_y + h/2 + light['pos'][1]), radius)

    offset = 80
    draw_signal(v_road_left - offset, h_road_top, 'N', 'vertical')
    draw_signal(v_road_right + offset, h_road_top, 'E', 'horizontal')
    draw_signal(v_road_left - offset, h_road_bottom, 'W', 'horizontal')
    draw_signal(v_road_right + offset, h_road_bottom, 'S', 'vertical')


def draw_timer(surface):
    elapsed = time.time() - traffic_light_manager.last_switch_time
    remaining = max(0, CYCLE_PER_DIRECTION_SECONDS - elapsed)
    active_dir = traffic_light_manager.get_active_direction()
    is_yellow = traffic_light_manager.is_yellow()
    
    dir_map = {'N': 'North', 'E': 'East', 'S': 'South', 'W': 'West'}
    
    timer_bg = pygame.Surface((250, 90), pygame.SRCALPHA)
    timer_bg.fill((0,0,0,128))
    surface.blit(timer_bg, (10,10))
    
    text1 = small_font.render("Green Light For:", True, WHITE)
    surface.blit(text1, (25, 25))
    
    dir_color = 'yellow' if is_yellow else 'lime'
    text2 = font.render(dir_map[active_dir], True, dir_color)
    surface.blit(text2, (180, 22))
    
    text3 = small_font.render(f"Time Left: {math.ceil(remaining)}s", True, WHITE)
    surface.blit(text3, (25, 60))


def main():
    vehicles = [Vehicle(dir) for dir in ['N', 'E', 'S', 'W'] for _ in range(7)]
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        traffic_light_manager.update()
        for v in vehicles:
            v.update(vehicles)

        draw_road(screen)
        draw_traffic_lights(screen)
        for v in vehicles:
            v.draw(screen)
        draw_timer(screen)
        
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == '__main__':
    main()
