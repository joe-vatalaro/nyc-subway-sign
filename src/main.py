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
    
    def run(self):
        print("Starting NYC Subway Sign...")
        routes = self.config.get_routes()
        subway_count = sum(1 for r in routes if r.get("type", "subway").lower() == "subway")
        bus_count = sum(1 for r in routes if r.get("type", "subway").lower() == "bus")
        print(f"Monitoring {len(routes)} route(s): {subway_count} subway, {bus_count} bus")
        
        while self.running:
            try:
                routes = self.config.get_routes()
                arrivals = self.mta_client.get_arrivals_for_routes(routes)
                
                if arrivals:
                    print(f"Found {len(arrivals)} upcoming arrivals")
                    self.display.show_arrivals(arrivals)
                else:
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

