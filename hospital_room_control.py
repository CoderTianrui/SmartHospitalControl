import pygame
import sys
import speech_recognition as sr
import requests
import os
import threading
import time
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Pygame
pygame.init()

# Color definitions
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 100, 255)
LIGHT_BLUE = (120, 190, 255)
DARK_BLUE = (0, 50, 150)
GRAY = (200, 200, 200)
DARK_GRAY = (100, 100, 100)
RED = (255, 50, 50)
GREEN = (50, 200, 50)
LIGHT_GREEN = (220, 255, 220)
OPTIMAL_GREEN = (100, 230, 100)
YELLOW = (250, 200, 0)
BG_BLUE = (230, 240, 255)
LIGHT_GRAY = (240, 240, 240)
ORANGE = (255, 165, 0)

# Window settings
WINDOW_WIDTH = 950
WINDOW_HEIGHT = 700
screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Smart Hospital Room Control System")

# Try to load custom fonts, fall back to default if not available
try:
    title_font = pygame.font.Font(None, 42)
    font = pygame.font.Font(None, 32)
    small_font = pygame.font.Font(None, 24)
    tiny_font = pygame.font.Font(None, 20)
except:
    title_font = pygame.font.SysFont("arial", 36)
    font = pygame.font.SysFont("arial", 28)
    small_font = pygame.font.SysFont("arial", 22)
    tiny_font = pygame.font.SysFont("arial", 18)

# Optimal ranges for environmental variables
OPTIMAL_RANGES = {
    "temperature": (21, 24),  # Optimal temperature range in °C
    "humidity": (40, 60),     # Optimal humidity range in %
    "light": (40, 70),        # Optimal light intensity range in %
    "co2": (400, 600)         # Optimal CO2 concentration range in ppm
}

class Slider:
    def __init__(self, x, y, width, height, min_val, max_val, initial_val, title, parameter_type):
        self.rect = pygame.Rect(x, y, width, height)
        self.min_val = min_val
        self.max_val = max_val
        self.value = initial_val
        self.title = title
        self.parameter_type = parameter_type  # temperature, humidity, light, co2
        self.sliding = False
        # Position handle correctly based on value
        relative_pos = (initial_val - min_val) / (max_val - min_val)
        handle_x = x + int(relative_pos * width) - 10
        self.handle_rect = pygame.Rect(handle_x, y - 10, 20, height + 20)
        self.track_color = GRAY
        self.handle_color = BLUE
        self.handle_hover_color = LIGHT_BLUE
        self.is_hover = False
        self.optimal_range = OPTIMAL_RANGES.get(parameter_type, (min_val, max_val))

    def update_handle_position(self):
        # Update handle position based on current value
        relative_pos = (self.value - self.min_val) / (self.max_val - self.min_val)
        self.handle_rect.centerx = self.rect.x + int(relative_pos * self.rect.width)

    def draw(self, screen):
        # Draw title
        title_text = font.render(f"{self.title}: {self.value:.1f}", True, DARK_BLUE)
        screen.blit(title_text, (self.rect.x, self.rect.y - 35))
        
        # Draw slider track
        pygame.draw.rect(screen, self.track_color, self.rect, border_radius=3)
        
        # Draw optimal range indicator
        opt_min_x = self.rect.x + int((self.optimal_range[0] - self.min_val) / (self.max_val - self.min_val) * self.rect.width)
        opt_max_x = self.rect.x + int((self.optimal_range[1] - self.min_val) / (self.max_val - self.min_val) * self.rect.width)
        opt_width = opt_max_x - opt_min_x
        opt_rect = pygame.Rect(opt_min_x, self.rect.y, opt_width, self.rect.height)
        pygame.draw.rect(screen, OPTIMAL_GREEN, opt_rect, border_radius=3)
        
        # Draw filled portion
        filled_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.rect.width)
        filled_rect = pygame.Rect(self.rect.x, self.rect.y, filled_width, self.rect.height)
        pygame.draw.rect(screen, LIGHT_BLUE, filled_rect, border_radius=3)
        
        # Draw slider handle
        handle_color = self.handle_hover_color if self.is_hover or self.sliding else self.handle_color
        pygame.draw.rect(screen, handle_color, self.handle_rect, border_radius=5)
        pygame.draw.rect(screen, DARK_BLUE, self.handle_rect, 2, border_radius=5)
        
        # Draw optimal range text
        range_text = tiny_font.render(f"Optimal: {self.optimal_range[0]}-{self.optimal_range[1]}", True, DARK_BLUE)
        screen.blit(range_text, (self.rect.right - range_text.get_width(), self.rect.y + self.rect.height + 5))

    def handle_event(self, event):
        mouse_pos = pygame.mouse.get_pos()
        self.is_hover = self.handle_rect.collidepoint(mouse_pos)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.sliding = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.sliding = False
        elif event.type == pygame.MOUSEMOTION and self.sliding:
            rel_x = max(self.rect.x, min(event.pos[0], self.rect.right))
            self.handle_rect.centerx = rel_x
            self.value = self.min_val + (rel_x - self.rect.x) / self.rect.width * (self.max_val - self.min_val)
            # Ensure handle stays within slider bounds
            self.update_handle_position()

    def check_limits(self, value):
        """Check if the value is within bounds and return True if in range"""
        return self.min_val <= value <= self.max_val

