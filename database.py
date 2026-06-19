import os
import streamlit as st
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load environment variables

load_dotenv()

# ==========================================
# GOOGLE SHEETS DATABASE TOOLS
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

from datetime import datetime

def add_signal_to_db(student_name, signal_type, severity, urgency, reason):
    """Appends a new signal to the signal_sheet in Google Sheets."""
    try:
        # 1. Connect to the Google Sheets service
        service = get_sheets_service()
        
        # 2. Get current time
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. Build the row matching your columns: 
        # student_id | signal_type | severity | urgency | reason | timestamp | actioned
        new_row = [student_name, signal_type, severity, urgency, reason, timestamp, "FALSE"]
        
        # 4. Append to Google Sheets using the official API syntax
        body = {
            'values': [new_row]
        }
        
        result = service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range="signal_sheet!A:G", # Target the signal_sheet tab
            valueInputOption="USER_ENTERED", # Tells Google to format it normally
            body=body
        ).execute()
        
        print(f"Successfully added signal for {student_name} to database.")
        
    except Exception as e:
        print(f"Error saving signal to database: {e}")

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