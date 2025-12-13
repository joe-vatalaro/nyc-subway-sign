import time
from typing import List, Dict
from rgbmatrix import RGBMatrix, RGBMatrixOptions
from PIL import Image, ImageDraw, ImageFont
from src.config import Config


class LEDDisplay:
    def __init__(self, config: Config):
        self.config = config
        display_settings = config.get_display_settings()
        
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
        options.hardware_mapping = "regular"
        
        self.matrix = RGBMatrix(options=options)
        self.canvas = self.matrix.CreateFrameCanvas()
        
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 10)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        except:
            self.font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()
    
    def _create_image(self, width: int, height: int) -> Image.Image:
        return Image.new("RGB", (width, height), color=(0, 0, 0))
    
    def _draw_arrival(self, draw: ImageDraw.ImageDraw, y_offset: int, arrival: Dict, width: int):
        route = arrival.get("display_name", arrival.get("route", "?"))
        minutes = arrival.get("minutes_away", 0)
        destination = arrival.get("destination", "")
        route_type = arrival.get("type", "subway")
        
        route_color = (0, 255, 255) if route_type == "bus" else (255, 255, 255)
        route_prefix = "B" if route_type == "bus" else ""
        route_text = f"{route_prefix}{route}"
        time_text = f"{minutes} min"
        
        draw.text((2, y_offset), route_text, font=self.font, fill=route_color)
        
        time_x = width - 50
        draw.text((time_x, y_offset), time_text, font=self.font, fill=(255, 255, 0))
        
        if destination and y_offset + 12 < self.config.get_display_settings()["matrix_height"]:
            dest_text = destination[:20] + "..." if len(destination) > 20 else destination
            draw.text((2, y_offset + 12), dest_text, font=self.small_font, fill=(200, 200, 200))
    
    def show_arrivals(self, arrivals: List[Dict]):
        if not arrivals:
            self._show_no_data()
            return
        
        width = self.config.get_display_settings()["matrix_width"]
        height = self.config.get_display_settings()["matrix_height"]
        
        image = self._create_image(width, height)
        draw = ImageDraw.Draw(image)
        
        y_offset = 2
        line_height = 24
        
        for arrival in arrivals[:3]:
            if y_offset + line_height > height:
                break
            
            self._draw_arrival(draw, y_offset, arrival, width)
            y_offset += line_height
        
        self.canvas.SetImage(image)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)
    
    def _show_no_data(self):
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
        width = self.config.get_display_settings()["matrix_width"]
        height = self.config.get_display_settings()["matrix_height"]
        image = self._create_image(width, height)
        self.canvas.SetImage(image)
        self.canvas = self.matrix.SwapOnVSync(self.canvas)