class Button:
    def __init__(self, x, y, width, height, text, color):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.color = color
        self.hover_color = self._lighten_color(color)
        self.text_color = BLACK
        self.is_pressed = False
        self.is_hover = False
        self.status_text = ""
        self.status_color = BLACK

    def _lighten_color(self, color):
        r, g, b = color
        return min(r + 30, 255), min(g + 30, 255), min(b + 30, 255)

    def draw(self, screen):
        # Draw button with hover effect
        color = self.hover_color if self.is_hover else self.color
        if self.is_pressed:
            color = self._darken_color(color)
            
        # Draw button with rounded corners
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, DARK_GRAY, self.rect, 2, border_radius=8)
        
        # Center text on button
        text_surface = font.render(self.text, True, self.text_color)
        text_rect = text_surface.get_rect(center=self.rect.center)
        screen.blit(text_surface, text_rect)
        
        # Draw status text below button
        if self.status_text:
            status = small_font.render(self.status_text, True, self.status_color)
            status_rect = status.get_rect(centerx=self.rect.centerx, top=self.rect.bottom + 5)
            screen.blit(status, status_rect)

    def _darken_color(self, color):
        r, g, b = color
        return max(r - 30, 0), max(g - 30, 0), max(b - 30, 0)

    def handle_event(self, event):
        mouse_pos = pygame.mouse.get_pos()
        self.is_hover = self.rect.collidepoint(mouse_pos)
        
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.is_pressed = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.is_pressed = False
        return False

    def set_status(self, text, color=BLACK):
        self.status_text = text
        self.status_color = color

class TextBox:
    def __init__(self, x, y, width, height, title="", bg_color=WHITE):
        self.rect = pygame.Rect(x, y, width, height)
        self.title = title
        self.text = ""
        self.text_color = BLACK
        self.title_color = DARK_BLUE
        self.border_color = DARK_GRAY
        self.background_color = bg_color

    def draw(self, screen):
        # Draw title
        if self.title:
            title_text = small_font.render(self.title, True, self.title_color)
            screen.blit(title_text, (self.rect.x, self.rect.y - 20))
        
        # Draw background with rounded corners
        pygame.draw.rect(screen, self.background_color, self.rect, border_radius=5)
        
        # Draw border
        pygame.draw.rect(screen, self.border_color, self.rect, 2, border_radius=5)
        
        # Draw text
        if self.text:
            # Split text into lines if it's too long
            words = self.text.split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                test_line = ' '.join(current_line)
                if small_font.size(test_line)[0] > self.rect.width - 20:
                    if len(current_line) > 1:
                        current_line.pop()
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(test_line)
                        current_line = []
            
            if current_line:
                lines.append(' '.join(current_line))
            
            # Draw each line
            y_offset = self.rect.y + 10
            for line in lines:
                text_surface = small_font.render(line, True, self.text_color)
                screen.blit(text_surface, (self.rect.x + 10, y_offset))
                y_offset += small_font.get_height() + 2

    def set_text(self, text):
        self.text = text

