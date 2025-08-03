# breakout.py
# Single-file Breakout in Python + Pygame, 60 FPS, mouse control,
# synthesized beep/boop sounds (no external files), no leaderboard.

import math
import sys
import time
import pygame
import numpy as np

# Window / game constants
WIN_W, WIN_H = 800, 600
FPS = 60
DT = 1.0 / 60.0

PADDLE_W, PADDLE_H = 100, 14
PADDLE_Y = 560

BALL_SIZE = 10
BALL_SPEED = 320.0

BRICK_COLS = 10
BRICK_ROWS = 6
BRICK_W = 70
BRICK_H = 22
BRICK_TOP = 80
BRICK_LEFT = 65
BRICK_GAP = 6

START_LIVES = 3

# Colors
BG = (10, 10, 15)
FG = (200, 220, 240)
PADDLE_COL = (200, 200, 200)
BALL_COL = (250, 250, 250)
BLACK = (0, 0, 0)

# Sound: synth simple tones so we don't need files
def make_tone(freq=440.0, ms=50, vol=0.4, sample_rate=44100):
    t = np.linspace(0, ms / 1000.0, int(sample_rate * ms / 1000.0), False)
    # Slightly percussive: sine * decay
    wave = np.sin(2 * np.pi * freq * t) * np.exp(-6 * t)
    wave *= vol
    # Convert to 16-bit signed
    audio = np.int16(wave * 32767)
    stereo = np.column_stack((audio, audio))  # 2 channels
    return pygame.sndarray.make_sound(stereo.copy())


class Sounds:
    def __init__(self):
        # Pre-generate a few effects
        self.wall = make_tone(700, 30, 0.35)
        self.paddle = make_tone(900, 40, 0.4)
        self.brick = make_tone(1200, 50, 0.45)
        self.lose = make_tone(200, 180, 0.5)
        self.win = make_tone(1500, 220, 0.5)
        # Start jingle: quick sequence
        self.start1 = make_tone(600, 60, 0.4)
        self.start2 = make_tone(800, 60, 0.4)

    def play_start(self):
        self.start1.play()
        # Slight stagger without blocking the loop too long
        pygame.time.set_timer(pygame.USEREVENT + 10, 80, True)

    def handle_event(self, e):
        if e.type == pygame.USEREVENT + 10:
            self.start2.play()


def brick_rect(r, c):
    x = BRICK_LEFT + c * (BRICK_W + BRICK_GAP)
    y = BRICK_TOP + r * (BRICK_H + BRICK_GAP)
    return pygame.Rect(x, y, BRICK_W, BRICK_H)


def reset_bricks():
    return [[1 for _ in range(BRICK_COLS)] for _ in range(BRICK_ROWS)]


