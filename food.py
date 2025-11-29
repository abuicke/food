import json
import urllib.request
import urllib.parse
import urllib.error

def geocode_location(location):
    """Convert location name to coordinates using Nominatim API."""
    params = {'q': location, 'format': 'json', 'limit': 1}
    # Headers are required by OSM policy
    headers = {'User-Agent': 'FoodBusinessFinder-Lambda/1.0'}
    
    url = f"https://nominatim.openstreetmap.org/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data:
                return None
            return {
                'lat': float(data[0]['lat']),
                'lon': float(data[0]['lon']),
                'display_name': data[0]['display_name']
            }
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None

def get_food_businesses(lat, lon, radius=1000):
    """Fetch food businesses from OpenStreetMap using Overpass API."""
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Overpass QL query
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|cafe|fast_food|bar|pub|food_court|ice_cream|bistro"](around:{radius},{lat},{lon});
      way["amenity"~"restaurant|cafe|fast_food|bar|pub|food_court|ice_cream|bistro"](around:{radius},{lat},{lon});
      node["shop"~"bakery|butcher|deli|seafood|greengrocer|convenience|supermarket|alcohol|beverages|coffee|confectionery|cheese|chocolate|tea|pastry|spices|organic"](around:{radius},{lat},{lon});
      way["shop"~"bakery|butcher|deli|seafood|greengrocer|convenience|supermarket|alcohol|beverages|coffee|confectionery|cheese|chocolate|tea|pastry|spices|organic"](around:{radius},{lat},{lon});
    );
    out center;
    """
    
    # 1. ENCODING: Overpass expects 'data=' in the body
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    
    # 2. HEADERS: This was the missing piece causing the empty list
    headers = {
        'User-Agent': 'FoodBusinessFinder-Lambda/1.0',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    req = urllib.request.Request(overpass_url, data=data, headers=headers, method='POST')
    
    try:
        # Increase timeout slightly for Overpass
        with urllib.request.urlopen(req, timeout=30) as response:
            if response.status != 200:
                print(f"Overpass API error: Status {response.status}")
                return []
            
            result = json.loads(response.read().decode('utf-8'))
            return result.get('elements', [])
            
    except Exception as e:
        print(f"Error fetching businesses: {e}")
        return []

def format_business(business):
    tags = business.get('tags', {})
    
    # Handle 'ways' (buildings) which have a 'center' lat/lon
    if business.get('type') == 'way':
        lat = business.get('center', {}).get('lat')
        lon = business.get('center', {}).get('lon')
    else:
        lat = business.get('lat')
        lon = business.get('lon')
    
    return {
        'name': tags.get('name', 'Unnamed'),
        'type': tags.get('amenity', tags.get('shop', 'N/A')),
        'cuisine': tags.get('cuisine', 'N/A'),
        'address': tags.get('addr:street', 'N/A'),
        'city': tags.get('addr:city', 'N/A'),
        'lat': lat,
        'lon': lon
    }

def lambda_handler(event, context):
    try:
        # Parse inputs
        query_params = event.get('queryStringParameters') or {}
        location = query_params.get('location')
        radius = query_params.get('radius', 1000)
        
        # Fallback to body
        if not location:
            body = event.get('body', '{}')
            try:
                body_json = json.loads(body) if isinstance(body, str) else body
                location = body_json.get('location')
                radius = body_json.get('radius', radius)
            except:
                pass

        if not location:
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Missing 'location' parameter"})
            }

        # Logic
        coords = geocode_location(location)
        if not coords:
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": f"Could not find location: {location}"})
            }

        businesses = get_food_businesses(coords['lat'], coords['lon'], radius)
        formatted = [format_business(b) for b in businesses]
        
        # Sort by name
        formatted.sort(key=lambda x: x['name'].lower())

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST"
            },
            "body": json.dumps({
                "location": {
                    "query": location,
                    "display_name": coords['display_name'],
                    "coordinates": {'lat': coords['lat'], 'lon': coords['lon']},
                    "radius_meters": radius
                },
                "count": len(formatted),
                "businesses": formatted
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)})
        }