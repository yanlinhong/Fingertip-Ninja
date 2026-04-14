import cv2
import mediapipe as mp
import pygame
import random
import math
import os
import sys
import numpy as np

# --- 1. 基础配置与路径 (完美适配 EXE 打包) ---
if getattr(sys, 'frozen', False):
    # 如果是双击 exe 运行，获取 exe 所在的目录
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # 如果是直接运行 py 代码，获取代码所在的目录
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
os.chdir(BASE_DIR)
FRUITS_FOLDER = os.path.join(BASE_DIR, "Fruits")

WIDTH, HEIGHT = 1280, 720
PROCESS_WIDTH, PROCESS_HEIGHT = 640, 480 
FRUIT_SIZE = 110
GRAVITY = 0.7
FPS = 60

STATE_START = 0
STATE_PLAYING = 1
STATE_GAMEOVER = 2

FRUIT_LIST = ["apple", "banana", "orange", "peach", "mango", "strawberry", "watermelon"]

# 科技感霓虹色彩配置
COLOR_CYAN = (0, 255, 255)
COLOR_MAGENTA = (255, 0, 255)
COLOR_DARK_BG = (15, 20, 30, 200) 
COLOR_AMBER = (255, 176, 0)

pygame.mixer.pre_init(44100, -16, 2, 512)
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("指尖忍者 - 专属评价版")
clock = pygame.time.Clock()

# --- 2. 资源与 HUD UI 加载 ---
class Assets:
    def __init__(self):
        self.fruits = {}
        self.bomb = None
        self.slice_sound = None
        
        font_paths = [
            r"C:\Windows\Fonts\msyhbd.ttc",  
            r"C:\Windows\Fonts\msyh.ttc",    
            r"C:\Windows\Fonts\simhei.ttf"   
        ]
        
        selected_font = None
        for path in font_paths:
            if os.path.exists(path):
                selected_font = path; break
                
        try:
            self.font_title = pygame.font.Font(selected_font, 110)
            self.font_lg = pygame.font.Font(selected_font, 80)
            self.font_md = pygame.font.Font(selected_font, 50)
            self.font_sm = pygame.font.Font(selected_font, 35)
        except:
            self.font_title = self.font_lg = self.font_md = self.font_sm = pygame.font.Font(None, 60)

        self.load()

    def load(self):
        if os.path.exists("slice.wav"):
            self.slice_sound = pygame.mixer.Sound("slice.wav")
            self.slice_sound.set_volume(0.5)
        
        if os.path.exists(FRUITS_FOLDER):
            for name in FRUIT_LIST:
                for ext in [".png", ".png.png", ".jpg"]:
                    path = os.path.join(FRUITS_FOLDER, f"{name}{ext}")
                    if os.path.exists(path):
                        img = pygame.image.load(path).convert_alpha()
                        self.fruits[name] = pygame.transform.scale(img, (FRUIT_SIZE, FRUIT_SIZE))
                        break
            
            for ext in [".png", ".png.png"]:
                path = os.path.join(FRUITS_FOLDER, f"bomb{ext}")
                if os.path.exists(path):
                    self.bomb = pygame.transform.scale(pygame.image.load(path).convert_alpha(), (FRUIT_SIZE, FRUIT_SIZE))
                    break

game_assets = Assets()

# --- 3. 高级绘制辅助 (霓虹发光文字与 HUD 面板) ---
def draw_neon_text(surface, text, font, color, x, y, glow=True):
    if glow:
        glow_color = (max(0, color[0]-100), max(0, color[1]-100), max(0, color[2]-100))
        for dx, dy in [(-2,-2), (2,-2), (-2,2), (2,2)]:
            g_txt = font.render(text, True, glow_color)
            surface.blit(g_txt, (x+dx, y+dy))
    txt = font.render(text, True, color)
    surface.blit(txt, (x, y))

