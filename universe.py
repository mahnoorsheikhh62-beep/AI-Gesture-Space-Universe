
import cv2
import mediapipe as mp
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math
import threading
import time
import random

# =========================================================
# AI GESTURE SPACE UNIVERSE
# =========================================================

WIDTH, HEIGHT = 1100, 750
NUM_PARTICLES = 1800

# SMALL CAMERA WINDOW
CAMERA_WIDTH = 350
CAMERA_HEIGHT = 260

lock = threading.Lock()

shared_data = {
    "mode": 1,
    "target_x": 0.0,
    "target_y": 0.0,
    "zoom": 12.0,
    "pinching": False,
    "frame": None,
    "running": True
}

# =========================================================
# PARTICLE SHAPE GENERATORS
# =========================================================

np.random.seed(42)


def random_sphere(count, radius=3.0):
    points = np.random.normal(size=(count, 3))
    lengths = np.linalg.norm(points, axis=1)
    lengths[lengths == 0] = 1
    points /= lengths[:, None]
    distances = np.random.uniform(0.1, radius, count)
    return points * distances[:, None]


# MODE 1: COSMOS
pos_space = random_sphere(NUM_PARTICLES, 4.0)


# MODE 2: SATURN
pos_planet = np.zeros((NUM_PARTICLES, 3))
NUM_SPHERE = 850

phi = np.random.uniform(0, 2*np.pi, NUM_SPHERE)
costheta = np.random.uniform(-1, 1, NUM_SPHERE)
theta = np.arccos(costheta)

pos_planet[:NUM_SPHERE, 0] = 1.25*np.sin(theta)*np.cos(phi)
pos_planet[:NUM_SPHERE, 1] = 1.25*np.sin(theta)*np.sin(phi)
pos_planet[:NUM_SPHERE, 2] = 1.25*np.cos(theta)

for i in range(NUM_SPHERE, NUM_PARTICLES):
    angle = np.random.uniform(0, 2*np.pi)
    radius = np.random.uniform(1.7, 3.8)

    pos_planet[i] = [
        radius*np.cos(angle),
        np.random.uniform(-0.07, 0.07),
        radius*np.sin(angle)
    ]


# MODE 3: I LOVE YOU
text_img = np.zeros((200, 800), dtype=np.uint8)

cv2.putText(
    text_img,
    "I LOVE YOU",
    (20, 130),
    cv2.FONT_HERSHEY_SIMPLEX,
    3.5,
    255,
    12,
    cv2.LINE_AA
)

yy, xx = np.where(text_img > 0)

text_points = np.column_stack((
    (xx-400)/70,
    -(yy-100)/70,
    np.random.uniform(-0.1, 0.1, len(xx))
))

pos_text = text_points[
    np.random.choice(len(text_points), NUM_PARTICLES)
].copy()


# MODE 4: HEART
t = np.random.uniform(-np.pi, np.pi, NUM_PARTICLES)
p = np.random.uniform(-np.pi, np.pi, NUM_PARTICLES)

pos_heart = np.column_stack((
    1.7*np.sin(t)**3,
    1.7*(np.cos(t)-0.35*np.cos(2*t)
         -0.15*np.cos(3*t)-0.05*np.cos(4*t))+0.4,
    np.sin(p)*0.45
))


# MODE 5: FLOWER
t = np.random.uniform(0, 2*np.pi, NUM_PARTICLES)
r = 0.35 + 1.65*np.abs(np.cos(5*t))**0.8

pos_flower = np.column_stack((
    r*np.cos(t),
    r*np.sin(t),
    np.random.uniform(-0.25, 0.25, NUM_PARTICLES)
))


# MODE 6: STAR
angle = np.random.uniform(0, 2*np.pi, NUM_PARTICLES)

sector = angle % (np.pi/4)
boundary = 1.0 / np.maximum(
    np.cos(sector-np.pi/8), 0.3
)

radius = np.random.uniform(0, 1, NUM_PARTICLES)**0.5
radius *= boundary

pos_star = np.column_stack((
    radius*np.cos(angle),
    radius*np.sin(angle),
    np.random.uniform(-0.2, 0.2, NUM_PARTICLES)
))


# MODE 7: SPIRAL GALAXY
arm = np.random.randint(0, 4, NUM_PARTICLES)
radius = np.random.uniform(0.2, 3.5, NUM_PARTICLES)

angle = (
    arm*(2*np.pi/4)
    + radius*1.8
    + np.random.normal(0, 0.18, NUM_PARTICLES)
)

