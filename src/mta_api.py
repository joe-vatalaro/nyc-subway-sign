import requests
import time
from typing import List, Dict, Optional
from google.transit import gtfs_realtime_pb2
from src.config import Config


class MTAClient:
    def __init__(self, config: Config):
        self.config = config
        self.api_key = config.mta_api_key
        self.subway_base_url = "https://api-endpoint.mta.info/Dataservice/mtagtfsrealtime"
        self.bus_base_url = "https://gtfsrt.prod.obanyc.com"
        
        routes = config.get_routes()
        has_bus_routes = any(r.get("type", "subway").lower() == "bus" for r in routes)
        if has_bus_routes and not self.api_key:
            print("WARNING: Bus routes configured but no MTA_API_KEY found. Bus data will not be available.")
        
        self.subway_feed_ids = {
            "1": "1", "2": "1", "3": "1", "4": "1", "5": "1", "6": "1", "S": "1",
            "A": "26", "C": "26", "E": "26",
            "B": "21", "D": "21", "F": "21", "M": "21",
            "G": "31",
            "J": "36", "Z": "36",
            "L": "2",
            "N": "16", "Q": "16", "R": "16", "W": "16",
            "7": "51",
            "SIR": "11"
        }
    
    def _get_feed_id(self, route_id: str, route_type: str = "subway") -> Optional[str]:
        if route_type.lower() == "bus":
            return None
        return self.subway_feed_ids.get(route_id.upper())
    
    def _fetch_subway_feed(self, feed_id: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        url = f"{self.subway_base_url}/feeds/{feed_id}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            print(f"Error fetching subway feed {feed_id}: {e}")
            return None
    
    def _fetch_bus_feed(self) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        if not self.api_key:
            print("API key required for bus feed but not provided")
            return None
        
        url = f"{self.bus_base_url}/tripUpdates?key={self.api_key}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            print(f"Error fetching bus feed: {e}")
            return None
    
    def get_arrivals_for_stop(self, route_id: str, stop_id: str, direction: str = None, route_type: str = "subway") -> List[Dict]:
        if route_type.lower() == "bus":
            feed = self._fetch_bus_feed()
        else:
            feed_id = self._get_feed_id(route_id, route_type)
            if not feed_id:
                return []
            feed = self._fetch_subway_feed(feed_id)
        
        if not feed:
            return []
        
        arrivals = []
        current_time = int(time.time())
        
        for entity in feed.entity:
            if entity.HasField('trip_update'):
                trip_update = entity.trip_update
                trip = trip_update.trip
                
                route_match = trip.route_id.upper() == route_id.upper()
                if not route_match:
                    continue
                
                if direction is not None and trip.HasField('direction_id') and trip.direction_id != int(direction):
                    continue
                
                for stop_time_update in trip_update.stop_time_update:
                    if stop_time_update.stop_id == stop_id:
                        if stop_time_update.HasField('arrival'):
                            arrival_time = stop_time_update.arrival.time
                            minutes_away = (arrival_time - current_time) // 60
                            
                            if minutes_away >= 0:
                                arrivals.append({
                                    "route": route_id,
                                    "destination": trip.trip_headsign or "Unknown",
                                    "minutes_away": minutes_away,
                                    "arrival_time": arrival_time,
                                    "type": route_type.lower()
                                })
        
        arrivals.sort(key=lambda x: x["arrival_time"])
        return arrivals[:5]
    
    def get_arrivals_for_routes(self, routes: List[Dict]) -> List[Dict]:
        all_arrivals = []
        
        for route_config in routes:
            route_id = route_config.get("route_id")
            stop_id = route_config.get("stop_id")
            direction = route_config.get("direction")
            display_name = route_config.get("display_name", route_id)
            route_type = route_config.get("type", "subway")
            
            arrivals = self.get_arrivals_for_stop(route_id, stop_id, direction, route_type)
            
            for arrival in arrivals:
                arrival["display_name"] = display_name
                arrival["stop_id"] = stop_id
            
            all_arrivals.extend(arrivals)
        
        all_arrivals.sort(key=lambda x: x["arrival_time"])
        return all_arrivals

