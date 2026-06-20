import os
from datetime import datetime
from dotenv import load_dotenv
from database import get_calendar_service

load_dotenv()

def get_calendar_id():
    """Dynamically fetches the Calendar ID to prevent import order bugs."""
    import streamlit as st
    try:
        if "GOOGLE_CALENDAR_ID" in st.secrets:
            return st.secrets["GOOGLE_CALENDAR_ID"]
    except Exception:
        pass
    return os.getenv("GOOGLE_CALENDAR_ID")

def push_schedule_to_calendar(schedule_data):
    """Iterates through the AI schedule and inserts events into the Google Calendar."""
    if not schedule_data or "scheduled_today" not in schedule_data:
        return False
        
    calendar_id = get_calendar_id()
        
    if not calendar_id:
        print("Error: GOOGLE_CALENDAR_ID not found in configurations.")
        return False
        
    service = get_calendar_service()
    current_date = datetime.now().strftime("%Y-%m-%d") 
    
    success_count = 0
    
    for slot in schedule_data["scheduled_today"]:
        try:
            start_rfc = f"{current_date}T{slot['start_time']}:00"
            end_rfc = f"{current_date}T{slot['end_time']}:00"
            
            event_body = {
                'summary': f"Success Coach Meeting: {slot['student_name']}",
                'description': f"Session Type: {slot['session_type']}\nReason: {slot['reason']}",
                'start': {
                    'dateTime': start_rfc,
                    'timeZone': 'Asia/Kolkata', 
                },
                'end': {
                    'dateTime': end_rfc,
                    'timeZone': 'Asia/Kolkata',
                },
            }
            
            # Insert the event directly into the dedicated calendar
            service.events().insert(calendarId=calendar_id, body=event_body).execute()
            success_count += 1
            print(f"Booked calendar event for {slot['student_name']} at {slot['start_time']}")
            
        except Exception as e:
            print(f"Failed to create event for {slot['student_name']}: {e}")
            
    return success_count > 0