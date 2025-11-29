import requests
import json

def geocode_location(location):
    """Convert location name to coordinates using Nominatim API."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': location,
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'FoodBusinessFinder/1.0'
    }
    
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    
    if not data:
        return None
    
    return {
        'lat': float(data[0]['lat']),
        'lon': float(data[0]['lon']),
        'display_name': data[0]['display_name']
    }

def get_food_businesses(lat, lon, radius=1000):
    """Fetch food businesses from OpenStreetMap using Overpass API."""
    overpass_url = "http://overpass-api.de/api/interpreter"
    
    # Overpass QL query for various food-related amenities
    query = f"""
    [out:json];
    (
      node["amenity"~"restaurant|cafe|fast_food|bar|pub|food_court|ice_cream|bistro"](around:{radius},{lat},{lon});
      node["shop"~"bakery|butcher|deli|seafood|greengrocer|convenience|supermarket|alcohol|beverages|coffee|confectionery|cheese|chocolate|tea|pastry|spices|organic"](around:{radius},{lat},{lon});
      node["cuisine"](around:{radius},{lat},{lon});
    );
    out body;
    """
    
    try:
        response = requests.get(overpass_url, params={'data': query}, timeout=30)
        response.raise_for_status()
        
        # Check if response is actually JSON
        content_type = response.headers.get('content-type', '')
        if 'json' not in content_type:
            print(f"Warning: Unexpected content type: {content_type}")
            print(f"Response text: {response.text[:200]}")
            return []
        
        data = response.json()
        return data.get('elements', [])
    
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Response text: {response.text[:500]}")
        return []

def format_business(business):
    """Format business information for display."""
    tags = business.get('tags', {})
    name = tags.get('name', 'Unnamed')
    amenity = tags.get('amenity', tags.get('shop', 'N/A'))
    cuisine = tags.get('cuisine', 'N/A')
    address = tags.get('addr:street', 'N/A')
    phone = tags.get('phone', 'N/A')
    
    return {
        'name': name,
        'type': amenity,
        'cuisine': cuisine,
        'address': address,
        'phone': phone,
        'lat': business.get('lat'),
        'lon': business.get('lon')
    }

def main():
    print("=" * 60)
    print("Food Business Finder")
    print("=" * 60)
    
    location = input("\nEnter a location (city, address, or place name): ").strip()
    
    if not location:
        print("No location provided. Exiting.")
        return
    
    print(f"\nGeocoding '{location}'...")
    coords = geocode_location(location)
    
    if not coords:
        print("Location not found. Please try a different search term.")
        return
    
    print(f"Found: {coords['display_name']}")
    print(f"Coordinates: {coords['lat']}, {coords['lon']}")
    
    radius = input("\nEnter search radius in meters (default 1000): ").strip()
    radius = int(radius) if radius.isdigit() else 1000
    
    print(f"\nSearching for food businesses within {radius}m...")
    businesses = get_food_businesses(coords['lat'], coords['lon'], radius)
    
    if not businesses:
        print("No food businesses found in this area.")
        return
    
    print(f"\nFound {len(businesses)} food-related businesses:\n")
    print("=" * 60)
    
    formatted = [format_business(b) for b in businesses]
    formatted.sort(key=lambda x: x['name'])
    
    for i, biz in enumerate(formatted, 1):
        print(f"\n{i}. {biz['name']}")
        print(f"   Type: {biz['type']}")
        if biz['cuisine'] != 'N/A':
            print(f"   Cuisine: {biz['cuisine']}")
        if biz['address'] != 'N/A':
            print(f"   Address: {biz['address']}")
        if biz['phone'] != 'N/A':
            print(f"   Phone: {biz['phone']}")
    
    print("\n" + "=" * 60)
    print(f"Total: {len(businesses)} businesses")
    
    # Ask if user wants to save results
    save = input("\nSave results to JSON file? (y/n): ").strip().lower()
    if save == 'y':
        filename = f"food_businesses_{location.replace(' ', '_')}.json"
        with open(filename, 'w') as f:
            json.dump(formatted, f, indent=2)
        print(f"Results saved to {filename}")

if __name__ == "__main__":
    main()