class PopupWindow:
    def __init__(self, title, message, width=400, height=200):
        self.rect = pygame.Rect(WINDOW_WIDTH//2 - width//2, WINDOW_HEIGHT//2 - height//2, width, height)
        self.title = title
        self.message = message
        self.active = False
        self.close_button = Button(self.rect.right - 100, self.rect.bottom - 50, 80, 40, "Close", RED)
        
    def draw(self, screen):
        if not self.active:
            return
            
        # Draw semi-transparent overlay
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        screen.blit(overlay, (0, 0))
        
        # Draw popup window
        pygame.draw.rect(screen, WHITE, self.rect, border_radius=10)
        pygame.draw.rect(screen, DARK_BLUE, self.rect, 3, border_radius=10)
        
        # Draw title
        title_text = font.render(self.title, True, RED)
        screen.blit(title_text, (self.rect.x + self.rect.width//2 - title_text.get_width()//2, self.rect.y + 20))
        
        # Draw message (support multiple lines)
        lines = self.message.split('\n')
        y_offset = self.rect.y + 70
        for line in lines:
            message_text = small_font.render(line, True, BLACK)
            screen.blit(message_text, (self.rect.x + self.rect.width//2 - message_text.get_width()//2, y_offset))
            y_offset += small_font.get_height() + 5
        
        # Draw close button
        self.close_button.draw(screen)
        
    def handle_event(self, event):
        if not self.active:
            return False
            
        if self.close_button.handle_event(event):
            self.active = False
            return True
        return False
        
    def show(self, message=None):
        if message:
            self.message = message
        self.active = True

class VoiceControl:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Set recognizer properties for better sensitivity
        self.recognizer.energy_threshold = 300  # Lower threshold for detecting speech
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.5  # Shorter pause to detect end of phrase
        
        self.api_key = os.getenv('DEEPSEEK_API_KEY')
        self.is_listening = False
        self.microphone = None
        self.available_mics = []
        self.check_microphone()
        self.last_speech = ""
        self.listening_thread = None
        self.stop_listening = False
        self.result = None
        self.mic_index = 0

    def check_microphone(self):
        try:
            # Get a list of all available microphones
            self.available_mics = sr.Microphone.list_microphone_names()
            if len(self.available_mics) > 0:
                # Try to use the default microphone (index=0)
                self.mic_index = 0
                self.microphone = sr.Microphone(device_index=self.mic_index)
                return True
            return False
        except Exception as e:
            print(f"Microphone initialization error: {e}")
            return False

    def cycle_microphone(self):
        """Switch to the next available microphone"""
        if len(self.available_mics) > 0:
            self.mic_index = (self.mic_index + 1) % len(self.available_mics)
            try:
                self.microphone = sr.Microphone(device_index=self.mic_index)
                mic_name = self.available_mics[self.mic_index]
                system_status_box.set_text(f"Switched to microphone: {mic_name}")
                return True
            except Exception as e:
                system_status_box.set_text(f"Error switching mic: {str(e)[:50]}")
                return False
        else:
            system_status_box.set_text("No microphones available")
            return False

    def get_mic_info(self):
        """Return information about the current microphone setup"""
        if not self.available_mics:
            return "No microphones detected"
        
        current_mic = f"Current mic ({self.mic_index}): {self.available_mics[self.mic_index]}"
        all_mics = f"Available mics: {len(self.available_mics)}"
        
        threshold = f"Energy threshold: {self.recognizer.energy_threshold}"
        return f"{current_mic}\n{all_mics}\n{threshold}"

    def start_listening(self):
        if not self.microphone:
            if not self.check_microphone():
                system_status_box.set_text("No microphone available. Check system settings.")
                return "Microphone not available"
        
        # Reset flags and result
        self.stop_listening = False
        self.result = None
        self.is_listening = True
        
        # Clear previous speech
        user_speech_box.set_text("Listening...")
        
        # Start the listening thread
        self.listening_thread = threading.Thread(target=self._listen_thread)
        self.listening_thread.daemon = True
        self.listening_thread.start()
        
        return "Listening started"

    def _listen_thread(self):
        try:
            with self.microphone as source:
                speak_button.set_status("Adjusting for noise...", BLUE)
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                system_status_box.set_text(f"Adjusted threshold: {self.recognizer.energy_threshold}")
                
                speak_button.set_status("Listening... Please speak", GREEN)
                
                # Set a shorter timeout for better responsiveness
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=3)
                
                if self.stop_listening:
                    speak_button.set_status("Listening cancelled", RED)
                    self.is_listening = False
                    return
                    
                speak_button.set_status("Processing speech...", BLUE)
                text = self.recognizer.recognize_google(audio)
                self.last_speech = text
                user_speech_box.set_text(f"You said: {text}")
                system_status_box.set_text("Speech recognition successful")
                
                if not self.stop_listening:
                    self.result = self.process_command(text)
        except sr.WaitTimeoutError:
            speak_button.set_status("No speech detected", RED)
            system_status_box.set_text("No speech detected - try speaking louder or check microphone")
            user_speech_box.set_text("No speech detected")
        except sr.RequestError as e:
            speak_button.set_status("Speech service unavailable", RED)
            system_status_box.set_text(f"Network error: {str(e)[:100]}")
        except Exception as e:
            speak_button.set_status(f"Error", RED)
            system_status_box.set_text(f"Recognition error: {str(e)[:100]}")
            print(f"Exception: {e}")
        finally:
            self.is_listening = False

    def cancel_listening(self):
        if self.is_listening:
            self.stop_listening = True
            speak_button.set_status("Cancelling...", YELLOW)
            # The thread will exit on its own

    def extract_number_and_unit(self, text):
        """Extract number and unit from text like 'raise temperature by 2 degrees'"""
        text = text.lower()
        
        # Check for percentage adjustment
        percent_match = re.search(r'(\d+\.?\d*)(\s*%|\s*percent)', text)
        if percent_match:
            value = float(percent_match.group(1))
            return value, "percent"
            
        # Check for direct value
        direct_value = re.search(r'to\s+(\d+\.?\d*)', text)
        if direct_value:
            return float(direct_value.group(1)), "absolute"
            
        # Check for relative adjustment
        increase_match = re.search(r'(raise|increase|up).*?(\d+\.?\d*)', text)
        if increase_match:
            value = float(increase_match.group(2))
            return value, "increase"
            
        decrease_match = re.search(r'(lower|decrease|down|reduce).*?(\d+\.?\d*)', text)
        if decrease_match:
            value = float(decrease_match.group(2))
            return -value, "decrease"
        
        # Default fallback - just extract any number
        numbers = re.findall(r'\d+\.?\d*', text)
        if numbers:
            return float(numbers[0]), "absolute"
            
        return None, None

    def process_command(self, text):
        # Process voice command
        try:
            text = text.lower()
            
            # Handle comfort-based commands (too hot/cold)
            if "too hot" in text or "too warm" in text or "very hot" in text:
                parameter = "temperature"
                slider = temperature_slider
                current_value = slider.value
                
                # If it's too hot, adjust to the lower end of optimal range
                optimal_min = slider.optimal_range[0]
                
                if current_value > optimal_min:
                    return {"parameter": parameter, "value": optimal_min, "comfort_adjust": "cooler"}
                else:
                    return {"parameter": parameter, "value": max(slider.min_val, current_value - 1), "comfort_adjust": "cooler"}
                    
            elif "too cold" in text or "too cool" in text or "very cold" in text or "freezing" in text:
                parameter = "temperature"
                slider = temperature_slider
                current_value = slider.value
                
                # If it's too cold, adjust to the upper end of optimal range
                optimal_max = slider.optimal_range[1]
                
                if current_value < optimal_max:
                    return {"parameter": parameter, "value": optimal_max, "comfort_adjust": "warmer"}
                else:
                    return {"parameter": parameter, "value": min(slider.max_val, current_value + 1), "comfort_adjust": "warmer"}
            
            # Handle comfort-based commands for humidity
            elif "too dry" in text or "very dry" in text:
                parameter = "humidity"
                slider = humidity_slider
                current_value = slider.value
                
                # If it's too dry, adjust to the upper end of optimal range
                optimal_max = slider.optimal_range[1]
                
                if current_value < optimal_max:
                    return {"parameter": parameter, "value": optimal_max, "comfort_adjust": "more humid"}
                else:
                    return {"parameter": parameter, "value": min(slider.max_val, current_value + 5), "comfort_adjust": "more humid"}
                    
            elif "too humid" in text or "too damp" in text or "very humid" in text:
                parameter = "humidity"
                slider = humidity_slider
                current_value = slider.value
                
                # If it's too humid, adjust to the lower end of optimal range
                optimal_min = slider.optimal_range[0]
                
                if current_value > optimal_min:
                    return {"parameter": parameter, "value": optimal_min, "comfort_adjust": "less humid"}
                else:
                    return {"parameter": parameter, "value": max(slider.min_val, current_value - 5), "comfort_adjust": "less humid"}
                    
            # Handle comfort-based commands for light
            elif "too bright" in text or "too light" in text:
                parameter = "light"
                slider = light_slider
                current_value = slider.value
                
                # If it's too bright, adjust to the lower end of optimal range
                optimal_min = slider.optimal_range[0]
                
                if current_value > optimal_min:
                    return {"parameter": parameter, "value": optimal_min, "comfort_adjust": "dimmer"}
                else:
                    return {"parameter": parameter, "value": max(slider.min_val, current_value - 10), "comfort_adjust": "dimmer"}
                    
            elif "too dark" in text or "too dim" in text:
                parameter = "light"
                slider = light_slider
                current_value = slider.value
                
                # If it's too dark, adjust to the upper end of optimal range
                optimal_max = slider.optimal_range[1]
                
                if current_value < optimal_max:
                    return {"parameter": parameter, "value": optimal_max, "comfort_adjust": "brighter"}
                else:
                    return {"parameter": parameter, "value": min(slider.max_val, current_value + 10), "comfort_adjust": "brighter"}
            
            # Determine which parameter is being adjusted (original logic)
            parameter = None
            if "temperature" in text or "hot" in text or "cold" in text or "warm" in text:
                parameter = "temperature"
                slider = temperature_slider
            elif "humid" in text or "humidity" in text or "moisture" in text or "dry" in text or "damp" in text:
                parameter = "humidity"
                slider = humidity_slider
            elif "light" in text or "bright" in text or "dark" in text or "dim" in text:
                parameter = "light"
                slider = light_slider
            elif "carbon dioxide" in text or "co2" in text:
                parameter = "co2"
                slider = co2_slider
            else:
                system_status_box.set_text(f"Unrecognized parameter in: '{text}'. Try saying 'Set temperature to 25 degrees'")
                return {"parameter": "unknown", "value": 0}
                
            # Get current value from appropriate slider
            current_value = slider.value
            
            # Extract the number and adjustment type from the command
            value, adjustment_type = self.extract_number_and_unit(text)
            
            if value is None:
                system_status_box.set_text(f"Couldn't extract a number from: '{text}'")
                return {"parameter": parameter, "value": current_value}
                
            # Apply the adjustment based on type
            if adjustment_type == "percent":
                # Calculate percentage adjustment
                range_size = slider.max_val - slider.min_val
                adjustment = (range_size * value) / 100
                if "increase" in text or "raise" in text or "up" in text:
                    new_value = current_value + adjustment
                elif "decrease" in text or "lower" in text or "down" in text or "reduce" in text:
                    new_value = current_value - adjustment
                else:
                    # Set to specific percentage of range
                    new_value = slider.min_val + (range_size * value) / 100
            elif adjustment_type == "increase" or adjustment_type == "decrease":
                # Direct value increase/decrease
                new_value = current_value + value
            else:  # absolute
                # Set to specific value
                new_value = value
                
            # Check if value is within slider range before setting
            if not slider.check_limits(new_value):
                # Return the out-of-range value with a flag
                return {
                    "parameter": parameter, 
                    "value": current_value,
                    "requested_value": new_value,
                    "out_of_range": True
                }
                
            # Ensure value is within slider range
            new_value = max(slider.min_val, min(slider.max_val, new_value))
            
            # Return the result
            return {"parameter": parameter, "value": new_value}
            
        except Exception as e:
            speak_button.set_status(f"API Error", RED)
            system_status_box.set_text(f"Command processing error: {str(e)[:100]}")
            return None

# Create control components with improved layout
temperature_slider = Slider(60, 140, 320, 16, 16, 30, 24, "Temperature (°C)", "temperature")
humidity_slider = Slider(60, 230, 320, 16, 30, 70, 50, "Humidity (%)", "humidity")
light_slider = Slider(60, 320, 320, 16, 0, 100, 50, "Light (%)", "light")
co2_slider = Slider(60, 410, 320, 16, 400, 1000, 600, "CO2 (ppm)", "co2")

# Create larger buttons with clearer labels
speak_button = Button(580, 110, 240, 60, "Voice Control", LIGHT_BLUE)
switch_mic_button = Button(580, 220, 240, 60, "Switch Mic", YELLOW)
cancel_button = Button(580, 330, 240, 60, "Cancel", RED)

# Add call nurse button and emergency button
call_nurse_button = Button(580, 540, 110, 50, "Call Nurse", GREEN)
emergency_button = Button(710, 540, 110, 50, "Emergency", RED)

# Create popup window for out-of-range warnings
range_warning_popup = PopupWindow("Out of Range", "Please adjust the value within the allowed range.", width=450, height=230)

# User speech display box, placed below buttons
user_speech_box = TextBox(580, 430, 320, 80, "User Speech", BG_BLUE)
# System status display box, placed at bottom left
system_status_box = TextBox(60, 480, 400, 170, "System Status", LIGHT_GRAY)

voice_control = VoiceControl()
if not voice_control.microphone:
    speak_button.set_status("No microphone detected", RED)
    system_status_box.set_text("No microphones found. Check your system settings.")
else:
    system_status_box.set_text(voice_control.get_mic_info())

def draw_round_rect(surface, color, rect, radius=10, border=0):
    """Draw a rounded rectangle"""
    rect = pygame.Rect(rect)
    color = pygame.Color(*color)
    alpha = color.a
    color.a = 0
    pos = rect.topleft
    rect.topleft = 0, 0
    rectangle = pygame.Surface(rect.size, pygame.SRCALPHA)

    circle = pygame.Surface([min(rect.size) * 3] * 2, pygame.SRCALPHA)
    pygame.draw.ellipse(circle, (0, 0, 0), circle.get_rect(), 0)
    circle = pygame.transform.smoothscale(circle, [radius * 2] * 2)

    radius = min(rect.height // 2, radius)
    for corner, pos in (
            (0, pygame.Rect(0, 0, radius, radius)),
            (1, pygame.Rect(rect.width - radius, 0, radius, radius)),
            (2, pygame.Rect(rect.width - radius, rect.height - radius, radius, radius)),
            (3, pygame.Rect(0, rect.height - radius, radius, radius))):
        rectangle.blit(circle, pos)

    rectangle.fill((0, 0, 0), rect.inflate(-radius * 2, 0))
    rectangle.fill((0, 0, 0), rect.inflate(0, -radius * 2))

    rectangle.fill(color, special_flags=pygame.BLEND_RGBA_MAX)
    rectangle.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MIN)

    return rectangle, pos

# Main loop
running = True
last_time = time.time()
while running:
    current_time = time.time()
    dt = current_time - last_time
    last_time = current_time
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        
        # Handle slider events
        temperature_slider.handle_event(event)
        humidity_slider.handle_event(event)
        light_slider.handle_event(event)
        co2_slider.handle_event(event)
        
        # Handle voice button events
        if speak_button.handle_event(event) and not voice_control.is_listening:
            voice_control.start_listening()
            
        # Handle microphone switch button
        if switch_mic_button.handle_event(event) and not voice_control.is_listening:
            if voice_control.cycle_microphone():
                speak_button.set_status("Microphone switched", GREEN)
                system_status_box.set_text(voice_control.get_mic_info())
            
        # Handle cancel button
        if cancel_button.handle_event(event) and voice_control.is_listening:
            voice_control.cancel_listening()
        
        # Handle call nurse and emergency buttons
        if call_nurse_button.handle_event(event):
            call_nurse_button.set_status("Call sent", BLUE)
            system_status_box.set_text("Nurse has been called. Please wait...")
            # Reset status after 3 seconds
            threading.Timer(3.0, lambda: call_nurse_button.set_status("")).start()
            
        if emergency_button.handle_event(event):
            emergency_button.set_status("Emergency call sent!", RED)
            system_status_box.set_text("Emergency call sent! Medical staff will arrive immediately...")
            # Reset status after 3 seconds
            threading.Timer(3.0, lambda: emergency_button.set_status("")).start()
        
        # Handle popup window events
        range_warning_popup.handle_event(event)
    
    # Check if listening thread has completed and returned a result
    if not voice_control.is_listening and voice_control.result:
        try:
            result = voice_control.result
            if "parameter" in result and "value" in result:
                # Handle comfort-based adjustments
                if "comfort_adjust" in result:
                    parameter = result["parameter"]
                    new_value = result["value"]
                    adjust_type = result["comfort_adjust"]
                    
                    if parameter == "temperature":
                        temperature_slider.value = new_value
                        temperature_slider.update_handle_position()
                        system_status_box.set_text(f"Adjusting to {adjust_type} temperature: {new_value:.1f}°C")
                    elif parameter == "humidity":
                        humidity_slider.value = new_value
                        humidity_slider.update_handle_position()
                        system_status_box.set_text(f"Adjusting to {adjust_type} humidity: {new_value:.1f}%")
                    elif parameter == "light":
                        light_slider.value = new_value
                        light_slider.update_handle_position()
                        system_status_box.set_text(f"Adjusting to {adjust_type} light level: {new_value:.1f}%")
                # Check if command was out of range
                elif result.get("out_of_range", False):
                    parameter = result["parameter"]
                    requested = result["requested_value"]
                    
                    if parameter == "temperature":
                        slider = temperature_slider
                        unit = "°C"
                    elif parameter == "humidity":
                        slider = humidity_slider
                        unit = "%"
                    elif parameter == "light":
                        slider = light_slider
                        unit = "%"
                    elif parameter == "co2":
                        slider = co2_slider
                        unit = "ppm"
                    
                    # Show popup with range information
                    warning_message = f"The requested {parameter} value {requested:.1f}{unit} \nis out of the allowed range.\nAllowed range: {slider.min_val} - {slider.max_val}{unit}\nPlease try with a suitable value."
                    range_warning_popup.show(warning_message)
                    system_status_box.set_text(f"Value {requested:.1f} out of range {slider.min_val}-{slider.max_val}")
                else:
                    # Normal value setting
                    if result["parameter"] == "temperature":
                        temperature_slider.value = result["value"]
                        temperature_slider.update_handle_position()  # Update handle to match value
                        system_status_box.set_text(f"Temperature set to {result['value']:.1f} °C")
                    elif result["parameter"] == "humidity":
                        humidity_slider.value = result["value"]
                        humidity_slider.update_handle_position()
                        system_status_box.set_text(f"Humidity set to {result['value']:.1f} %")
                    elif result["parameter"] == "light":
                        light_slider.value = result["value"]
                        light_slider.update_handle_position()
                        system_status_box.set_text(f"Light set to {result['value']:.1f} %")
                    elif result["parameter"] == "co2":
                        co2_slider.value = result["value"]
                        co2_slider.update_handle_position()
                        system_status_box.set_text(f"CO2 concentration set to {result['value']:.1f} ppm")
            voice_control.result = None
        except Exception as e:
            speak_button.set_status(f"Error", RED)
            system_status_box.set_text(f"Command parsing error: {str(e)[:100]}")
            voice_control.result = None

    # Draw interface
    screen.fill(WHITE)
    
    # Draw title with a nicer background
    title_bg = pygame.Rect(0, 0, WINDOW_WIDTH, 70)
    pygame.draw.rect(screen, BG_BLUE, title_bg)
    pygame.draw.line(screen, DARK_BLUE, (0, 70), (WINDOW_WIDTH, 70), 2)
    
    title = title_font.render("Smart Hospital Room Control System", True, DARK_BLUE)
    screen.blit(title, (WINDOW_WIDTH//2 - title.get_width()//2, 20))
    
    # Draw dividing line
    pygame.draw.line(screen, BLUE, (470, 90), (470, WINDOW_HEIGHT-20), 2)
    
    # Draw control panel background
    control_panel = pygame.Rect(20, 90, 430, 370)
    pygame.draw.rect(screen, LIGHT_GREEN, control_panel, border_radius=10)
    pygame.draw.rect(screen, DARK_GRAY, control_panel, 2, border_radius=10)
    
    # Draw voice control panel background
    voice_panel = pygame.Rect(490, 90, 440, 370)
    pygame.draw.rect(screen, BG_BLUE, voice_panel, border_radius=10)
    pygame.draw.rect(screen, DARK_GRAY, voice_panel, 2, border_radius=10)
    
    # Draw control components
    temperature_slider.draw(screen)
    humidity_slider.draw(screen)
    light_slider.draw(screen)
    co2_slider.draw(screen)
    speak_button.draw(screen)
    switch_mic_button.draw(screen)
    cancel_button.draw(screen)
    user_speech_box.draw(screen)
    system_status_box.draw(screen)
    
    # Draw new buttons
    call_nurse_button.draw(screen)
    emergency_button.draw(screen)
    
    # Draw popup window if active
    range_warning_popup.draw(screen)

    pygame.display.flip()

pygame.quit()
sys.exit() 