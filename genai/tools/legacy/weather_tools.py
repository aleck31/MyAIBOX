import requests
from strands import tool
from cachetools import TTLCache
from typing import Optional, Dict, Any

# Create TTL cache instances
location_cache = TTLCache(maxsize=100, ttl=86400)  # Cache for 1 day
weather_cache = TTLCache(maxsize=100, ttl=21600)  # Cache for 6 hours

def get_location_coords_with_cache(place: str) -> Dict[str, Any]:
    """Get latitude and longitude for a place name using OpenStreetMap Nominatim"""
    url = "https://nominatim.openstreetmap.org/search"
    headers = {'User-Agent': 'GenAI-Toolbox/1.0'}  # Required by Nominatim ToS
    
    try:
        params = {'q': place, 'format': 'json', 'limit': 1}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not data:
            return {
                "error": f"Location not found: {place}",
                "success": False
            }
            
        return {
            "success": True,
            "latitude": data[0]["lat"],
            "longitude": data[0]["lon"],
            "display_name": data[0]["display_name"]
        }
        
    except requests.RequestException as e:
        return {
            "error": f"Failed to get coordinates: {str(e)}",
            "success": False
        }

def get_weather_with_cache(place: str, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Get weather information for a location, either current or for a specific date
    
    Args:
        place: Location name (e.g., 'London, UK', 'New York City')
        target_date: Optional ISO date string (YYYY-MM-DD). If None, returns current weather
    """
    # First get coordinates
    location = get_location_coords(place)
    if not location.get("success"):
        return location
        
    # Get weather data from Open-Meteo
    url = "https://api.open-meteo.com/v1/forecast"
    try:
        if target_date is None:
            # Get current weather
            params = {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": ["temperature_2m", "relative_humidity_2m", "weather_code", 
                           "wind_speed_10m", "wind_direction_10m", "precipitation"],
                "timezone": "auto"
            }
        else:
            # Get forecast for specific date
            params = {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "daily": ["temperature_2m_max", "temperature_2m_min", "precipitation_probability_max",
                         "weather_code", "wind_speed_10m_max"],
                "timezone": "auto",
                "start_date": target_date,
                "end_date": target_date
            }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Map WMO weather codes to descriptions
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Depositing rime fog",
            51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
            85: "Slight snow showers", 86: "Heavy snow showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
        }
        
        if target_date is None:
            # Return current weather
            current = data["current"]
            weather_desc = weather_codes.get(current["weather_code"], "Unknown")
            
            return {
                "success": True,
                "location": location["display_name"],
                "temperature": {
                    "value": current["temperature_2m"],
                    "unit": "°C"
                },
                "humidity": {
                    "value": current["relative_humidity_2m"],
                    "unit": "%"
                },
                "wind": {
                    "speed": {
                        "value": current["wind_speed_10m"],
                        "unit": "km/h"
                    },
                    "direction": current["wind_direction_10m"]
                },
                "precipitation": {
                    "value": current["precipitation"],
                    "unit": "mm"
                },
                "conditions": weather_desc,
                "timestamp": current["time"]
            }
        else:
            # Return forecast for target day
            daily = data["daily"]
            target_idx = 0  # We requested exactly one day
            
            return {
                "success": True,
                "location": location["display_name"],
                "date": daily["time"][target_idx],
                "temperature": {
                    "max": {
                        "value": daily["temperature_2m_max"][target_idx],
                        "unit": "°C"
                    },
                    "min": {
                        "value": daily["temperature_2m_min"][target_idx],
                        "unit": "°C"
                    }
                },
                "precipitation": {
                    "probability": daily["precipitation_probability_max"][target_idx],
                    "unit": "%"
                },
                "wind": {
                    "speed": {
                        "value": daily["wind_speed_10m_max"][target_idx],
                        "unit": "km/h"
                    }
                },
                "conditions": weather_codes.get(daily["weather_code"][target_idx], "Unknown")
            }
        
    except requests.RequestException as e:
        return {
            "error": f"Failed to get forecast data: {str(e)}",
            "success": False
        }

# Cache wrapper functions
def get_location_coords(place: str) -> Dict[str, Any]:
    """Cached wrapper for get_location_coords_with_cache"""
    if place in location_cache:
        return location_cache[place]
    result = get_location_coords_with_cache(place)
    location_cache[place] = result
    return result

@tool
def get_weather(place: str, target_date: Optional[str] = None) -> Dict[str, Any]:
    """Cached wrapper for get_weather_with_cache"""
    cache_key = f"{place}_{target_date if target_date else 'current'}"
    if cache_key in weather_cache:
        return weather_cache[cache_key]
    result = get_weather_with_cache(place, target_date)
    weather_cache[cache_key] = result
    return result


# Tool specifications in Bedrock format
list_of_tools_specs = [
    {
        "toolSpec": {
            "name": "get_weather",
            "description": "Get weather information for a location, either current weather or forecast for a specific date. Use this for both current conditions and future predictions. Location names must be translated to English.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "place": {
                            "type": "string",
                            "description": "Location name in English (e.g., 'London, UK', 'New York City', 'Tokyo, Japan'). Always use English names for locations, for example use 'Beijing' instead of '北京'."
                        },
                        "target_date": {
                            "type": "string",
                            "description": "Target date in YYYY-MM-DD format (e.g., '2024-12-30'). Leave empty for current weather",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
                        }
                    },
                    "required": ["place"]
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "get_location_coords",
            "description": "Get geographic coordinates for a location. Use this when you need precise latitude/longitude for a place, or to verify/disambiguate location names. This is typically used internally before weather queries to ensure accurate location matching. Location names must be translated to English.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "place": {
                            "type": "string",
                            "description": "Location name in English (e.g., 'London, UK', 'New York City'). Always translate non-English names to English before use."
                        }
                    },
                    "required": ["place"]
                }
            }
        }
    }
]
