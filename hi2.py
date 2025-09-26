import random
import datetime
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import math

# -------------------
#  App Initialization
# -------------------
app = FastAPI(
    title="Safe Route API",
    description="API for suggesting safe travel routes in Bangladesh based on crime data.",
    version="1.0.0"
)

# Configure CORS to allow the front-end to communicate with this backend
origins = [
    "http://localhost",
    "http://localhost:8080",
    "null", # Allows opening the HTML file directly
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------
#  Pydantic Models (Data Validation)
# -------------------
class RouteRequest(BaseModel):
    start_lat: float
    start_lon: float
    destination: str
    age: int
    gender: str
    visit_time: str # e.g., "22:48"

# -------------------
#  Mock Database & Logic
# -------------------
# This data simulates what you would query from your database.
mock_incidents = []
crime_types = {
    "Theft": {"severity": 2, "description": "Minor property crime."},
    "Robbery": {"severity": 5, "description": "Theft involving force."},
    "Assault": {"severity": 7, "description": "Physical harm or threat."},
    "Harassment": {"severity": 4, "description": "Unwanted and intimidating behavior."}
}

for _ in range(300):
    lat = 23.8103 + (random.random() - 0.5) * 0.2
    lon = 90.4125 + (random.random() - 0.5) * 0.2
    mock_incidents.append({
        "location": [lat, lon],
        "crime_type": random.choice(list(crime_types.keys())),
        "victim_gender": random.choice(["Female", "Male", "Any"]),
        "time_of_day": random.choice(["day", "night"]),
    })

def calculate_risk_score(route_points: List[List[float]], gender: str, time_of_day: str) -> int:
    risk_score = 0
    proximity_threshold = 0.005 # about 500 meters
    for point in route_points:
        for incident in mock_incidents:
            dist = math.sqrt((point[0] - incident['location'][0])**2 + (point[1] - incident['location'][1])**2)
            if dist < proximity_threshold:
                incident_risk = crime_types[incident['crime_type']]['severity']
                if incident['time_of_day'] == time_of_day:
                    incident_risk *= 1.5
                if incident['victim_gender'] == gender or incident['victim_gender'] == "Any":
                    incident_risk *= 1.5
                risk_score += incident_risk
    return int(risk_score)

def generate_road_route(start_coords, end_coords, num_points=15):
    route = [start_coords]
    lat_diff = end_coords[0] - start_coords[0]
    lon_diff = end_coords[1] - start_coords[1]
    for i in range(1, num_points):
        fraction = i / num_points
        mid_lat = start_coords[0] + lat_diff * fraction
        mid_lon = start_coords[1] + lon_diff * fraction
        offset_lat = (random.random() - 0.5) * 0.008 * math.sin(fraction * math.pi)
        offset_lon = (random.random() - 0.5) * 0.008 * math.sin(fraction * math.pi)
        route.append([mid_lat + offset_lat, mid_lon + offset_lon])
    route.append(end_coords)
    return route

# -------------------
#  API Endpoint
# -------------------
@app.post("/suggest-route")
async def suggest_route(request: RouteRequest):
    # 1. Determine the context from the request
    try:
        # Parse the hour from the "HH:MM" time string
        request_hour = int(request.visit_time.split(':')[0])
    except (ValueError, IndexError):
        # Fallback to current server time if the format is invalid
        request_hour = datetime.datetime.now().hour
        
    time_of_day = "night" if (request_hour >= 19 or request_hour < 6) else "day"
    start_point = [request.start_lat, request.start_lon]

    # 2. Define two potential routes to evaluate
    route_options = {
        "direct_route": {
            "name": "Direct Route via Mohakhali",
            "end_point": [23.785, 90.408],
            "eta": f"{random.randint(15, 25)} min",
            "details": "Most direct path, may pass through congested or high-risk areas."
        },
        "safer_route": {
            "name": "Alternative via Hatirjheel",
            "end_point": [23.753, 90.392],
            "eta": f"{random.randint(25, 35)} min",
            "details": "Longer route that uses major, well-lit roads, avoiding some risk zones."
        }
    }

    # 3. Generate path coordinates and calculate risk for each option
    for key, route_info in route_options.items():
        route_info["coords"] = generate_road_route(start_point, route_info["end_point"])
        route_info["risk_score"] = calculate_risk_score(route_info["coords"], request.gender, time_of_day)

    # 4. Choose the best route (lowest risk score)
    best_route_key = min(route_options, key=lambda k: route_options[k]['risk_score'])
    chosen_route = route_options[best_route_key]
    
    # 5. Classify the final risk level for the UI
    risk_score = chosen_route['risk_score']
    if risk_score < 150:
        risk_level, risk_color = "Safe", "green"
        theme = {"bg": "bg-green-100 dark:bg-green-900/50", "border": "border-green-500", "text": "text-green-800"}
    elif risk_score < 300:
        risk_level, risk_color = "Moderate Risk", "yellow"
        theme = {"bg": "bg-yellow-100 dark:bg-yellow-900/50", "border": "border-yellow-500", "text": "text-yellow-800"}
    else:
        risk_level, risk_color = "High Risk", "red"
        theme = {"bg": "bg-red-100 dark:bg-red-900/50", "border": "border-red-500", "text": "text-red-800"}

    # 6. Generate the heatmap data, weighted by the current context
    heatmap_points = []
    for incident in mock_incidents:
        intensity = 0.5
        if incident['time_of_day'] == time_of_day:
            intensity += 0.3
        if incident['victim_gender'] == request.gender or incident['victim_gender'] == "Any":
            intensity += 0.3
        heatmap_points.append([incident['location'][0], incident['location'][1], intensity])

    # 7. Return the final data package to the front-end
    return {
        "route": {
            "name": chosen_route['name'],
            "risk": risk_level,
            "risk_color": risk_color,
            "eta": chosen_route['eta'],
            "details": chosen_route['details'],
            "theme": theme,
        },
        "heatmap": heatmap_points,
        "route_coords": chosen_route['coords'],
    }


# uvicorn main:app --reload