pos_galaxy = np.column_stack((
    radius*np.cos(angle),
    radius*np.sin(angle)*0.65,
    np.random.normal(0, 0.12, NUM_PARTICLES)
))


# MODE 8: PARTICLE EXPLOSION
pos_explosion = random_sphere(NUM_PARTICLES, 3.5)


# =========================================================
# COLORS AND MODE NAMES
# =========================================================

MODE_COLORS = {
    1: (0.1, 0.55, 1.0),
    2: (1.0, 0.65, 0.15),
    3: (0.0, 0.85, 1.0),
    4: (1.0, 0.12, 0.4),
    5: (0.75, 0.25, 1.0),
    6: (1.0, 0.9, 0.2),
    7: (0.4, 0.55, 1.0),
    8: (1.0, 0.35, 0.1)
}

MODE_NAMES = {
    1: "COSMIC UNIVERSE",
    2: "SATURN PLANET",
    3: "I LOVE YOU",
    4: "COSMIC HEART",
    5: "PARTICLE FLOWER",
    6: "SUPER STAR",
    7: "SPIRAL GALAXY",
    8: "PARTICLE EXPLOSION"
}

MODE_SHAPES = {
    1: pos_space,
    2: pos_planet,
    3: pos_text,
    4: pos_heart,
    5: pos_flower,
    6: pos_star,
    7: pos_galaxy,
    8: pos_explosion
}

current_pos = pos_space.copy()


# =========================================================
# GESTURE RECOGNITION
# =========================================================

def get_fingers(hand):
    lm = hand.landmark

    tips = [8, 12, 16, 20]
    pips = [6, 10, 14, 18]

    fingers = [
        lm[tip].y < lm[pip].y
        for tip, pip in zip(tips, pips)
    ]

    thumb_extended = (
        abs(lm[4].x-lm[2].x)
        > abs(lm[3].x-lm[2].x)*1.15
    )

    return thumb_extended, fingers



def detect_gesture(hand):
    lm = hand.landmark

    thumb, fingers = get_fingers(hand)

    index, middle, ring, pinky = fingers

    pinch_distance = math.sqrt(
        (lm[4].x-lm[8].x)**2 +
        (lm[4].y-lm[8].y)**2
    )

    # PINCH: ZOOM CONTROL
    if pinch_distance < 0.045:
        return None, pinch_distance, True

    # THUMBS UP
    if thumb and lm[4].y < lm[3].y and not any(fingers):
        return 6, pinch_distance, False

    # THUMBS DOWN
    if thumb and lm[4].y > lm[3].y and not any(fingers):
        return 8, pinch_distance, False

    # OPEN PALM
    if thumb and all(fingers):
        return 1, pinch_distance, False

    # CLOSED FIST - HEART
    # Fist detection no longer depends on thumb detection.
    if not any(fingers):
        return 4, pinch_distance, False

    # INDEX FINGER
    if index and not middle and not ring and not pinky:
        return 2, pinch_distance, False

    # PEACE SIGN
    if index and middle and not ring and not pinky:
        return 3, pinch_distance, False

    # THREE FINGERS
    if index and middle and ring and not pinky:
        return 5, pinch_distance, False

    # ROCK SIGN
    if index and pinky and not middle and not ring:
        return 7, pinch_distance, False

    return None, pinch_distance, False

# =========================================================
# CAMERA THREAD
# =========================================================

def camera_thread_func():

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("ERROR: Camera could not be opened.")

        with lock:
            shared_data["running"] = False

        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    hands = mp_hands.Hands(
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.65,
        min_tracking_confidence=0.65
    )

    detected_mode = 1
    candidate_mode = None
    candidate_count = 0

    zoom_value = 12.0

    while True:

        with lock:
            if not shared_data["running"]:
                break

        ret, frame = cap.read()

        if not ret:
            time.sleep(0.02)
            continue

        frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        results = hands.process(rgb)

        local_x = 0.0
        local_y = 0.0
        local_pinch = False

        if results.multi_hand_landmarks:

            hand = results.multi_hand_landmarks[0]

            mp_draw.draw_landmarks(
                frame,
                hand,
                mp_hands.HAND_CONNECTIONS
            )

            new_mode, distance, pinching = detect_gesture(hand)

            wrist = hand.landmark[0]

            local_x = (wrist.x-0.5)*8.0
            local_y = -(wrist.y-0.5)*6.0

            local_pinch = pinching

            # GESTURE STABILIZATION
            if new_mode is not None:

                if new_mode == candidate_mode:
                    candidate_count += 1
                else:
                    candidate_mode = new_mode
                    candidate_count = 1

                if candidate_count >= 4:
                    detected_mode = new_mode

            else:
                candidate_mode = None
                candidate_count = 0

            # PINCH ZOOM
            if pinching:

                zoom_value = float(np.interp(
                    distance,
                    [0.015, 0.045],
                    [7.0, 17.0]
                ))

        else:

            candidate_mode = None
            candidate_count = 0

        # CAMERA HUD
        cv2.rectangle(
            frame,
            (0, 0),
            (640, 65),
            (15, 10, 35),
            -1
        )

        cv2.putText(
            frame,
            "AI GESTURE SPACE UNIVERSE",
            (12, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 220, 255),
            2
        )

        cv2.putText(
            frame,
            "MODE: " + MODE_NAMES[detected_mode],
            (12, 52),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (100, 255, 150),
            1
        )

        with lock:

            shared_data["mode"] = detected_mode
            shared_data["target_x"] = local_x
            shared_data["target_y"] = local_y
            shared_data["pinching"] = local_pinch
            shared_data["zoom"] = zoom_value
            shared_data["frame"] = frame

    hands.close()
    cap.release()