def reset_ball_paddle(rng):
    paddle = pygame.Rect((WIN_W - PADDLE_W) // 2, PADDLE_Y, PADDLE_W, PADDLE_H)
    ball = pygame.Rect(WIN_W // 2 - BALL_SIZE // 2, WIN_H // 2 + 60,
                       BALL_SIZE, BALL_SIZE)
    ang = (math.pi / 4.0) + rng.random() * (math.pi / 2.0)
    dir_sign = -1.0 if rng.random() < 0.5 else 1.0
    vx = math.cos(ang) * BALL_SPEED * dir_sign
    vy = -abs(math.sin(ang) * BALL_SPEED)
    return paddle, ball, [vx, vy]


def all_bricks_cleared(bricks):
    for row in bricks:
        for b in row:
            if b:
                return False
    return True


def intersects_ball_rect(ball, rect):
    return ball.colliderect(rect)


def reflect_from_brick(ball, rb, vel):
    # Compute penetration on four sides, flip the dominant axis
    left_pen = rb.right - ball.left
    right_pen = ball.right - rb.left
    top_pen = rb.bottom - ball.top
    bot_pen = ball.bottom - rb.top

    # Pick the smallest penetration; tie-breaks are fine
    min_pen = left_pen
    nx, ny = 1, 0

    if right_pen < min_pen:
        min_pen = right_pen
        nx, ny = -1, 0
    if top_pen < min_pen:
        min_pen = top_pen
        nx, ny = 0, 1
    if bot_pen < min_pen:
        min_pen = bot_pen
        nx, ny = 0, -1

    if nx != 0:
        vel[0] = -vel[0]
        if nx > 0:
            ball.left = rb.right + 1
        else:
            ball.right = rb.left - 1
    if ny != 0:
        vel[1] = -vel[1]
        if ny > 0:
            ball.top = rb.bottom + 1
        else:
            ball.bottom = rb.top - 1


def main():
    pygame.init()

    # Init audio first; fallback silently if mixer fails (older systems)
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
    except Exception:
        pass
    try:
        pygame.mixer.init()
    except Exception:
        pass

    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("Breakout - One Shot Arcade (Python)")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 22)

    rng = np.random.default_rng()

    sounds = Sounds()

    bricks = reset_bricks()
    paddle, ball, vel = reset_ball_paddle(rng)
    lives = START_LIVES
    score = 0
    paused = False
    game_over = False
    is_win = False

    sounds.play_start()

    acc = 0.0
    last_time = time.perf_counter()

    running = True
    while running:
        # Timing
        now = time.perf_counter()
        frame = now - last_time
        last_time = now
        acc += frame

        # Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_p:
                    paused = not paused
                elif event.key == pygame.K_r:
                    bricks = reset_bricks()
                    paddle, ball, vel = reset_ball_paddle(rng)
                    lives = START_LIVES
                    score = 0
                    paused = False
                    game_over = False
                    is_win = False
                    sounds.play_start()
            else:
                # Allow sound jingle callback
                sounds.handle_event(event)

        # Mouse controls
        if not game_over:
            mx, _ = pygame.mouse.get_pos()
            paddle.centerx = mx
            if paddle.left < 0:
                paddle.left = 0
            if paddle.right > WIN_W:
                paddle.right = WIN_W

        # Fixed-step update
        while acc >= DT:
            if not paused and not game_over:
                # Move ball
                ball.x += int(vel[0] * DT)
                ball.y += int(vel[1] * DT)

                # Walls
                if ball.left <= 0:
                    ball.left = 0
                    vel[0] = abs(vel[0])
                    if pygame.mixer.get_init():
                        sounds.wall.play()
                elif ball.right >= WIN_W:
                    ball.right = WIN_W
                    vel[0] = -abs(vel[0])
                    if pygame.mixer.get_init():
                        sounds.wall.play()
                if ball.top <= 0:
                    ball.top = 0
                    vel[1] = abs(vel[1])
                    if pygame.mixer.get_init():
                        sounds.wall.play()

                # Bottom: lose life
                if ball.top > WIN_H:
                    lives -= 1
                    if pygame.mixer.get_init():
                        sounds.lose.play()
                    if lives <= 0:
                        game_over = True
                        is_win = False
                    else:
                        paddle, ball, vel = reset_ball_paddle(rng)

                # Paddle collision
                if ball.colliderect(paddle) and vel[1] > 0:
                    # Angle based on where it hits the paddle
                    hit = (ball.centerx - paddle.left) / float(paddle.width)
                    ang = (hit - 0.5) * (math.pi / 1.2)
                    speed = math.hypot(vel[0], vel[1])
                    vel[0] = speed * math.sin(ang)
                    vel[1] = -abs(speed * math.cos(ang))
                    ball.bottom = paddle.top - 1
                    if pygame.mixer.get_init():
                        sounds.paddle.play()

                # Bricks
                hit_brick = False
                for r in range(BRICK_ROWS):
                    if hit_brick:
                        break
                    for c in range(BRICK_COLS):
                        if bricks[r][c] == 0:
                            continue
                        rb = brick_rect(r, c)
                        if ball.colliderect(rb):
                            reflect_from_brick(ball, rb, vel)
                            bricks[r][c] = 0
                            score += 10
                            hit_brick = True
                            if pygame.mixer.get_init():
                                sounds.brick.play()
                            if all_bricks_cleared(bricks):
                                game_over = True
                                is_win = True
                                if pygame.mixer.get_init():
                                    sounds.win.play()
                            break
            acc -= DT

        # Draw
        screen.fill(BG)

        # Info line
        info = f"Breakout 60FPS | Score: {score}  Lives: {lives}"
        text = font.render(info, True, FG)
        screen.blit(text, (10, 10))
        hint = "Mouse to move | P=Pause | R=Reset"
        hint_text = font.render(hint, True, FG)
        screen.blit(hint_text, (WIN_W - 265, 10))

        # Bricks
        for r in range(BRICK_ROWS):
            for c in range(BRICK_COLS):
                if bricks[r][c]:
                    rb = brick_rect(r, c)
                    hue = 40 + r * 35
                    col = (hue, min(255, 120 + r * 15),
                           max(0, 180 - r * 20))
                    pygame.draw.rect(screen, col, rb)
                    pygame.draw.rect(screen, BLACK, rb, 1)

        # Paddle
        pygame.draw.rect(screen, PADDLE_COL, paddle)

        # Ball
        pygame.draw.ellipse(screen, BALL_COL, ball)

        # Overlays
        if paused:
            msg = "PAUSED - Press P to resume"
            t = font.render(msg, True, FG)
            screen.blit(t, (WIN_W // 2 - t.get_width() // 2,
                            WIN_H // 2 - 10))

        if game_over:
            msg = "YOU WIN! Press R to play again" if is_win else \
                  "GAME OVER - Press R to retry"
            t = font.render(msg, True, FG)
            screen.blit(t, (WIN_W // 2 - t.get_width() // 2,
                            WIN_H // 2 - 10))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main()) 
