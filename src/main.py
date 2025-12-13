#!/usr/bin/env python3
import time
import signal
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import Config
from src.mta_api import MTAClient
from src.display import LEDDisplay


class SubwaySign:
    def __init__(self):
        self.config = Config()
        self.mta_client = MTAClient(self.config)
        self.display = LEDDisplay(self.config)
        self.running = True
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print("\nShutting down...")
        self.running = False
        self.display.clear()
        sys.exit(0)
    
    def _print_arrivals(self, arrivals):
        if not arrivals:
            print("  No arrivals found")
            return
        
        print(f"\n  Found {len(arrivals)} upcoming arrival(s):")
        print("  " + "-" * 60)
        def colorize(text: str, route: str, route_type: str) -> str:
            if not self.config.terminal_colors:
                return text
            if route_type.upper() == "BUS":
                return f"\033[36m{text}\033[0m"  # cyan
            # Simple, readable defaults for common subway colors
            r = (route or "").upper()
            if r in ("4", "5", "6"):
                return f"\033[32m{text}\033[0m"  # green
            if r in ("B", "D", "F", "M"):
                return f"\033[33m{text}\033[0m"  # yellow-ish for orange
            if r in ("L", "GS", "FS", "H", "S"):
                return f"\033[37m{text}\033[0m"  # gray/white
            return text

        for arrival in arrivals:
            route_type = arrival.get("type", "subway").upper()
            route_display = arrival.get("display_name", arrival.get("route", "?"))
            minutes = arrival.get("minutes_away", 0)
            destination = arrival.get("destination", "Unknown")
            stop_label = arrival.get("stop_name") or arrival.get("stop_id", "")
            
            route_type_indicator = "[BUS]" if route_type == "BUS" else "[SUBWAY]"
            route_label = colorize(f"{route_display:12}", arrival.get("route", ""), route_type)
            dest_label = colorize(f"{destination[:30]:30}", arrival.get("route", ""), route_type)
            print(f"  {route_type_indicator} {route_label} → {dest_label} | {minutes:3} min | Stop: {stop_label}")
        print("  " + "-" * 60)
    
    def run(self):
        print("Starting NYC Subway Sign...")
        routes = self.config.get_routes()
        subway_count = sum(1 for r in routes if r.get("type", "subway").lower() == "subway")
        bus_count = sum(1 for r in routes if r.get("type", "subway").lower() == "bus")
        print(f"Monitoring {len(routes)} route(s): {subway_count} subway, {bus_count} bus")
        
        if self.config.verbose_terminal:
            print("\nTerminal output enabled - arrivals will be printed here")
            print("=" * 70)
        
        while self.running:
            try:
                routes = self.config.get_routes()
                arrivals = self.mta_client.get_arrivals_for_routes(routes)
                
                if self.config.verbose_terminal:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Fetching arrivals...")
                    self._print_arrivals(arrivals)
                
                if arrivals:
                    if not self.config.verbose_terminal:
                        print(f"Found {len(arrivals)} upcoming arrivals")
                    self.display.show_arrivals(arrivals)
                else:
                    if not self.config.verbose_terminal:
                        print("No arrivals found")
                    self.display._show_no_data()
                
                time.sleep(self.config.update_interval)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(5)
        
        self.display.clear()


if __name__ == "__main__":
    sign = SubwaySign()
    sign.run()