# =========================================================
# START CAMERA
# =========================================================

camera_thread = threading.Thread(
    target=camera_thread_func,
    daemon=True
)

camera_thread.start()

time.sleep(1.5)


# =========================================================
# PYGAME AND OPENGL INITIALIZATION
# =========================================================

pygame.init()

pygame.display.set_mode(
    (WIDTH, HEIGHT),
    DOUBLEBUF | OPENGL
)

pygame.display.set_caption(
    "AI Gesture Space Universe"
)

glViewport(0, 0, WIDTH, HEIGHT)

glMatrixMode(GL_PROJECTION)
glLoadIdentity()

gluPerspective(
    45,
    WIDTH/HEIGHT,
    0.1,
    100.0
)

glMatrixMode(GL_MODELVIEW)

glEnable(GL_DEPTH_TEST)
glEnable(GL_BLEND)

glBlendFunc(
    GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA
)

glEnable(GL_POINT_SMOOTH)

glHint(
    GL_POINT_SMOOTH_HINT,
    GL_NICEST
)

clock = pygame.time.Clock()

font = pygame.font.SysFont(
    "Arial", 20, bold=True
)

small_font = pygame.font.SysFont(
    "Arial", 15
)

# SMALL CAMERA WINDOW
# Create and resize from the main GUI thread.

cv2.namedWindow(
    "Hand Gesture Monitor",
    cv2.WINDOW_NORMAL
)

cv2.resizeWindow(
    "Hand Gesture Monitor",
    CAMERA_WIDTH,
    CAMERA_HEIGHT
)

rotation_angle = 0.0

hand_x = 0.0
hand_y = 0.0
zoom = 12.0

hand_rotation_x = 0.0
hand_rotation_y = 0.0

background_stars = random_sphere(500, 20.0)


# =========================================================
# UI FUNCTIONS
# =========================================================

def draw_text(x, y, message, font_obj, color):

    surface = font_obj.render(
        message,
        True,
        color
    )

    data = pygame.image.tostring(
        surface,
        "RGBA",
        True
    )

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()

    glOrtho(
        0, WIDTH,
        HEIGHT, 0,
        -1, 1
    )

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glDisable(GL_DEPTH_TEST)

    glRasterPos2f(x, y)

    glDrawPixels(
        surface.get_width(),
        surface.get_height(),
        GL_RGBA,
        GL_UNSIGNED_BYTE,
        data
    )

    glEnable(GL_DEPTH_TEST)

    glPopMatrix()

    glMatrixMode(GL_PROJECTION)
    glPopMatrix()

    glMatrixMode(GL_MODELVIEW)


def draw_background():

    glPointSize(1.5)

    glBegin(GL_POINTS)

    for point in background_stars:

        glColor4f(
            0.45, 0.55, 0.85, 0.7
        )

        glVertex3f(
            point[0],
            point[1],
            point[2]-12
        )

    glEnd()


def draw_particles(mode, positions, animation_time):

    base_color = MODE_COLORS[mode]

    pulse = 1.0 + 0.04*math.sin(
        animation_time*3
    )

    if mode == 8:
        pulse = 1.0 + 0.35*math.sin(
            animation_time*5
        )

    glPointSize(3.5)

    glBegin(GL_POINTS)

    for i in range(NUM_PARTICLES):

        x, y, z = positions[i]

        x *= pulse
        y *= pulse
        z *= pulse

        variation = 0.75 + 0.25*math.sin(
            animation_time*2+i*0.04
        )

        alpha = 0.85

        if mode == 8:
            alpha = 0.6 + 0.4*abs(
                math.sin(animation_time*4+i*0.02)
            )

        glColor4f(
            min(base_color[0]*variation, 1.0),
            min(base_color[1]*variation, 1.0),
            min(base_color[2]*variation, 1.0),
            alpha
        )

        glVertex3f(x, y, z)

    glEnd()