def draw_hud_button(text, center_y, color, tips):
    rect = pygame.Rect(WIDTH//2 - 180, center_y - 45, 360, 90)
    s = pygame.Surface((360, 90), pygame.SRCALPHA)
    s.fill((10, 15, 25, 200))
    screen.blit(s, rect.topleft)
    pygame.draw.rect(screen, color, rect, 2)
    pygame.draw.line(screen, color, (rect.left, rect.top), (rect.left+20, rect.top), 5)
    pygame.draw.line(screen, color, (rect.left, rect.top), (rect.left, rect.top+20), 5)
    pygame.draw.line(screen, color, (rect.right, rect.bottom), (rect.right-20, rect.bottom), 5)
    pygame.draw.line(screen, color, (rect.right, rect.bottom), (rect.right, rect.bottom-20), 5)
    
    txt = game_assets.font_md.render(text, True, (255, 255, 255))
    screen.blit(txt, (WIDTH//2 - txt.get_width()//2, center_y - txt.get_height()//2))
    
    is_hover = False
    for tip in tips:
        if rect.collidepoint(tip): is_hover = True
    if is_hover:
        pygame.draw.rect(screen, color, rect, 5) 
    return rect

def draw_hud_panel(score, missed, total):
    # 增加面板高度以容纳命中率
    s = pygame.Surface((300, 160), pygame.SRCALPHA)
    s.fill(COLOR_DARK_BG)
    screen.blit(s, (20, 20))
    pygame.draw.rect(screen, COLOR_CYAN, (20, 20, 300, 160), 2)
    pygame.draw.line(screen, COLOR_CYAN, (20, 20), (50, 20), 5)
    
    # 计算命中率
    hit_rate = (score / total * 100) if total > 0 else 0.0
    
    draw_neon_text(screen, f" 得分 : {score}", game_assets.font_sm, COLOR_CYAN, 40, 35, False)
    draw_neon_text(screen, f" 丢分 : {missed}", game_assets.font_sm, COLOR_MAGENTA, 40, 80, False)
    draw_neon_text(screen, f"命中率 : {hit_rate:.1f}%", game_assets.font_sm, COLOR_AMBER, 40, 125, False)

# --- 4. 游戏物体 ---
class Fruit:
    def __init__(self): 
        self.reset()
        
    def reset(self, manual=False):
        global missed_score, total_targets
        
        if not manual and hasattr(self, 'y') and self.y > HEIGHT and not self.is_cut and not self.is_bomb:
            missed_score += 1
            
        self.x = random.randint(200, WIDTH - 200)
        self.y = HEIGHT + 100
        self.vx = random.randint(-4, 4)
        self.vy = -random.randint(20, 27)
        self.angle = 0
        self.spin = random.randint(-8, 8)
        self.is_cut = False
        self.is_bomb = (random.random() < 0.20) and (game_assets.bomb is not None)
        
        if not self.is_bomb: 
            self.type = random.choice(list(game_assets.fruits.keys())) if game_assets.fruits else "sphere"
            # 只要重置出一个真的水果，总目标数就加 1
            total_targets += 1

    def update(self):
        self.x += self.vx; self.y += self.vy; self.vy += GRAVITY; self.angle += self.spin
        if self.y > HEIGHT + 150: self.reset()

    def draw(self, surface):
        if self.is_cut: return
        img = game_assets.bomb if self.is_bomb else game_assets.fruits.get(self.type)
        if img:
            rotated = pygame.transform.rotate(img, self.angle)
            surface.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))).topleft)

class HalfFruit:
    def __init__(self, img, x, y, vx, vy, angle, spin):
        self.img, self.x, self.y, self.vx, self.vy, self.angle, self.spin = img, x, y, vx, vy, angle, spin
    def update(self):
        self.x += self.vx; self.y += self.vy; self.vy += GRAVITY; self.angle += self.spin
    def draw(self, surface):
        rotated = pygame.transform.rotate(self.img, self.angle)
        surface.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))).topleft)

# --- 5. AI 初始化 ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(model_complexity=0, min_detection_confidence=0.7, max_num_hands=2) 
cap = cv2.VideoCapture(0)
cap.set(3, WIDTH); cap.set(4, HEIGHT)

# --- 6. 全局状态 ---
current_state = STATE_START
score = missed_score = total_targets = 0
fruits = [Fruit() for _ in range(5)]
half_fruits = []
trails = [[], []] 

