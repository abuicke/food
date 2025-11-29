import json
import urllib3
from urllib.parse import urlencode

# Initialize HTTP client
http = urllib3.PoolManager()

def geocode_location(location):
    """Convert location name to coordinates using Nominatim API."""
    params = {
        'q': location,
        'format': 'json',
        'limit': 1
    }
    
    url = f"https://nominatim.openstreetmap.org/search?{urlencode(params)}"
    
    try:
        response = http.request(
            'GET',
            url,
            headers={'User-Agent': 'FoodBusinessFinder-Lambda/1.0'}
        )
        
        data = json.loads(response.data.decode('utf-8'))
        
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
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Overpass QL query for various food-related amenities
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"~"restaurant|cafe|fast_food|bar|pub|food_court|ice_cream|bistro"](around:{radius},{lat},{lon});
      node["shop"~"bakery|butcher|deli|seafood|greengrocer|convenience|supermarket|alcohol|beverages|coffee|confectionery|cheese|chocolate|tea|pastry|spices|organic"](around:{radius},{lat},{lon});
      node["cuisine"](around:{radius},{lat},{lon});
    );
    out body;
    """
    
    try:
        response = http.request(
            'POST',
            overpass_url,
            fields={'data': query},
            timeout=30.0
        )
        
        # Check if response is successful
        if response.status != 200:
            print(f"Overpass API error: Status {response.status}")
            return []
        
        data = json.loads(response.data.decode('utf-8'))
        return data.get('elements', [])
    
    except Exception as e:
        print(f"Error fetching businesses: {e}")
        return []

def format_business(business):
    """Format business information for display."""
    tags = business.get('tags', {})
    
    return {
        'name': tags.get('name', 'Unnamed'),
        'type': tags.get('amenity', tags.get('shop', 'N/A')),
        'cuisine': tags.get('cuisine', 'N/A'),
        'address': tags.get('addr:street', 'N/A'),
        'housenumber': tags.get('addr:housenumber', 'N/A'),
        'city': tags.get('addr:city', 'N/A'),
        'phone': tags.get('phone', 'N/A'),
        'website': tags.get('website', 'N/A'),
        'opening_hours': tags.get('opening_hours', 'N/A'),
        'lat': business.get('lat'),
        'lon': business.get('lon')
    }

def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    
    Expected input via URL query parameters:
    GET /food-businesses?location=Cork%20City&radius=1000
    
    Or via POST body:
    {
        "location": "Cork City",
        "radius": 1000
    }
    
    Returns:
    {
        "statusCode": 200,
        "body": {
            "location": {...},
            "businesses": [...],
            "count": 123
        }
    }
    """
    
    try:
        # Parse input - check query string parameters first, then body
        query_params = event.get('queryStringParameters', {}) or {}
        
        location = query_params.get('location')
        radius = query_params.get('radius', 1000)
        
        # If not in query params, check body
        if not location:
            if isinstance(event.get('body'), str):
                body = json.loads(event['body'])
            else:
                body = event.get('body', event)
            
            location = body.get('location')
            radius = body.get('radius', radius)
        
        if not location:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': 'Missing required parameter: location'
                })
            }
        
        # Validate radius
        try:
            radius = int(radius)
            if radius < 100 or radius > 5000:
                radius = 1000
        except (ValueError, TypeError):
            radius = 1000
        
        # Geocode location
        coords = geocode_location(location)
        
        if not coords:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'error': f'Location not found: {location}'
                })
            }
        
        # Get food businesses
        businesses = get_food_businesses(coords['lat'], coords['lon'], radius)
        
        # Format results
        formatted = [format_business(b) for b in businesses]
        formatted.sort(key=lambda x: x['name'].lower())
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'location': {
                    'query': location,
                    'display_name': coords['display_name'],
                    'coordinates': {
                        'lat': coords['lat'],
                        'lon': coords['lon']
                    },
                    'radius_meters': radius
                },
                'businesses': formatted,
                'count': len(formatted)
            })
        }
    
    except Exception as e:
        print(f"Lambda error: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

# For local testing
if __name__ == "__main__":
    # Test with query parameters
    test_event = {
        "queryStringParameters": {
            "location": "Cork City",
            "radius": "500"
        }
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(json.loads(result['body']), indent=2))