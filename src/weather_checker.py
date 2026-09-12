import os
import requests
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config', '.env')
load_dotenv(env_path)

def get_weather_summary(location):
    api_key = os.getenv('ACCU_API_KEY')
    if not api_key:
        return "API key not found. Check your .env file and ACCU_API_KEY variable."
    
    url = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={api_key}&q={location}"
    resp = requests.get(url)
    try:
        locs = resp.json()
    except Exception as e:
        return f"Error decoding JSON: {e}"

    if not isinstance(locs, list) or not locs:
        return "Weather information unavailable (location lookup failed)."
    if 'Key' not in locs[0]:
        return "Weather information unavailable (no Key found, possible API error)."

    location_key = locs[0]['Key']
    current_cond_url = f"http://dataservice.accuweather.com/currentconditions/v1/{location_key}?apikey={api_key}&details=true"
    resp = requests.get(current_cond_url)
    try:
        cond = resp.json()
    except Exception as e:
        return f"Error decoding condition JSON: {e}"

    if not isinstance(cond, list) or len(cond) == 0 or 'WeatherText' not in cond[0]:
        return "Weather information unavailable (condition response problematic)."

    data = cond[0]
    summary = f"Weather at {location}: {data['WeatherText']}, Temp: {data['Temperature']['Metric']['Value']}°C."
    return summary

# --- Testing block ---
if __name__ == "__main__":
    print(get_weather_summary("Surat"))
    print(get_weather_summary("Delhi"))
    print(get_weather_summary("Frankfurt"))