print(">>> 赛博系统启动...")
running = True
try:
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False

        success, frame = cap.read()
        if not success: continue
        
        frame = cv2.flip(cv2.resize(frame, (WIDTH, HEIGHT)), 1)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame) 
        
        # 赛博红焰发光骨骼
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    landmark_drawing_spec=mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=1, circle_radius=1),
                    connection_drawing_spec=mp_drawing.DrawingSpec(color=(0, 0, 200), thickness=2) 
                )
                for landmark in hand_landmarks.landmark:
                    cx = int(landmark.x * frame.shape[1])
                    cy = int(landmark.y * frame.shape[0])
                    cv2.circle(frame, (cx, cy), 9, (100, 100, 255), -1)  
                for landmark in hand_landmarks.landmark:
                    cx = int(landmark.x * frame.shape[1])
                    cy = int(landmark.y * frame.shape[0])
                    cv2.circle(frame, (cx, cy), 4, (0, 0, 255), -1)

        bg_surface = pygame.image.frombuffer(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes(), (WIDTH, HEIGHT), 'RGB')
        screen.blit(bg_surface, (0, 0))
        
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 10, 20, 80))
        for i in range(0, HEIGHT, 4): pygame.draw.line(overlay, (0, 0, 0, 50), (0, i), (WIDTH, i))
        screen.blit(overlay, (0, 0))

        tip_positions = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                x = int(hand_landmarks.landmark[8].x * WIDTH)
                y = int(hand_landmarks.landmark[8].y * HEIGHT)
                tip_positions.append((x, y))

        if current_state == STATE_START:
            title_str = "指 尖 忍 者"
            t_w = game_assets.font_title.size(title_str)[0]
            draw_neon_text(screen, title_str, game_assets.font_title, COLOR_CYAN, WIDTH//2 - t_w//2, 150)
            
            sub_w = game_assets.font_sm.size("CYBERPUNK EDITION")[0]
            draw_neon_text(screen, "CYBERPUNK EDITION", game_assets.font_sm, COLOR_AMBER, WIDTH//2 - sub_w//2, 270)
            
            btn_start = draw_hud_button("系 统 启 动", 450, COLOR_CYAN, tip_positions)
            
            if any(btn_start.collidepoint(tip) for tip in tip_positions):
                pygame.time.delay(300)
                current_state = STATE_PLAYING; 
                score = missed_score = total_targets = 0
                fruits = [Fruit() for _ in range(5)]
                half_fruits = []

        elif current_state == STATE_PLAYING:
            draw_hud_panel(score, missed_score, total_targets)
            
            for f in fruits:
                f.update(); f.draw(screen)
                if not f.is_cut:
                    for tip in tip_positions:
                        if math.hypot(tip[0]-f.x, tip[1]-f.y) < 65:
                            if f.is_bomb: 
                                current_state = STATE_GAMEOVER; break
                            else:
                                f.is_cut = True; score += 1
                                if game_assets.slice_sound: game_assets.slice_sound.play()
                                img = game_assets.fruits.get(f.type)
                                if img:
                                    w, h = img.get_size(); w_h = w//2
                                    half_fruits.append(HalfFruit(img.subsurface((0,0,w_h,h)), f.x-20, f.y, f.vx-6, f.vy, f.angle, f.spin-8))
                                    half_fruits.append(HalfFruit(img.subsurface((w_h,0,w-w_h,h)), f.x+20, f.y, f.vx+6, f.vy, f.angle, f.spin+8))
                                f.reset(manual=True)
                                break 

            for hf in half_fruits[:]:
                hf.update(); hf.draw(screen)
                if hf.y > HEIGHT + 100: half_fruits.remove(hf)

        elif current_state == STATE_GAMEOVER:
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            s.fill((40, 0, 10, 200)) 
            screen.blit(s, (0, 0))
            
            t_w = game_assets.font_title.size("连 接 中 断")[0]
            draw_neon_text(screen, "连 接 中 断", game_assets.font_title, (255, 50, 50), WIDTH//2 - t_w//2, 100)
            
            hit_rate = (score / total_targets * 100) if total_targets > 0 else 0.0
            res_str = f"得分: {score}  |  错过: {missed_score}  |  命中率: {hit_rate:.1f}%"
            r_w = game_assets.font_md.size(res_str)[0]
            draw_neon_text(screen, res_str, game_assets.font_md, COLOR_AMBER, WIDTH//2 - r_w//2, 230)
            
            # --- 专属评价系统 ---
            if score < 10:
                eval_str = "评价：你菜的跟夏维鑫一样"
            elif 10 <= score < 30:
                eval_str = "评价：你跟胡齐一样菜得扣脚"
            elif 30 <= score < 60:
                eval_str = "评价：比孟子旭厉害多了"
            else:
                eval_str = "评价：你很棒，不过比闫淋洪还差一点"
                
            e_w = game_assets.font_md.size(eval_str)[0]
            draw_neon_text(screen, eval_str, game_assets.font_md, COLOR_CYAN, WIDTH//2 - e_w//2, 330)
            
            btn_retry = draw_hud_button("再 来 一 次", 480, COLOR_CYAN, tip_positions)
            btn_quit = draw_hud_button("退 出 游 戏", 600, COLOR_MAGENTA, tip_positions)
            
            if any(btn_retry.collidepoint(tip) for tip in tip_positions):
                pygame.time.delay(300)
                current_state = STATE_PLAYING
                score = missed_score = total_targets = 0
                fruits = [Fruit() for _ in range(5)]
                half_fruits = []
            elif any(btn_quit.collidepoint(tip) for tip in tip_positions): 
                running = False

        # --- 7. 双轨剑气绘制 ---
        trail_colors = [COLOR_CYAN, COLOR_MAGENTA]
        for i in range(2): 
            if i < len(tip_positions):
                trails[i].append(tip_positions[i])
                if len(trails[i]) > 12: trails[i].pop(0)
                for j in range(len(trails[i])-1):
                    width = int(18*(j/len(trails[i])))+1
                    pygame.draw.line(screen, trail_colors[i], trails[i][j], trails[i][j+1], width)
                pygame.draw.circle(screen, (255, 255, 255), tip_positions[i], 8)
                pygame.draw.circle(screen, trail_colors[i], tip_positions[i], 12, 2)
            else:
                trails[i].clear() 

        pygame.display.flip()
        clock.tick(FPS)

except Exception as e:
    import traceback
    traceback.print_exc()
finally:
    cap.release()
    pygame.quit()