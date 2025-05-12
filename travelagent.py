import streamlit as st
import json
import os
from serpapi.google_search import GoogleSearch
from agno.agent import Agent
from agno.tools.serpapi import SerpApiTools
from agno.models.google import Gemini
from datetime import datetime, timedelta

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

# Initialize AI Agents
def setup_ai_agents():
    # Entity extraction agent specifically for understanding travel details from natural language
    entity_extractor = Agent(
        name="EntityExtractor",
        instructions=[
            "You are an expert at extracting travel-related information from natural language text.",
            "Extract only the specified entity type when requested.",
            "Provide clean, direct responses without explanations.",
            "If information is not found, respond with 'None' only.",
            "For airport codes, return the standard 3-letter IATA code in uppercase.",
            "For dates, return in YYYY-MM-DD format.",
            "For budget levels, categorize as 'Economy', 'Standard', or 'Luxury'.",
            "For travel themes, categorize as 'Family Vacation', 'Couple Getaway', 'Adventure Trip', or 'Solo Exploration'.",
            "For activities, return a comma-separated list of activities mentioned."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        add_datetime_to_instructions=True,
    )

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
    
    return entity_extractor, researcher, planner, hotel_restaurant_finder

# LLM-based entity extraction functions
def extract_airport_code(text, entity_extractor):
    prompt = f"""
    Extract the airport code from the following text: "{text}"
    
    If an explicit airport code is mentioned (like 'DEL', 'BOM', 'JFK'), return that.
    If a city name is mentioned (like 'Delhi', 'Mumbai', 'New York'), return the most common airport code for that city.
    Only return the 3-letter IATA airport code in uppercase, nothing else.
    If no airport or city is mentioned, return None.
    """
    response = entity_extractor.run(prompt, stream=False)
    result = response.content.strip()
    
    # Validate the result - should be a 3-letter code
    if result and result != "None" and len(result) == 3 and result.isalpha():
        return result.upper()
    return None

def extract_travel_dates(text, entity_extractor):
    prompt = f"""
    Extract the departure date and return date from the following text: "{text}"
    
    Format the dates as YYYY-MM-DD.
    If only one date is mentioned, assume it's the departure date.
    If no dates are mentioned, return "None" for both.
    Return in this format: departure_date, return_date
    """
    response = entity_extractor.run(prompt, stream=False)
    result = response.content.strip()
    
    try:
        departure_date, return_date = result.split(",")
        departure_date = departure_date.strip()
        return_date = return_date.strip()
        
        # Validate dates
        if departure_date == "None":
            # Default to a week from now
            departure_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        if return_date == "None":
            # Default to two weeks from now
            return_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
            
        return departure_date, return_date
    except:
        # Default dates if extraction fails
        departure_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        return_date = (datetime.now() + timedelta(days=14)).strftime('%Y-%m-%d')
        return departure_date, return_date

def extract_travel_theme(text, entity_extractor):
    prompt = f"""
    Extract the travel theme or style from the following text: "{text}"
    
    Categorize into exactly one of these categories:
    - Family Vacation
    - Couple Getaway
    - Adventure Trip
    - Solo Exploration
    
    Return only the category name, nothing else.
    """
    response = entity_extractor.run(prompt, stream=False)
    result = response.content.strip()
    
    # Add emoji to the theme
    theme_emojis = {
        "Family Vacation": "👨‍👩‍👧‍👦 Family Vacation",
        "Couple Getaway": "💑 Couple Getaway",
        "Adventure Trip": "🏔️ Adventure Trip",
        "Solo Exploration": "🧳 Solo Exploration"
    }
    
    return theme_emojis.get(result, "🧳 Solo Exploration")

def extract_budget_preference(text, entity_extractor):
    prompt = f"""
    Extract the budget preference from the following text: "{text}"
    
    Categorize into exactly one of these categories:
    - Economy (budget-friendly, cheap, affordable)
    - Standard (moderate, mid-range)
    - Luxury (high-end, premium, expensive)
    
    Return only the category name (Economy, Standard, or Luxury), nothing else.
    """
    response = entity_extractor.run(prompt, stream=False)
    return response.content.strip()

def extract_activities(text, entity_extractor):
    prompt = f"""
    Extract the activities or interests mentioned in the following text: "{text}"
    
    Return a comma-separated list of activities.
    Common travel activities include: beach, hiking, trekking, shopping, food/cuisine, history, 
    museums, adventure, relaxation, nightlife, culture, sightseeing, photography, wildlife, 
    nature, temples, architecture, etc.
    
    If no specific activities are mentioned, return "sightseeing, local cuisine, relaxation"
    """
    response = entity_extractor.run(prompt, stream=False)
    return response.content.strip()

# Initialize session state variables
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi! I'm your AI Travel Assistant. Tell me where you'd like to travel, and I'll help plan your trip."}
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
    entity_extractor, _, _, _ = st.session_state.agents
    
    if collection_stage == 'initial':
        # Try to extract destination from initial message
        destination = extract_airport_code(user_message, entity_extractor)
        if destination:
            info['destination'] = destination
            info['collection_stage'] = 'source'
            response = f"Great! I see you want to visit {destination}. Where will you be traveling from? (Please mention the departure city or airport)"
        else:
            response = "Where would you like to go? Please mention the destination city or airport"
            info['collection_stage'] = 'destination'
    
    elif collection_stage == 'destination':
        destination = extract_airport_code(user_message, entity_extractor)
        if destination:
            info['destination'] = destination
            info['collection_stage'] = 'source'
            response = f"Your destination is {destination}. Where will you be traveling from?"
        else:
            response = "I couldn't identify a valid destination. Please mention a city or airport code clearly (e.g., 'Delhi' or 'DEL')"
    
    elif collection_stage == 'source':
        source = extract_airport_code(user_message, entity_extractor)
        if source:
            info['source'] = source
            info['collection_stage'] = 'dates'
            response = f"Your departure city is {source}. When would you like to travel? Please mention departure and return dates."
        else:
            response = "I couldn't identify a valid source location. Please mention a city or airport code clearly (e.g., 'Delhi' or 'DEL')"
    
    elif collection_stage == 'dates':
        # Try to extract two dates using LLM
        departure_date, return_date = extract_travel_dates(user_message, entity_extractor)
        
        info['departure_date'] = departure_date
        info['return_date'] = return_date
        
        # Calculate duration
        try:
            d1 = datetime.strptime(info['departure_date'], '%Y-%m-%d')
            d2 = datetime.strptime(info['return_date'], '%Y-%m-%d')
            info['num_days'] = (d2 - d1).days
        except:
            # Fallback if date parsing fails
            info['num_days'] = 7
        
        info['collection_stage'] = 'duration'
        response = f"Your trip is from {info['departure_date']} to {info['return_date']}. That's a {info['num_days']}-day trip. Is this correct? If yes, please tell me about your travel style (e.g., family, couple, adventure, or solo)"
    
    elif collection_stage == 'duration':
        # Extract travel theme using LLM
        info['travel_theme'] = extract_travel_theme(user_message, entity_extractor)
        info['collection_stage'] = 'theme'
        response = f"Your travel style: {info['travel_theme']}. Now tell me your budget preference (economy, standard, or luxury)"
    
    elif collection_stage == 'theme':
        # Extract budget using LLM
        info['budget'] = extract_budget_preference(user_message, entity_extractor)
        info['collection_stage'] = 'budget'
        response = f"Your budget: {info['budget']}. Finally, what kind of activities are you interested in?"
    
    elif collection_stage == 'budget':
        # Extract activities using LLM
        info['activities'] = extract_activities(user_message, entity_extractor)
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
    _, researcher, planner, hotel_restaurant_finder = st.session_state.agents
    
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