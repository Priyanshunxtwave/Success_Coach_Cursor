import streamlit as st
import json
import os
import datetime
from openai import OpenAI
from dotenv import load_dotenv

# --- GOOGLE SHEETS IMPORTS ---
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from google.oauth2 import service_account
# Load environment variables
load_dotenv()
client = OpenAI()

# ==========================================
# 1. GOOGLE SHEETS DATABASE TOOLS
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SPREADSHEET_ID = os.getenv('GOOGLE_SPREADSHEET_ID')


load_dotenv()

def get_google_creds():
    try:
        # Try to pull from Streamlit Cloud Secrets first
        if "gcp_service_account" in st.secrets:
            return service_account.Credentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]),
                scopes=SCOPES
            )
    except Exception:
        pass # Ignore the error if st.secrets doesn't exist locally
        
    # Fallback for local development
    return service_account.Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES
    )

def get_spreadsheet_id():
    try:
        # Try to pull from Streamlit Cloud Secrets first
        if "GOOGLE_SPREADSHEET_ID" in st.secrets:
            return st.secrets["GOOGLE_SPREADSHEET_ID"]
    except Exception:
        pass # Ignore the error if st.secrets doesn't exist locally
        
    # Fallback for local development
    return os.getenv("GOOGLE_SPREADSHEET_ID")


SPREADSHEET_ID = get_spreadsheet_id()

def get_sheets_service():
    creds = get_google_creds()
    return build("sheets", "v4", credentials=creds)

def fetch_tab_data(service, tab_name, range_span="A1:F100"):
    """Fetches data from a specific tab."""
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=f"{tab_name}!{range_span}").execute()
    values = result.get('values', [])
    if not values: return []
    headers = values[0]
    return [dict(zip(headers, row + [''] * (len(headers) - len(row)))) for row in values[1:]]

@st.cache_data(ttl=600) # Cache this so it doesn't slow down the app on every reload
def get_all_student_names():
    """Fetches just the names for the Streamlit dropdown menu."""
    service = get_sheets_service()
    roster = fetch_tab_data(service, 'roster')
    return [student['name'] for student in roster if 'name' in student]

def get_student_academic_data(student_name):
    """This is the tool the AI will call to fetch the data."""
    service = get_sheets_service()
    roster_data = fetch_tab_data(service, 'roster')
    
    student_info = next((row for row in roster_data if row.get('name', '').strip().lower() == student_name.strip().lower()), None)
    if not student_info:
        return {"error": f"Student '{student_name}' not found."}
        
    student_id = student_info['student_id']
    scores_data = [row for row in fetch_tab_data(service, 'exam_scores') if row.get('student_id') == student_id]
    attendance_data = [row for row in fetch_tab_data(service, 'attendance') if row.get('student_id') == student_id]
    schedule_data = [row for row in fetch_tab_data(service, 'exam_schedule') if row.get('student_id') == student_id]
    
    return {
        "student_profile": student_info,
        "exam_scores": scores_data,
        "attendance": attendance_data,
        "upcoming_schedule": schedule_data
    }

# ==========================================
# 2. OPENAI TOOL DEFINITION
# ==========================================
# This tells the AI what tools it has access to and how to use them.
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_student_academic_data",
            "description": "Fetches a student's database profile, including recent exam scores, weekly attendance records, and upcoming exam schedule. Use this when the student asks about their grades, attendance, schedule, or overall performance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "student_name": {
                        "type": "string",
                        "description": "The full name of the student"
                    }
                },
                "required": ["student_name"],
            },
        }
    }
]

# ==========================================
# 3. STREAMLIT FRONTEND UI
# ==========================================
st.set_page_config(page_title="Success Coach AI", page_icon="🎓")

# Sidebar for Student Selection
with st.sidebar:
    st.header("👤 Student Login")
    try:
        student_list = get_all_student_names()
        selected_student = st.selectbox("Select your profile:", ["-- Select --"] + student_list)
    except Exception as e:
        st.error("Error connecting to Google Sheets. Check your credentials.")
        selected_student = "-- Select --"
        
st.title("🎓 Success Coach AI")

if selected_student == "-- Select --":
    st.info("Please select your name from the sidebar to begin.")
    st.stop() # Stops the rest of the app from running until a student is selected

st.write(f"Welcome back, **{selected_student}**! I'm your Success Coach. How can I help you today?")

# ==========================================
# 4. CHAT MEMORY & INITIALIZATION
# ==========================================
if "chat_history" not in st.session_state or st.session_state.get("current_student") != selected_student:
    # If the user changes their name in the dropdown, reset the chat history
    st.session_state.current_student = selected_student
    st.session_state.chat_history = [
       {
    "role": "system", 
    "content": f"You are a supportive Student Success Coach chatting with {selected_student}. Keep your tone warm, conversational, and encouraging—never sound judgmental. Whenever they ask about their grades, schedule, or attendance, you must use the get_student_academic_data tool to check their records. If you notice their grades slipping or their attendance dropping below 75%, gently bring it up. Don't lecture them; instead, check in to see how they are doing and offer a practical strategy to help them get back on track."
}
    ]

# Draw past messages
for msg in st.session_state.chat_history:
    if msg["role"] not in ["system", "tool"]: # Hide system prompts and raw tool data from the UI
        st.chat_message(msg["role"]).write(msg["content"])

# ==========================================
# 5. THE CHAT LOOP WITH AI TOOL CALLING
# ==========================================
if user_input := st.chat_input("Ask me about your grades, attendance, or upcoming exams..."):
    
    # Show user message
    st.chat_message("user").write(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.spinner("Analyzing your profile..."):
        # 1st Call to OpenAI: Let AI decide if it needs a tool
        response = client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17", # Upgraded to a standard tool-calling model, change back if you prefer your custom string
            messages=st.session_state.chat_history,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        # Check if AI decided to call our tool
        if response_message.tool_calls:
            # Add the AI's tool call request to memory
            st.session_state.chat_history.append(response_message)
            
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "get_student_academic_data":
                    # Extract the arguments the AI decided to use
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Execute our actual Python function
                    tool_data = get_student_academic_data(
                        student_name=function_args.get("student_name")
                    )
                    
                    # Add the raw data back to memory as a "tool" message
                    st.session_state.chat_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps(tool_data) # Send data as text
                    })
            
            # 2nd Call to OpenAI: Give it the raw data so it can write a nice message
            second_response = client.chat.completions.create(
                model="gpt-5.4-mini-2026-03-17",
                messages=st.session_state.chat_history
            )
            final_reply = second_response.choices[0].message.content
        else:
            # AI didn't need a tool, just reply normally
            final_reply = response_message.content

    # Show the final AI reply
    st.chat_message("assistant").write(final_reply)
    st.session_state.chat_history.append({"role": "assistant", "content": final_reply})