import streamlit as st
import json
import os
from serpapi.google_search import GoogleSearch
from agno.agent import Agent
from agno.tools.serpapi import SerpApiTools
from agno.models.google import Gemini
from datetime import datetime, timedelta
import re

# API Keys
SERPAPI_KEY = "404a65fa26765c2d5e65d39afa2a809efc09d1bc09dca8fb560e0524a1ed0559"
GOOGLE_API_KEY = "AIzaSyDn3KImU6z28oSqERLS7KjzmQBgP60nh4g"
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY

# Configure page
st.set_page_config(page_title="🌍 Travel Chatbot", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.8rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .bot-message {
        background-color: #f0f2f6;
        border-left: 5px solid #7e57c2;
    }
    .user-message {
        background-color: #e1f5fe;
        border-left: 5px solid #29b6f6;
        text-align: right;
    }
    .bot-icon, .user-icon {
        font-size: 1.5rem;
        margin-bottom: 0.5rem;
    }
    .title {
        text-align: center;
        font-size: 2.5rem;
        font-weight: bold;
        color: #ff5733;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.markdown('<h1 class="title">✈️ AI Travel Assistant</h1>', unsafe_allow_html=True)

# Helper functions
def format_datetime(iso_string):
    try:
        dt = datetime.strptime(iso_string, "%Y-%m-%d %H:%M")
        return dt.strftime("%b-%d, %Y | %I:%M %p")
    except:
        return "N/A"

def fetch_flights(source, destination, departure_date, return_date):
    params = {
        "engine": "google_flights",
        "departure_id": source,
        "arrival_id": destination,
        "outbound_date": str(departure_date),
        "return_date": str(return_date),
        "currency": "INR",
        "hl": "en",
        "api_key": SERPAPI_KEY
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results
    except Exception as e:
        st.error(f"Error fetching flight data: {e}")
        return {}

def extract_cheapest_flights(flight_data, limit=3):
    best_flights = flight_data.get("best_flights", [])
    sorted_flights = sorted(best_flights, key=lambda x: x.get("price", float("inf")))[:limit]
    return sorted_flights

def display_flight_info(flight):
    airline_logo = flight.get("airline_logo", "")
    airline_name = flight.get("airline", "Unknown Airline")
    price = flight.get("price", "Not Available")
    total_duration = flight.get("total_duration", "N/A")
    
    flights_info = flight.get("flights", [{}])
    departure = flights_info[0].get("departure_airport", {})
    arrival = flights_info[-1].get("arrival_airport", {})
    
    departure_time = format_datetime(departure.get("time", "N/A"))
    arrival_time = format_datetime(arrival.get("time", "N/A"))
    
    flight_info = f"""
    **Flight**: {airline_name}
    **Price**: {price}
    **Departure**: {departure_time}
    **Arrival**: {arrival_time}
    **Duration**: {total_duration} minutes
    """
    return flight_info

def extract_airport_code(text):
    # Look for common airport code patterns (3 uppercase letters in parentheses)
    pattern = r'\(([A-Z]{3})\)'
    match = re.search(pattern, text)
    if match:
        return match.group(1)
    return None

def extract_date(text, reference_date=None):
    if not reference_date:
        reference_date = datetime.now()
    
    # Try to identify dates in various formats
    patterns = [
        # DD/MM/YYYY or MM/DD/YYYY
        r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})',
        # Month name formats
        r'(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})',
        # Relative dates
        r'(today|tomorrow|next week|next month)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if match.group(1).lower() == 'today':
                return reference_date.strftime('%Y-%m-%d')
            elif match.group(1).lower() == 'tomorrow':
                return (reference_date + timedelta(days=1)).strftime('%Y-%m-%d')
            elif 'next week' in match.group(1).lower():
                return (reference_date + timedelta(weeks=1)).strftime('%Y-%m-%d')
            elif 'next month' in match.group(1).lower():
                # Simple approximation for next month
                new_month = reference_date.month + 1
                new_year = reference_date.year
                if new_month > 12:
                    new_month = 1
                    new_year += 1
                return datetime(new_year, new_month, reference_date.day).strftime('%Y-%m-%d')
            else:
                # Format properly based on the matched pattern
                try:
                    if len(match.groups()) == 3:
                        if match.group(3).isdigit() and len(match.group(3)) == 4:  # Full year format
                            # Determine if it's DD/MM or MM/DD based on values
                            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                            if month > 12:  # Must be DD/MM format
                                day, month = month, day
                            return f"{year}-{month:02d}-{day:02d}"
                except:
                    pass
    
    # Default to a week from now if no date found
    return (reference_date + timedelta(days=7)).strftime('%Y-%m-%d')

def extract_duration_days(text):
    # Look for patterns like "3 days", "5-day trip", etc.
    patterns = [
        r'(\d+)\s*days',
        r'(\d+)[-\s]day',
        r'for\s+(\d+)\s+days',
        r'stay(?:ing)?\s+for\s+(\d+)\s+days'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    # Default duration if not found
    return 5

def extract_travel_theme(text):
    themes = {
        "couple": "💑 Couple Getaway",
        "romantic": "💑 Couple Getaway",
        "honeymoon": "💑 Couple Getaway",
        "family": "👨‍👩‍👧‍👦 Family Vacation",
        "kids": "👨‍👩‍👧‍👦 Family Vacation",
        "adventure": "🏔️ Adventure Trip",
        "hiking": "🏔️ Adventure Trip",
        "trekking": "🏔️ Adventure Trip",
        "solo": "🧳 Solo Exploration",
        "backpacking": "🧳 Solo Exploration"
    }
    
    text_lower = text.lower()
    for keyword, theme in themes.items():
        if keyword in text_lower:
            return theme
    
    # Default theme
    return "🧳 Solo Exploration"

def extract_budget_preference(text):
    text_lower = text.lower()
    if any(word in text_lower for word in ["luxury", "expensive", "high end", "premium", "5 star"]):
        return "Luxury"
    elif any(word in text_lower for word in ["cheap", "budget", "affordable", "economical", "inexpensive"]):
        return "Economy"
    else:
        return "Standard"

def extract_activities(text):
    activities = []
    activity_keywords = [
        "beach", "hiking", "trekking", "shopping", "food", "cuisine", "history", 
        "museum", "adventure", "relax", "nightlife", "party", "culture", "sightseeing",
        "photography", "wildlife", "nature", "temple", "church", "architecture"
    ]
    
    text_lower = text.lower()
    for activity in activity_keywords:
        if activity in text_lower:
            activities.append(activity)
    
    if not activities:
        activities = ["sightseeing", "relaxing", "local cuisine"]
    
    return ", ".join(activities)

# Initialize AI Agents
def setup_ai_agents():
    researcher = Agent(
        name="Researcher",
        instructions=[
            "Identify the travel destination specified by the user.",
            "Gather detailed information on the destination, including climate, culture, and safety tips.",
            "Find popular attractions, landmarks, and must-visit places.",
            "Search for activities that match the user's interests and travel style.",
            "Prioritize information from reliable sources and official travel guides.",
            "Provide well-structured summaries with key insights and recommendations."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        show_tool_calls=True,
        tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        add_datetime_to_instructions=True,
    )

    planner = Agent(
        name="Planner",
        instructions=[
            "Gather details about the user's travel preferences and budget.",
            "Create a detailed itinerary with scheduled activities and estimated costs.",
            "Ensure the itinerary includes transportation options and travel time estimates.",
            "Optimize the schedule for convenience and enjoyment.",
            "Present the itinerary in a structured format."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        add_datetime_to_instructions=True,
        show_tool_calls=True,
    )

    hotel_restaurant_finder = Agent(
        name="Hotel & Restaurant Finder",
        instructions=[
            "Identify key locations in the user's travel itinerary.",
            "Search for highly rated hotels near those locations.",
            "Search for top-rated restaurants based on cuisine preferences and proximity.",
            "Prioritize results based on user preferences, ratings, and availability.",
            "Provide direct booking links or reservation options where possible."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        show_tool_calls=True,
        add_datetime_to_instructions=True,
    )
    
    return researcher, planner, hotel_restaurant_finder

# Initialize session state variables
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "AI Travel Assistant. Hi! I'm your AI Travel Assistant. Tell me where you'd like to travel, and I'll help plan your trip.)"}
    ]

if 'travel_info' not in st.session_state:
    st.session_state.travel_info = {
        'source': None,
        'destination': None,
        'departure_date': None,
        'return_date': None,
        'num_days': None,
        'travel_theme': None,
        'budget': None,
        'activities': None,
        'collection_stage': 'initial'  # Tracks which info we're collecting
    }

if 'agents' not in st.session_state:
    st.session_state.agents = setup_ai_agents()

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="🧳"):
            st.markdown(message["content"])
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])

# Chat input
def process_user_message():
    # Get the required information based on the collection stage
    info = st.session_state.travel_info
    collection_stage = info['collection_stage']
    
    if collection_stage == 'initial':
        # Try to extract destination from initial message
        destination = extract_airport_code(user_message)
        if destination:
            info['destination'] = destination
            info['collection_stage'] = 'source'
            response = f"Great! I see you want to visit {destination}. Where will you be traveling from? (Please mention the departure city or airport code)"
        else:
            response = "Where would you like to go? Please mention the destination city or airport code"
            info['collection_stage'] = 'destination'
    
    elif collection_stage == 'destination':
        destination = extract_airport_code(user_message) or user_message.strip().upper()
        if len(destination) == 3 and destination.isalpha():
            info['destination'] = destination
            info['collection_stage'] = 'source'
            response = f"Your destination is {destination}. Where will you be traveling from?"
        else:
            response = "Please provide a valid airport code (e.g., DEL for Delhi, BOM for Mumbai)"
    
    elif collection_stage == 'source':
        source = extract_airport_code(user_message) or user_message.strip().upper()
        if len(source) == 3 and source.isalpha():
            info['source'] = source
            info['collection_stage'] = 'dates'
            response = f"Your departure city is {source}. When would you like to travel? Please mention departure and return dates."
        else:
            response = "Please provide a valid airport code (e.g., DEL for Delhi, BOM for Mumbai)"
    
    elif collection_stage == 'dates':
        # Try to extract two dates
        dates = re.findall(r'\d{1,2}[/-]\d{1,2}[/-]\d{4}', user_message)
        today = datetime.now()
        
        if len(dates) >= 2:
            info['departure_date'] = extract_date(dates[0], today)
            info['return_date'] = extract_date(dates[1], today)
        else:
            # If explicit dates not found, extract what we can
            info['departure_date'] = extract_date(user_message, today)
            # Set return date as departure + 7 days by default
            departure_dt = datetime.strptime(info['departure_date'], '%Y-%m-%d')
            info['return_date'] = (departure_dt + timedelta(days=7)).strftime('%Y-%m-%d')
        
        # Calculate duration
        d1 = datetime.strptime(info['departure_date'], '%Y-%m-%d')
        d2 = datetime.strptime(info['return_date'], '%Y-%m-%d')
        info['num_days'] = (d2 - d1).days
        
        info['collection_stage'] = 'duration'
        response = f"Your trip is from {info['departure_date']} to {info['return_date']}. That's a {info['num_days']}-day trip. Is this correct? If yes, please tell me about your travel style (e.g., family, couple, adventure, or solo)"
    
    elif collection_stage == 'duration':
        # Extract travel theme
        info['travel_theme'] = extract_travel_theme(user_message)
        info['collection_stage'] = 'theme'
        response = f"Your travel style: {info['travel_theme']}. Now tell me your budget preference (economy, standard, or luxury)"
    
    elif collection_stage == 'theme':
        # Extract budget
        info['budget'] = extract_budget_preference(user_message)
        info['collection_stage'] = 'budget'
        response = f"Your budget: {info['budget']}. Finally, what kind of activities are you interested in?"
    
    elif collection_stage == 'budget':
        # Extract activities
        info['activities'] = extract_activities(user_message)
        info['collection_stage'] = 'generate_plan'
        response = "Thank you! I'm now generating your travel plan. Please wait..."
        
        # Add a function call to generate the plan
        st.session_state.messages.append({"role": "assistant", "content": response})
        generate_travel_plan()
        return
    
    else:
        # If all information is collected or we're in some other stage
        response = "Would you like to provide any other information? Or how else can I help you?"
    
    # Update session state
    st.session_state.travel_info = info
    st.session_state.messages.append({"role": "assistant", "content": response})

def generate_travel_plan():
    # Extract all collected information
    info = st.session_state.travel_info
    researcher, planner, hotel_restaurant_finder = st.session_state.agents
    
    with st.spinner("🔍 Researching best attractions & activities..."):
        research_prompt = (
            f"Research the best attractions and activities in {info['destination']} for a {info['num_days']}-day {info['travel_theme'].lower()} trip. "
            f"The traveler enjoys: {info['activities']}. Budget: {info['budget']}."
        )
        research_results = researcher.run(research_prompt, stream=False)

    with st.spinner("🏨 Searching for hotels & restaurants..."):
        hotel_restaurant_prompt = (
            f"Find the best hotels and restaurants near popular attractions in {info['destination']} for a {info['travel_theme'].lower()} trip. "
            f"Budget: {info['budget']}. Preferred activities: {info['activities']}."
        )
        hotel_restaurant_results = hotel_restaurant_finder.run(hotel_restaurant_prompt, stream=False)

    with st.spinner("✈️ Fetching best flight options..."):
        flight_data = fetch_flights(info['source'], info['destination'], info['departure_date'], info['return_date'])
        cheapest_flights = extract_cheapest_flights(flight_data)
        
        flight_info_text = "**✈️ Best Flight Options:**\n\n"
        if cheapest_flights:
            for i, flight in enumerate(cheapest_flights[:3], 1):
                flight_info_text += f"**Option {i}:**\n" + display_flight_info(flight) + "\n\n"
        else:
            flight_info_text += "No flight data available at the moment. Please check popular flight booking websites.\n\n"

    with st.spinner("🗺️ Creating your personalized itinerary..."):
        planning_prompt = (
            f"Based on the following data, create a {info['num_days']}-day itinerary for a {info['travel_theme'].lower()} trip to {info['destination']}. "
            f"The traveler enjoys: {info['activities']}. Budget: {info['budget']}. "
            f"Research: {research_results.content}. "
            f"Hotels & Restaurants: {hotel_restaurant_results.content}."
        )
        itinerary = planner.run(planning_prompt, stream=False)
    
    # Compile the final response
    final_response = f"""
## 🎉 Your Travel Plan to {info['destination']} is ready!

### Travel Details:
- **From:** {info['source']} to {info['destination']}
- **Dates:** {info['departure_date']} to {info['return_date']} ({info['num_days']} days)
- **Style:** {info['travel_theme']}
- **Budget:** {info['budget']}

{flight_info_text}

### 🏨 Accommodation & Dining Recommendations:
{hotel_restaurant_results.content}

### 🗓️ Your Itinerary:
{itinerary.content}

---
Hope you like your travel plan! Would you like to know anything else?
    """
    
    # Add the final plan to the messages
    st.session_state.messages.append({"role": "assistant", "content": final_response})
    
    # Reset collection stage for next planning
    info['collection_stage'] = 'initial'
    st.session_state.travel_info = info

# Get user input
user_message = st.chat_input("Tell me about your travel plans...")

if user_message:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_message})
    
    # Display the user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_message)
    
    # Process the message and generate response
    process_user_message()
    
    # Rerun to display the assistant's message
    st.rerun()