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
    # Conversation Manager Agent
    conversation_manager = Agent(
        name="ConversationManager",
        instructions=[
            "You are an AI travel assistant that helps users plan trips in a natural, conversational way.",
            "Your goal is to collect all necessary information to plan a trip while maintaining a friendly conversation.",
            "Understand context across multiple messages and remember what the user has already told you.",
            "Extract travel information naturally without making the user feel like they're filling out a form.",
            "If the user changes topics temporarily, engage with them, then gently guide them back to the trip planning.",
            "The required information for planning a trip includes: source location, destination, travel dates, travel style/theme, budget, and activities.",
            "Respond directly to what the user is saying while advancing the conversation toward collecting all necessary information.",
            "If there are contradictions in the information provided, ask for clarification.",
            "Present responses in a helpful, warm tone that feels like talking to a knowledgeable friend.",
            "Track conversation state and identify what information is still needed."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        add_datetime_to_instructions=True,
    )
    
    # Entity Extraction Agent
    entity_extractor = Agent(
        name="EntityExtractor",
        instructions=[
            "You are a specialized entity extraction system for travel information.",
            "Extract specific travel details from user messages when requested.",
            "Analyze the travel conversation context to identify relevant information.",
            "Return only the requested information in the specified format.",
            "For ambiguous information, provide the most likely interpretation based on context.",
            "If specific information is not present, return 'Unknown'.",
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        add_datetime_to_instructions=True,
    )

    # Travel Research Agent
    researcher = Agent(
        name="Researcher",
        instructions=[
            "Research travel destinations to provide accurate and helpful information.",
            "Focus on attractions, activities, cultural insights, and practical travel tips.",
            "Prioritize information relevant to the user's stated preferences and interests.",
            "Provide well-structured, concise summaries of destination highlights.",
            "Include practical information like best times to visit, local customs, and safety tips."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        show_tool_calls=True,
        tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        add_datetime_to_instructions=True,
    )

    # Itinerary Planning Agent
    planner = Agent(
        name="Planner",
        instructions=[
            "Create personalized travel itineraries based on user preferences and destination research.",
            "Optimize schedules to minimize travel time and maximize enjoyment.",
            "Balance structured activities with free time for exploration.",
            "Consider practical aspects like opening hours, travel distances, and local transportation.",
            "Create day-by-day plans with estimated timings and alternative options.",
            "Adapt recommendations based on travel style (family, couple, solo, adventure)."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        add_datetime_to_instructions=True,
        show_tool_calls=True,
    )

    # Hotel & Restaurant Recommendations Agent
    hotel_restaurant_finder = Agent(
        name="HotelRestaurantFinder",
        instructions=[
            "Find accommodation and dining options that match user preferences and budget.",
            "Recommend hotels in convenient locations for the planned activities.",
            "Suggest restaurants featuring local cuisine and specialties.",
            "Consider special requirements like family-friendly options or romantic settings.",
            "Provide a mix of popular establishments and hidden gems.",
            "Include practical information like price ranges and reservation recommendations."
        ],
        model=Gemini(id="gemini-2.0-flash-exp"),
        tools=[SerpApiTools(api_key=SERPAPI_KEY)],
        show_tool_calls=True,
        add_datetime_to_instructions=True,
    )
    
    return conversation_manager, entity_extractor, researcher, planner, hotel_restaurant_finder

# Initialize session state variables
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi there! I'm your AI Travel Assistant. Whether you're planning a quick getaway or an extended vacation, I'm here to help. Just tell me a bit about what kind of trip you're thinking about, and we can start planning together!"}
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
        'planning_stage': 'initial',  # Now tracks the overall planning stage, not just info collection
        'ready_to_generate': False,    # Flag for when we have enough info to generate a plan
        'plan_generated': False        # Flag to track if we've already generated a plan
    }

if 'agents' not in st.session_state:
    st.session_state.agents = setup_ai_agents()

if 'conversation_history' not in st.session_state:
    st.session_state.conversation_history = ""

# Display chat messages
for message in st.session_state.messages:
    if message["role"] == "assistant":
        with st.chat_message("assistant", avatar="🧳"):
            st.markdown(message["content"])
    else:
        with st.chat_message("user", avatar="👤"):
            st.markdown(message["content"])

# Extract travel information from conversation
def extract_travel_info(conversation_history, entity_extractor):
    prompt = f"""
    Analyze the following conversation history between a user and a travel assistant:
    
    {conversation_history}
    
    Extract the following travel information as a JSON object:
    {{
        "source": "The departure airport code or city name",
        "destination": "The destination airport code or city name",
        "departure_date": "The departure date in YYYY-MM-DD format",
        "return_date": "The return date in YYYY-MM-DD format",
        "travel_theme": "One of: Family Vacation, Couple Getaway, Adventure Trip, Solo Exploration",
        "budget": "One of: Economy, Standard, Luxury",
        "activities": "Comma-separated list of activities mentioned"
    }}
    
    For any field where information is not available, use null.
    Include only the JSON object in your response, nothing else.
    """
    
    response = entity_extractor.run(prompt, stream=False)
    try:
        # Clean up the response to handle potential formatting issues
        response_text = response.content.strip()
        # Remove any backticks or "json" text that might be included
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        extracted_info = json.loads(response_text.strip())
        return extracted_info
    except Exception as e:
        st.error(f"Error parsing extracted information: {e}")
        return {}

# Determine what information is still needed
def get_missing_info(travel_info):
    essential_fields = {
        'source': "departure city or airport",
        'destination': "destination",
        'departure_date': "departure date",
        'return_date': "return date", 
        'travel_theme': "travel style (family, couple, adventure, or solo)",
        'budget': "budget preference (economy, standard, or luxury)",
        'activities': "activities you're interested in"
    }
    
    missing = {}
    for field, name in essential_fields.items():
        if travel_info.get(field) is None or travel_info.get(field) == "null" or travel_info.get(field) == "":
            missing[field] = name
    
    return missing

# Generate next conversation prompt
def generate_conversation_prompt(user_message, conversation_history, travel_info):
    conversation_manager = st.session_state.agents[0]
    
    # Update conversation history with the new message
    updated_history = f"{conversation_history}\nUser: {user_message}"
    
    # Check for missing information
    missing_info = get_missing_info(travel_info)
    missing_fields_list = list(missing_info.values())
    
    if travel_info.get('planning_stage') == 'initial' and travel_info.get('destination') is not None:
        # We have a destination, move to information gathering
        travel_info['planning_stage'] = 'gathering_info'
    
    if travel_info.get('planning_stage') == 'gathering_info' and len(missing_fields_list) == 0:
        # We have all needed information, move to confirmation
        travel_info['planning_stage'] = 'confirmation'
        travel_info['ready_to_generate'] = True
    
    # Prepare context about the current state of the planning process
    planning_context = f"""
    Current planning stage: {travel_info.get('planning_stage', 'initial')}
    
    Information we already have:
    """
    
    # Add information we already have
    for field, name in {'source': "Departure", 'destination': "Destination", 
                        'departure_date': "Departure date", 'return_date': "Return date",
                        'travel_theme': "Travel style", 'budget': "Budget", 
                        'activities': "Activities"}.items():
        value = travel_info.get(field)
        if value and value != "null" and value != "":
            planning_context += f"- {name}: {value}\n"
    
    planning_context += "\nMissing information we need to collect:\n"
    
    # Add information we still need
    if missing_fields_list:
        for field in missing_fields_list:
            planning_context += f"- {field}\n"
    else:
        planning_context += "- None (all essential information collected)\n"
    
    # Create the prompt for the conversation manager
    if travel_info.get('planning_stage') == 'initial':
        prompt = f"""
        {planning_context}
        
        Based on the conversation history and current planning stage, respond to the user in a natural, conversational way.
        If the user hasn't mentioned a destination yet, gently ask them where they'd like to go.
        If they've mentioned a destination but we don't have enough details, ask follow-up questions to collect missing information.
        Avoid asking all questions at once - focus on 1-2 missing pieces of information at a time.
        
        Conversation history:
        {updated_history}
        
        Your response:
        """
    elif travel_info.get('planning_stage') == 'gathering_info':
        prompt = f"""
        {planning_context}
        
        Based on the conversation history and current planning stage, respond to the user in a natural, conversational way.
        Focus on collecting 1-2 pieces of missing information at a time, while still being responsive to the user's message.
        If the user asks questions or changes the subject, answer them naturally, then gently guide them back to the planning process.
        
        Conversation history:
        {updated_history}
        
        Your response:
        """
    elif travel_info.get('planning_stage') == 'confirmation':
        prompt = f"""
        {planning_context}
        
        We have all the essential information for planning. Based on the conversation history:
        1. Briefly summarize the travel plan details we've collected.
        2. Ask if the user wants to generate a detailed travel plan.
        3. If there's anything they want to change before generating the plan, they can let you know.
        
        Conversation history:
        {updated_history}
        
        Your response:
        """
    elif travel_info.get('planning_stage') == 'post_plan':
        prompt = f"""
        {planning_context}
        
        The travel plan has been generated. Respond to any follow-up questions the user might have about their trip.
        If they express interest in a new trip or making significant changes to this one, suggest starting a new plan.
        Be helpful with any travel-related questions they might have.
        
        Conversation history:
        {updated_history}
        
        Your response:
        """
    
    response = conversation_manager.run(prompt, stream=False)
    return response.content, updated_history

# Process user message and update travel info
def process_user_message(user_message):
    # Add user message to conversation history
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = f"User: {user_message}"
    else:
        st.session_state.conversation_history += f"\nUser: {user_message}"
    
    # Extract travel information
    entity_extractor = st.session_state.agents[1]
    extracted_info = extract_travel_info(st.session_state.conversation_history, entity_extractor)
    
    # Update travel info with extracted info
    for key, value in extracted_info.items():
        if value and value != "null" and value != "Unknown":
            st.session_state.travel_info[key] = value
    
    # Calculate duration if we have both dates
    if st.session_state.travel_info['departure_date'] and st.session_state.travel_info['return_date']:
        try:
            d1 = datetime.strptime(st.session_state.travel_info['departure_date'], '%Y-%m-%d')
            d2 = datetime.strptime(st.session_state.travel_info['return_date'], '%Y-%m-%d')
            st.session_state.travel_info['num_days'] = (d2 - d1).days
        except:
            st.session_state.travel_info['num_days'] = 7  # Default
    
    # Generate response
    response, updated_history = generate_conversation_prompt(
        user_message, 
        st.session_state.conversation_history, 
        st.session_state.travel_info
    )
    
    # Update conversation history with assistant's response
    st.session_state.conversation_history = updated_history + f"\nAssistant: {response}"
    
    # Check if we should generate a travel plan
    ready_to_generate = st.session_state.travel_info['ready_to_generate']
    plan_mentioned = any(phrase in user_message.lower() for phrase in [
        "plan", "itinerary", "schedule", "generate", "create", "show me", "let's go", "sounds good", "yes", "proceed"
    ])
    
    if ready_to_generate and plan_mentioned and not st.session_state.travel_info['plan_generated']:
        # If we have all necessary info and user has indicated they want to proceed
        st.session_state.messages.append({"role": "assistant", "content": response})
        generate_travel_plan()
        st.session_state.travel_info['plan_generated'] = True
        st.session_state.travel_info['planning_stage'] = 'post_plan'
    else:
        # Just return the conversational response
        st.session_state.messages.append({"role": "assistant", "content": response})

def generate_travel_plan():
    # Extract all collected information
    info = st.session_state.travel_info
    _, _, researcher, planner, hotel_restaurant_finder = st.session_state.agents
    
    # Add emoji to the theme if not already present
    theme_emojis = {
        "Family Vacation": "👨‍👩‍👧‍👦 Family Vacation",
        "Couple Getaway": "💑 Couple Getaway",
        "Adventure Trip": "🏔️ Adventure Trip",
        "Solo Exploration": "🧳 Solo Exploration"
    }
    
    display_theme = info['travel_theme']
    for key, value in theme_emojis.items():
        if key in info['travel_theme'] and not any(emoji in info['travel_theme'] for emoji in ["👨‍👩‍👧‍👦", "💑", "🏔️", "🧳"]):
            display_theme = value
            break
    
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
- **Style:** {display_theme}
- **Budget:** {info['budget']}

{flight_info_text}

### 🏨 Accommodation & Dining Recommendations:
{hotel_restaurant_results.content}

### 🗓️ Your Itinerary:
{itinerary.content}

---
I hope you like your travel plan! Is there anything specific about the itinerary you'd like me to explain or modify?
    """
    
    # Add the final plan to the messages
    st.session_state.messages.append({"role": "assistant", "content": final_response})

# Handle user reset request
def handle_reset_request(user_message):
    reset_keywords = ["start over", "reset", "start again", "new trip", "different trip", "new plan"]
    return any(keyword in user_message.lower() for keyword in reset_keywords)

# Get user input
user_message = st.chat_input("Chat with your Travel Assistant...")

if user_message:
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": user_message})
    
    # Display the user message
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_message)
    
    # Check if user wants to reset the conversation
    if handle_reset_request(user_message):
        # Reset the travel info but keep the conversation history
        st.session_state.travel_info = {
            'source': None,
            'destination': None,
            'departure_date': None,
            'return_date': None,
            'num_days': None,
            'travel_theme': None,
            'budget': None,
            'activities': None,
            'planning_stage': 'initial',
            'ready_to_generate': False,
            'plan_generated': False
        }
        reset_confirmation = "I've reset your trip planning. Let's start fresh! Where would you like to go?"
        st.session_state.messages.append({"role": "assistant", "content": reset_confirmation})
        st.session_state.conversation_history += f"\nUser: {user_message}\nAssistant: {reset_confirmation}"
    else:
        # Process the message normally
        process_user_message(user_message)
    
    # Rerun to display the assistant's message
    st.rerun()