# =========================================================
# MAIN APPLICATION LOOP
# =========================================================

running = True

animation_time = 0.0

current_pos = pos_space.copy()

try:

    while running:

        dt = clock.tick(60)/1000.0

        animation_time += dt

        # EVENTS
        for event in pygame.event.get():

            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:
                    running = False

                elif pygame.K_1 <= event.key <= pygame.K_8:

                    selected_mode = event.key - pygame.K_0

                    with lock:
                        shared_data["mode"] = selected_mode

                elif event.key in (
                    pygame.K_PLUS,
                    pygame.K_EQUALS
                ):

                    zoom = max(5.0, zoom-0.5)

                elif event.key == pygame.K_MINUS:

                    zoom = min(20.0, zoom+0.5)

                elif event.key == pygame.K_r:

                    zoom = 12.0
                    hand_x = 0.0
                    hand_y = 0.0
                    rotation_angle = 0.0

        # CAMERA DATA
        with lock:

            current_mode = shared_data["mode"]

            target_hand_x = shared_data["target_x"]
            target_hand_y = shared_data["target_y"]

            target_zoom = shared_data["zoom"]

            pinching = shared_data["pinching"]

            frame = shared_data["frame"]

            camera_running = shared_data["running"]

        if not camera_running:
            running = False

        # DISPLAY SMALL CAMERA WINDOW
        if frame is not None:

            cv2.imshow(
                "Hand Gesture Monitor",
                frame
            )

            if cv2.waitKey(1) & 0xFF == ord('q'):
                running = False

        # SMOOTH CONTROLS
        hand_x += (target_hand_x-hand_x)*0.12
        hand_y += (target_hand_y-hand_y)*0.12

        if pinching:
            zoom += (target_zoom-zoom)*0.15

        # PARTICLE TRANSITION
        target_pos = MODE_SHAPES[current_mode]

        current_pos += (
            target_pos-current_pos
        )*min(1.0, dt*5.0)

        # ROTATION
        rotation_angle += 25.0*dt

        hand_rotation_y = hand_x*10.0
        hand_rotation_x = hand_y*8.0

        # RENDER
        glClearColor(
            0.005,
            0.005,
            0.025,
            1.0
        )

        glClear(
            GL_COLOR_BUFFER_BIT |
            GL_DEPTH_BUFFER_BIT
        )

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        draw_background()

        # MAIN 3D UNIVERSE
        glPushMatrix()

        glTranslatef(
            hand_x*0.25,
            hand_y*0.25,
            -zoom
        )

        glRotatef(
            hand_rotation_x,
            1, 0, 0
        )

        glRotatef(
            rotation_angle+hand_rotation_y,
            0, 1, 0
        )

        if current_mode == 2:
            glRotatef(25, 1, 0, 0)

        draw_particles(
            current_mode,
            current_pos,
            animation_time
        )

        glPopMatrix()

        # PROFESSIONAL HUD
        draw_text(
            25, 35,
            "AI GESTURE SPACE UNIVERSE",
            font,
            (100, 210, 255)
        )

        draw_text(
            25, 70,
            "CURRENT MODE: "+MODE_NAMES[current_mode],
            small_font,
            (255, 255, 255)
        )

        draw_text(
            25, 100,
            "PARTICLES: "+str(NUM_PARTICLES),
            small_font,
            (150, 180, 255)
        )

        draw_text(
            25, 130,
            "ZOOM: "+str(round(zoom, 1)),
            small_font,
            (150, 220, 255)
        )

        draw_text(
            25, HEIGHT-35,
            "ESC: EXIT | R: RESET | +/-: ZOOM | 1-8: MODES",
            small_font,
            (170, 190, 220)
        )

        draw_text(
            WIDTH-290, 35,
            "PINCH: "+("ACTIVE" if pinching else "READY"),
            small_font,
            (100, 255, 180)
        )

        pygame.display.flip()


finally:

    with lock:
        shared_data["running"] = False

    camera_thread.join(timeout=2.0)

    cv2.destroyAllWindows()
    pygame.quit()

    print(
        "AI Gesture Space Universe closed successfully."
    )