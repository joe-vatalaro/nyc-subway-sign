import requests
import time
import urllib.parse
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
from google.transit import gtfs_realtime_pb2
from src.config import Config


class MTAClient:
    def __init__(self, config: Config):
        self.config = config
        self.bustime_api_key = config.bustime_api_key
        self.bus_api_mode = config.bus_api_mode
        self.subway_terminals = config.get_subway_terminals()
        self.subway_base_url = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds"
        self.bus_gtfsrt_base_url = "https://gtfsrt.prod.obanyc.com"
        self.bus_siri_base_url = "https://bustime.mta.info/api/siri"
        
        routes = config.get_routes()
        has_bus_routes = any(r.get("type", "subway").lower() == "bus" for r in routes)
        # Subway feeds work without an API key; if a feed returns 403, set MTA_API_KEY.

        if not self.bustime_api_key and has_bus_routes:
            if has_bus_routes:
                print("WARNING: Bus routes configured but no BUSTIME_API_KEY found. Bus data will not be available.")
        
        self.subway_feed_paths = {
            "1": "nyct/gtfs", "2": "nyct/gtfs", "3": "nyct/gtfs", "4": "nyct/gtfs", 
            "5": "nyct/gtfs", "6": "nyct/gtfs", "S": "nyct/gtfs",
            "A": "nyct/gtfs-ace", "C": "nyct/gtfs-ace", "E": "nyct/gtfs-ace",
            "B": "nyct/gtfs-bdfm", "D": "nyct/gtfs-bdfm", "F": "nyct/gtfs-bdfm", "M": "nyct/gtfs-bdfm",
            "G": "nyct/gtfs-g",
            "J": "nyct/gtfs-jz", "Z": "nyct/gtfs-jz",
            "L": "nyct/gtfs-l",
            "N": "nyct/gtfs-nqrw", "Q": "nyct/gtfs-nqrw", "R": "nyct/gtfs-nqrw", "W": "nyct/gtfs-nqrw",
            "7": "nyct/gtfs-7",
            "SIR": "nyct/gtfs-si"
        }
    
    def _get_trip_display_text(self, trip: gtfs_realtime_pb2.TripDescriptor) -> str:
        """
        GTFS-Realtime TripDescriptor does NOT include a headsign field.
        We use trip_id (when available) as a best-effort identifier.
        """
        try:
            trip_id = getattr(trip, "trip_id", "")
        except Exception:
            trip_id = ""

        return trip_id or "Unknown trip"

    def _get_subway_terminal_from_trip_id(self, route_id: str, trip_id: str) -> str:
        """
        Best-effort subway "destination/headsign" mapping.
        - We infer direction from trip_id suffix patterns like '..N' / '..S'
        - Then map (route_id, direction) to a human terminal name via config/subway_overrides.json
        """
        if not trip_id:
            return ""

        direction_letter = ""
        # NYCT trip_id patterns vary by route/feed, e.g.:
        # - "104250_L..N"
        # - "107000_L..S"
        # - "108550_6..N01R"
        # - "105800_6..S01X014"
        # - "108300_F..N69R"
        #
        # We look for the first occurrence of "..N" or "..S" anywhere in the trip_id.
        idx_n = trip_id.find("..N")
        idx_s = trip_id.find("..S")
        if idx_n != -1 and (idx_s == -1 or idx_n < idx_s):
            direction_letter = "N"
        elif idx_s != -1:
            direction_letter = "S"
        else:
            # Fallback: last char if it's N/S
            if trip_id[-1] in ("N", "S"):
                direction_letter = trip_id[-1]

        if not direction_letter:
            return ""

        per_route = self.subway_terminals.get(route_id.upper(), {})
        return per_route.get(direction_letter, "")

    def _get_feed_path(self, route_id: str, route_type: str = "subway") -> Optional[str]:
        if route_type.lower() == "bus":
            return None
        return self.subway_feed_paths.get(route_id.upper())
    
    def _fetch_subway_feed(self, feed_path: str) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        encoded_path = urllib.parse.quote(feed_path, safe='')
        url = f"{self.subway_base_url}/{encoded_path}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            if "403" in str(e):
                print(f"Error fetching subway feed {feed_path}: 403 Forbidden")
            else:
                print(f"Error fetching subway feed {feed_path}: {e}")
            return None
    
    def _fetch_bus_feed(self) -> Optional[gtfs_realtime_pb2.FeedMessage]:
        if not self.bustime_api_key:
            print("API key required for bus feed but not provided")
            return None
        
        url = f"{self.bus_gtfsrt_base_url}/tripUpdates?key={self.bustime_api_key}"
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            feed = gtfs_realtime_pb2.FeedMessage()
            feed.ParseFromString(response.content)
            return feed
        except Exception as e:
            print(f"Error fetching bus feed: {e}")
            return None

    def _parse_iso8601_to_epoch_seconds(self, value: str) -> Optional[int]:
        if not value:
            return None
        try:
            # Handle "Z" suffix.
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except Exception:
            return None

    def _as_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            # Some SIRI fields can be arrays of strings/dicts.
            return self._as_text(value[0])
        if isinstance(value, dict):
            # Some SIRI fields can be {"$": "text"} or {"value": "..."} depending on producer.
            for key in ("$", "value", "text"):
                if key in value:
                    return self._as_text(value.get(key))
        return str(value)

    def _fetch_bustime_siri_stop_monitoring(self, monitoring_ref: str, line_ref: Optional[str] = None) -> Optional[Dict]:
        if not self.bustime_api_key:
            print("BUSTIME_API_KEY required for SIRI StopMonitoring but not provided")
            return None

        # MTA Bus Time SIRI is exposed as a REST-ish GET interface.
        # Typical endpoint: /api/siri/stop-monitoring.json?key=...&MonitoringRef=...&LineRef=...&MaximumStopVisits=...
        params = {
            "key": self.bustime_api_key,
            "MonitoringRef": monitoring_ref,
            "MaximumStopVisits": "10",
        }
        # We intentionally do NOT pass LineRef here.
        # BusTime LineRef values sometimes don't match what people commonly use (e.g. "M14A" vs "M14A-SBS").
        # We'll fetch all routes at the stop and filter locally with a tolerant matcher.

        url = f"{self.bus_siri_base_url}/stop-monitoring.json"

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching bus SIRI StopMonitoring for {monitoring_ref}: {e}")
            return None

    def _get_siri_visits_count(self, siri_json: Dict) -> int:
        try:
            deliveries = siri_json.get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
            if not deliveries:
                return 0
            visits = deliveries[0].get("MonitoredStopVisit", []) or []
            return len(visits)
        except Exception:
            return 0

    def _fetch_best_bustime_siri_for_stop(self, stop_id: str) -> Dict:
        """
        BusTime stop MonitoringRef sometimes expects "MTA_<stopid>".
        Fetch both forms (when numeric) and return the one with more visits.
        """
        first = self._fetch_bustime_siri_stop_monitoring(monitoring_ref=stop_id, line_ref=None) or {}

        if not str(stop_id).isdigit():
            return first

        prefixed = self._fetch_bustime_siri_stop_monitoring(monitoring_ref=f"MTA_{stop_id}", line_ref=None) or {}
        if self._get_siri_visits_count(prefixed) > self._get_siri_visits_count(first):
            return prefixed
        return first

    def _normalize_bustime_line_ref(self, value: str) -> str:
        """
        Normalize bus LineRef/route_id strings so config values like 'M14A-SBS'
        match BusTime values like 'M14A'.
        """
        v = (value or "").strip().upper()

        # Common BusTime patterns look like:
        # - "M14A"
        # - "M14A-SBS"
        # - "MTA NYCT_M14A+"
        # - "NYCT_M14A+"
        #
        # Strategy:
        # - take last whitespace-separated token
        # - take substring after last "_" (if present)
        # - strip trailing "+" (express/variant marker)
        token = v.split()[-1] if v else ""
        if "_" in token:
            token = token.split("_")[-1]
        token = token.rstrip("+")

        if token.endswith("-SBS"):
            token = token[:-4]

        return token

    def _extract_bus_arrivals_from_siri(
        self,
        siri_json: Dict,
        route_id: str,
        stop_id: str,
        direction: Optional[str],
    ) -> List[Dict]:
        arrivals: List[Dict] = []
        current_time = int(time.time())

        try:
            deliveries = siri_json.get("Siri", {}).get("ServiceDelivery", {}).get("StopMonitoringDelivery", [])
            if not deliveries:
                if self.config.verbose_terminal:
                    print(f"  [BUS DEBUG] No StopMonitoringDelivery in SIRI response for stop {stop_id}")
                return []
            visits = deliveries[0].get("MonitoredStopVisit", []) or []
        except Exception:
            return []

        if self.config.verbose_terminal and not visits:
            print(f"  [BUS DEBUG] SIRI returned 0 MonitoredStopVisit for stop {stop_id}")

        available_line_refs = set()

        for visit in visits:
            mvj = visit.get("MonitoredVehicleJourney", {}) or {}
            line_ref = self._as_text(mvj.get("LineRef"))
            if line_ref:
                available_line_refs.add(self._normalize_bustime_line_ref(line_ref))
            if line_ref and self._normalize_bustime_line_ref(line_ref) != self._normalize_bustime_line_ref(route_id):
                continue

            # NOTE: We intentionally do not filter by DirectionRef for bus StopMonitoring.
            # The stop_id itself is generally direction-specific, and BusTime DirectionRef
            # semantics don't reliably match user expectations of "0/1".

            call = mvj.get("MonitoredCall", {}) or {}
            stop_name = self._as_text(call.get("StopPointName"))
            expected_arrival = self._as_text(call.get("ExpectedArrivalTime"))
            expected_departure = self._as_text(call.get("ExpectedDepartureTime"))
            aimed_arrival = self._as_text(call.get("AimedArrivalTime"))
            aimed_departure = self._as_text(call.get("AimedDepartureTime"))

            epoch = (
                self._parse_iso8601_to_epoch_seconds(expected_arrival)
                or self._parse_iso8601_to_epoch_seconds(expected_departure)
                or self._parse_iso8601_to_epoch_seconds(aimed_arrival)
                or self._parse_iso8601_to_epoch_seconds(aimed_departure)
            )
            if not epoch:
                continue

            minutes_away = (epoch - current_time) // 60
            if minutes_away < 0:
                continue

            destination = self._as_text(mvj.get("DestinationName")) or self._as_text(mvj.get("DestinationRef")) or "Unknown"

            arrivals.append({
                "route": route_id,
                "destination": destination,
                "minutes_away": minutes_away,
                "arrival_time": epoch,
                "type": "bus",
                "stop_name": stop_name,
            })

        arrivals.sort(key=lambda x: x["arrival_time"])
        if self.config.verbose_terminal and not arrivals and visits:
            desired = self._normalize_bustime_line_ref(route_id)
            if available_line_refs and desired not in available_line_refs:
                available = ", ".join(sorted(available_line_refs))
                print(f"  [BUS DEBUG] Stop {stop_id} has routes: {available} (wanted {desired})")
            else:
                print(f"  [BUS DEBUG] Stop {stop_id} had visits but none produced usable times (missing Expected/Aimed times?)")

        return arrivals[:5]
    
    def get_arrivals_for_stop(self, route_id: str, stop_id: str, direction: str = None, route_type: str = "subway") -> List[Dict]:
        # NOTE: This method is kept for single-stop use.
        # For multiple routes/stops, prefer get_arrivals_for_routes() which caches feeds.
        feed: Optional[gtfs_realtime_pb2.FeedMessage]
        if route_type.lower() == "bus":
            if self.bus_api_mode == "siri":
                siri_json = self._fetch_best_bustime_siri_for_stop(stop_id=str(stop_id))
                return self._extract_bus_arrivals_from_siri(siri_json or {}, route_id=route_id, stop_id=stop_id, direction=None)

            feed = self._fetch_bus_feed()
        else:
            feed_path = self._get_feed_path(route_id, route_type)
            if not feed_path:
                return []
            feed = self._fetch_subway_feed(feed_path)

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
                
                # NOTE: Do not filter subway by direction_id (stop_id already encodes direction).
                # Only apply direction_id filtering for GTFS-RT bus mode (if used).
                if route_type.lower() == "bus" and direction is not None and trip.HasField("direction_id") and trip.direction_id != int(direction):
                    continue
                
                for stop_time_update in trip_update.stop_time_update:
                    if stop_time_update.stop_id == stop_id:
                        time_event = None
                        if stop_time_update.HasField("arrival"):
                            time_event = stop_time_update.arrival
                        elif stop_time_update.HasField("departure"):
                            time_event = stop_time_update.departure

                        if time_event and time_event.time:
                            arrival_time = time_event.time
                            minutes_away = (arrival_time - current_time) // 60

                            if minutes_away >= 0:
                                arrivals.append({
                                    "route": route_id,
                    "destination": (
                        self._get_subway_terminal_from_trip_id(route_id=route_id, trip_id=getattr(trip, "trip_id", ""))  # type: ignore[attr-defined]
                        or self._get_trip_display_text(trip)
                    ),
                                    "minutes_away": minutes_away,
                                    "arrival_time": arrival_time,
                                    "type": route_type.lower()
                                })
        
        arrivals.sort(key=lambda x: x["arrival_time"])
        return arrivals[:5]
    
    def get_arrivals_for_routes(self, routes: List[Dict]) -> List[Dict]:
        """
        Fetch and aggregate arrivals for many (route_id, stop_id) pairs.
        This method caches feeds so we don't refetch the same feed repeatedly.
        """
        all_arrivals: List[Dict] = []
        feed_cache: Dict[str, Any] = {}

        for route_config in routes:
            route_id = route_config.get("route_id")
            stop_id = route_config.get("stop_id")
            direction = route_config.get("direction")
            display_name = route_config.get("display_name", route_id)
            route_type = route_config.get("type", "subway").lower()
            stop_name = route_config.get("stop_name")

            if not route_id or not stop_id:
                continue

            if route_type == "bus":
                if self.bus_api_mode == "siri":
                    # Cache by stop + route to avoid multiple HTTP calls per refresh.
                    cache_key = f"bus:siri:{route_id}:{stop_id}"
                    if cache_key not in feed_cache:
                        feed_cache[cache_key] = self._fetch_best_bustime_siri_for_stop(stop_id=str(stop_id))

                    arrivals = self._extract_bus_arrivals_from_siri(
                        siri_json=feed_cache[cache_key],
                        route_id=route_id,
                        stop_id=stop_id,
                        direction=None,
                    )
                    walk_time = int(route_config.get("walk_time", 0))
                    arrivals = [a for a in arrivals if a["minutes_away"] >= walk_time]
                    for arrival in arrivals:
                        arrival["display_name"] = display_name
                        arrival["stop_id"] = stop_id
                        # Config override: if stop_name is provided, always use it (even if SIRI returns StopPointName).
                        if stop_name:
                            arrival["stop_name"] = stop_name
                    all_arrivals.extend(arrivals)
                    continue

                cache_key = "bus:gtfsrt:tripUpdates"
                if cache_key not in feed_cache:
                    feed_cache[cache_key] = self._fetch_bus_feed()
                feed = feed_cache[cache_key]
            else:
                feed_path = self._get_feed_path(route_id, "subway")
                if not feed_path:
                    continue
                cache_key = f"subway:{feed_path}"
                if cache_key not in feed_cache:
                    feed_cache[cache_key] = self._fetch_subway_feed(feed_path)
                feed = feed_cache[cache_key]

            if not feed:
                continue

            arrivals = self._extract_arrivals_from_feed(
                feed=feed,
                route_id=route_id,
                stop_id=stop_id,
                direction=direction,
                route_type=route_type,
            )
            walk_time = int(route_config.get("walk_time", 0))
            arrivals = [a for a in arrivals if a["minutes_away"] >= walk_time]

            for arrival in arrivals:
                arrival["display_name"] = display_name
                arrival["stop_id"] = stop_id
                if stop_name:
                    arrival["stop_name"] = stop_name

            all_arrivals.extend(arrivals)

        all_arrivals.sort(key=lambda x: x["arrival_time"])
        return all_arrivals

    def _extract_arrivals_from_feed(
        self,
        feed: gtfs_realtime_pb2.FeedMessage,
        route_id: str,
        stop_id: str,
        direction: Optional[str],
        route_type: str,
    ) -> List[Dict]:
        arrivals: List[Dict] = []
        current_time = int(time.time())

        for entity in feed.entity:
            if not entity.HasField("trip_update"):
                continue

            trip_update = entity.trip_update
            trip = trip_update.trip

            if trip.route_id.upper() != route_id.upper():
                continue

            # NOTE: On NYCT subway GTFS-RT, direction_id is not consistently reliable across feeds.
            # Since stop_ids already encode direction (e.g. L06N vs L06S), we do not filter by direction_id.
            # NOTE: Do not filter by direction_id for subway feeds; stop_id already encodes direction.

            for stop_time_update in trip_update.stop_time_update:
                if stop_time_update.stop_id != stop_id:
                    continue

                time_event = None
                if stop_time_update.HasField("arrival"):
                    time_event = stop_time_update.arrival
                elif stop_time_update.HasField("departure"):
                    time_event = stop_time_update.departure

                if not time_event or not time_event.time:
                    continue

                arrival_time = time_event.time
                minutes_away = (arrival_time - current_time) // 60
                if minutes_away < 0:
                    continue

                arrivals.append({
                    "route": route_id,
                    "destination": (
                        self._get_subway_terminal_from_trip_id(route_id=route_id, trip_id=getattr(trip, "trip_id", ""))  # type: ignore[attr-defined]
                        or self._get_trip_display_text(trip)
                    ),
                    "minutes_away": minutes_away,
                    "arrival_time": arrival_time,
                    "type": route_type,
                })

        arrivals.sort(key=lambda x: x["arrival_time"])
        return arrivals[:5]

