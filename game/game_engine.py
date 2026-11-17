import math

import pygame

from .marble import Marble
from .wall import Wall

# Game Engine

WHITE = (255, 255, 255)
DARK = (40, 40, 50)
WALL_COLOR = (90, 90, 110)
GOAL_COLOR = (60, 200, 120)

RESTITUTION = 0.30          # how bouncy the walls are (same feel as before)


class GameEngine:
    def __init__(self, width, height):
        self.width = width
        self.height = height

        self.marble = Marble(50, 50)
        self.tilt_strength = 0.6
        self.friction = 0.02
        self.max_speed = 9

        self.walls = self._build_maze()
        self.goal_x, self.goal_y, self.goal_radius = width - 60, height - 60, 22

        self.time_limit_ms = 45000
        self.start_ticks = pygame.time.get_ticks()

        self.font = pygame.font.SysFont("Arial", 26)
        self.small_font = pygame.font.SysFont("Arial", 18)
        self.big_font = pygame.font.SysFont("Arial", 40, bold=True)
        self.game_over = False
        self.result = None  # "solved" or "timeout"
        self.finish_time_ms = None
        self.should_quit = False

    def _build_maze(self):
        walls = []
        t = 16  # wall thickness

        # outer boundary
        walls.append(Wall(0, 0, self.width, t))
        walls.append(Wall(0, self.height - t, self.width, t))
        walls.append(Wall(0, 0, t, self.height))
        walls.append(Wall(self.width - t, 0, t, self.height))

        # a few internal walls forming a simple winding path
        walls.append(Wall(0, 140, self.width - 140, t))
        walls.append(Wall(140, 260, self.width - 140, t))
        walls.append(Wall(0, 380, self.width - 140, t))

        return walls

    def handle_event(self, event):
        """The round now waits for the player instead of exiting on its own."""
        if event.type == pygame.QUIT:
            self.should_quit = True
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.should_quit = True

    def handle_input(self):
        if self.game_over:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        dx = mouse_x - self.width // 2
        dy = mouse_y - self.height // 2
        dist = max(1, (dx ** 2 + dy ** 2) ** 0.5)
        ax = (dx / dist) * self.tilt_strength
        ay = (dy / dist) * self.tilt_strength
        self.marble.vx += ax
        self.marble.vy += ay

    def update(self):
        if self.game_over:
            return

        elapsed = pygame.time.get_ticks() - self.start_ticks
        if elapsed >= self.time_limit_ms:
            self.game_over = True
            self.result = "timeout"
            return

        self.marble.vx *= (1 - self.friction)
        self.marble.vy *= (1 - self.friction)

        speed = math.hypot(self.marble.vx, self.marble.vy)
        if speed > self.max_speed:
            scale = self.max_speed / speed
            self.marble.vx *= scale
            self.marble.vy *= scale
            speed = self.max_speed

        # Sub-step the movement so a fast marble can never tunnel through a
        # 16 px wall (previously a 9 px/frame marble could skip one).
        steps = max(1, int(math.ceil(speed / (self.marble.radius * 0.5))))
        for _ in range(steps):
            self.marble.x += self.marble.vx / steps
            self.marble.y += self.marble.vy / steps
            self._resolve_wall_collisions()

        gx = self.goal_x - self.marble.x
        gy = self.goal_y - self.marble.y
        if (gx ** 2 + gy ** 2) ** 0.5 <= self.goal_radius:
            self.game_over = True
            self.result = "solved"
            self.finish_time_ms = elapsed

    def _hit(self, wall):
        """Circle vs rectangle: returns (nx, ny, penetration) or None.

        This is the fix for Task 1. The old test compared the marble's square
        bounding box (colliderect) with the wall, so near a corner the box could
        overlap the wall before the round marble touched it and the marble
        bounced off empty space. Here we use the closest point on the rectangle
        to the marble centre, which is exact for a circle.
        """
        r = wall.rect()
        m = self.marble
        closest_x = min(max(m.x, r.left), r.right)
        closest_y = min(max(m.y, r.top), r.bottom)
        dx, dy = m.x - closest_x, m.y - closest_y
        d2 = dx * dx + dy * dy
        radius = m.radius
        if d2 > radius * radius:
            return None                      # the round marble does not touch the wall

        if d2 > 1e-9:                        # touching an edge or a corner
            d = math.sqrt(d2)
            return dx / d, dy / d, radius - d

        # Centre is inside the rectangle: push out along the shallowest axis.
        left, right = m.x - r.left, r.right - m.x
        top, bottom = m.y - r.top, r.bottom - m.y
        smallest = min(left, right, top, bottom)
        if smallest == left:
            return -1.0, 0.0, left + radius
        if smallest == right:
            return 1.0, 0.0, right + radius
        if smallest == top:
            return 0.0, -1.0, top + radius
        return 0.0, 1.0, bottom + radius

    def _resolve_wall_collisions(self):
        for _ in range(3):                   # repeat to settle corner contacts
            moved = False
            for wall in self.walls:
                hit = self._hit(wall)
                if hit is None:
                    continue
                nx, ny, penetration = hit
                self.marble.x += nx * penetration
                self.marble.y += ny * penetration

                vn = self.marble.vx * nx + self.marble.vy * ny
                if vn < 0:                   # only reflect if closing on the wall
                    self.marble.vx -= (1 + RESTITUTION) * vn * nx
                    self.marble.vy -= (1 + RESTITUTION) * vn * ny
                moved = True
            if not moved:
                break

    def render(self, screen):
        screen.fill(DARK)

        for wall in self.walls:
            pygame.draw.rect(screen, WALL_COLOR, wall.rect())

        pygame.draw.circle(screen, GOAL_COLOR, (self.goal_x, self.goal_y), self.goal_radius)
        pygame.draw.circle(screen, WHITE, (int(self.marble.x), int(self.marble.y)), self.marble.radius)

        self._render_hud(screen)

        if self.game_over:
            self._render_end(screen)

    def _render_hud(self, screen):
        elapsed = pygame.time.get_ticks() - self.start_ticks
        remaining = self.time_limit_ms - elapsed
        if self.game_over and self.result == "solved" and self.finish_time_ms is not None:
            label = "Solved in %.1fs" % (self.finish_time_ms / 1000.0)
            color = (90, 220, 140)
        else:
            label = "Time: %ds" % max(0, remaining // 1000)
            color = WHITE if remaining > 5000 else (240, 110, 110)
        screen.blit(self.font.render(label, True, color), (10, 10))

    def _panel(self, screen, alpha=225):
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((12, 14, 20, alpha))
        screen.blit(overlay, (0, 0))

    def _render_end(self, screen):
        self._panel(screen)
        w = self.width
        if self.result == "solved":
            title = self.big_font.render("MAZE SOLVED", True, (90, 220, 140))
            detail = "Finish time: %.2f s" % (self.finish_time_ms / 1000.0)
        else:
            title = self.big_font.render("TIME'S UP", True, (240, 110, 110))
            detail = "The marble did not reach the goal."
        screen.blit(title, (w // 2 - title.get_width() // 2, 150))
        d = self.font.render(detail, True, WHITE)
        screen.blit(d, (w // 2 - d.get_width() // 2, 205))
        hint = self.small_font.render("Esc   quit", True, (200, 206, 220))
        screen.blit(hint, (w // 2 - hint.get_width() // 2, 300))
        prompt = self.small_font.render("Waiting for your choice...", True, (150, 156, 170))
        screen.blit(prompt, (w // 2 - prompt.get_width() // 2, self.height - 40))
