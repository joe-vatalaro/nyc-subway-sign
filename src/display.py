import time
from typing import List, Dict
from PIL import Image, ImageDraw, ImageFont
from src.config import Config

try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions
    RGB_MATRIX_AVAILABLE = True
except ImportError:
    RGB_MATRIX_AVAILABLE = False


class LEDDisplay:
    def __init__(self, config: Config):
        self.config = config
        self.hardware_available = False
        display_settings = config.get_display_settings()
        
        if RGB_MATRIX_AVAILABLE:
            try:
                options = RGBMatrixOptions()
                options.rows = display_settings["matrix_height"]
                options.cols = display_settings["matrix_width"]
                options.chain_length = display_settings["chain_length"]
                options.parallel = display_settings["parallel"]
                options.brightness = display_settings["brightness"]
                options.led_rgb_sequence = display_settings["led_rgb_sequence"]
                options.pixel_mapper_config = display_settings["pixel_mapper"]
                options.row_address_type = display_settings["row_address_type"]
                options.multiplexing = display_settings["multiplexing"]
                options.pwm_bits = display_settings["pwm_bits"]
                options.show_refresh_rate = display_settings["show_refresh_rate"]
                options.gpio_slowdown = display_settings["gpio_slowdown"]
                options.disable_hardware_pulsing = display_settings["disable_hardware_pulsing"]
                options.hardware_mapping = "adafruit-hat"
                options.panel_type = "FM6127"
                
                self.matrix = RGBMatrix(options=options)
                self.canvas = self.matrix.CreateFrameCanvas()
                self.hardware_available = True
                print("LED Matrix hardware initialized successfully")
            except Exception as e:
                print(f"Warning: Could not initialize LED Matrix hardware: {e}")
                print("Continuing in terminal-only mode...")
                self.hardware_available = False
        else:
            print("Warning: rpi-rgb-led-matrix not available. Running in terminal-only mode...")
            self.hardware_available = False
        
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 9)
        except:
            self.font = ImageFont.load_default()
    
    def _create_image(self, width: int, height: int) -> Image.Image:
        return Image.new("RGB", (width, height), color=(0, 0, 0))
    
    def _draw_arrival(self, draw: ImageDraw.ImageDraw, y_offset: int, arrival: Dict, width: int):
        route = arrival.get("display_name", arrival.get("route", "?"))
        minutes = arrival.get("minutes_away", 0)
        destination = arrival.get("destination", "")
        route_type = arrival.get("type", "subway")
        route_id = (arrival.get("route") or "").upper()

        route_colors = self.config.get_route_colors()
        hex_color = route_colors.get("BUS") if route_type == "bus" else route_colors.get(route_id)
        if hex_color and isinstance(hex_color, str) and len(hex_color) == 6:
            try:
                route_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            except Exception:
                route_color = (0, 255, 255) if route_type == "bus" else (255, 255, 255)
        else:
            route_color = (0, 255, 255) if route_type == "bus" else (255, 255, 255)

        route_id_short = (arrival.get("route") or "").split("-")[0]
        route_label = route_id_short or route

        stop_id = (arrival.get("stop_id") or "").upper()
        if route_type == "subway":
            direction = "↑" if stop_id.endswith("N") else "↓" if stop_id.endswith("S") else ""
            dest_short = direction
        else:
            dest_short = (destination or "")[:6].strip()
        time_label = f"{minutes}m"
        route_color_bright = tuple(min(255, c + 40) for c in route_color)
        time_color = (255, 255, 0)
        dest_color = (255, 255, 255)

        x = 2
        draw.text((x, y_offset), route_label, font=self.font, fill=route_color_bright)
        bbox = draw.textbbox((0, 0), route_label, font=self.font)
        x += bbox[2] - bbox[0] + 2

        if dest_short:
            draw.text((x, y_offset), dest_short, font=self.font, fill=dest_color)
            bbox = draw.textbbox((0, 0), dest_short, font=self.font)
            x += bbox[2] - bbox[0] + 4

        time_bbox = draw.textbbox((0, 0), time_label, font=self.font)
        time_width = time_bbox[2] - time_bbox[0]
        draw.text((width - time_width - 2, y_offset), time_label, font=self.font, fill=time_color)
    
    def show_arrivals(self, arrivals: List[Dict]):
        if not self.hardware_available:
            return

        if not arrivals:
            self._show_no_data()
            return

        width = self.config.get_display_settings()["matrix_width"]
        height = self.config.get_display_settings()["matrix_height"]

        line_height = 10
        divider_height = 1
        row_height = line_height + divider_height
        top_padding = 0

        image = self._create_image(width, height)
        draw = ImageDraw.Draw(image)

        for i, arrival in enumerate(arrivals[:3]):
            y_offset = top_padding + i * row_height
            if y_offset + line_height > height:
                break

            self._draw_arrival(draw, y_offset, arrival, width)

            if i < 2 and y_offset + row_height < height:
                divider_y = y_offset + line_height
                draw.line([(0, divider_y), (width, divider_y)], fill=(60, 60, 60))

        self.canvas.SetImage(image)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def _show_no_data(self):
        if not self.hardware_available:
            return
        
        width = self.config.get_display_settings()["matrix_width"]
        height = self.config.get_display_settings()["matrix_height"]
        
        image = self._create_image(width, height)
        draw = ImageDraw.Draw(image)
        
        text = "No Data"
        bbox = draw.textbbox((0, 0), text, font=self.font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        draw.text((x, y), text, font=self.font, fill=(255, 0, 0))
        
        self.canvas.SetImage(image)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def clear(self):
        if not self.hardware_available:
            return
        
        width = self.config.get_display_settings()["matrix_width"]
        height = self.config.get_display_settings()["matrix_height"]
        image = self._create_image(width, height)
        self.canvas.SetImage(image)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

