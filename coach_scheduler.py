import os
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from database import fetch_pending_signals
from memory_manager import get_openai_key
load_dotenv()

# ==========================================
# 1. DEFINE STRUCURED OUTPUT SCHEMAS (Pydantic)
# ==========================================
class ScheduledSlot(BaseModel):
    student_name: str = Field(description="Full name of the student being scheduled.")
    start_time: str = Field(description="Start time in 24-hour HH:MM format (e.g., 09:30).")
    end_time: str = Field(description="End time in 24-hour HH:MM format (e.g., 10:30).")
    session_type: str = Field(description="Category: Academic Review, Mental Health Check, or Attendance Intervention.")
    reason: str = Field(description="A concise description of why this student requires attention today.")

class DeferredSlot(BaseModel):
    student_name: str = Field(description="Full name of the student who could not fit into today's schedule.")
    reason: str = Field(description="Detailed reason explaining why they were deferred to tomorrow.")

class DailyItinerary(BaseModel):
    scheduled_today: List[ScheduledSlot] = Field(description="List of students successfully scheduled within the 8-hour workday.")
    deferred_tomorrow: List[DeferredSlot] = Field(description="List of students deferred due to time constraints.")


# ==========================================
# 2. CORE SCHEDULER FUNCTION
# ==========================================
def generate_daily_schedule():
    """Fetches pending signals and uses LangChain to generate a structured 8-hour workday itinerary."""
    # Fetch un-actioned signals from the database
    signals = fetch_pending_signals()
    
    if not signals:
        print("No pending student signals found today.")
        return None, []

    # Format the raw database signals into a clear block of text for the prompt
    signals_context = ""
    for s in signals:
        # Using .get() prevents future KeyErrors and we use 'student_id' to match your sheet
        student_identifier = s.get('student_id', s.get('student_name', 'Unknown'))
        
        signals_context += (
            f"- Student: {student_identifier} | Type: {s.get('signal_type', 'None')} | "
            f"Severity: {s.get('severity', 'None')} | Urgency: {s.get('urgency', 'None')} | Reason: {s.get('reason', 'None')}\n"
        )

    # Initialize the LangChain ChatOpenAI wrapper
    # It leverages your existing key retrieval helper function
    llm = ChatOpenAI(
        model="gpt-5.4-mini-2026-03-17", 
        api_key=get_openai_key(),
        temperature=0.1
    )

    # Enforce strict structured output matching our Pydantic schema
    structured_llm = llm.with_structured_output(DailyItinerary)

    # Create the LangChain Prompt Template
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """You are an elite administrative assistant coordinating a Student Success Coach's daily schedule.
Your goal is to organize an 8-hour workday itinerary (strictly from 09:00 AM to 05:00 PM) based on incoming high-priority student alert signals.

Scheduling Constraints:
. You must assign each student to one of these exact, non-overlapping sequential time slots:
   - Slot 1: 09:00 to 10:00
   - Slot 2: 10:00 to 11:00
   - Slot 3: 11:00 to 12:00
   - Slot 4: 13:00 to 14:00
   - Slot 5: 14:00 to 15:00
   - Slot 6: 15:00 to 16:00
   - Slot 7: 16:00 to 17:00
. NEVER assign two students to the same time slot.
1. Prioritize 'Critical' and 'High' severity items first, followed by 'Medium'. Completely ignore 'Low' severity.
2. Prioritize 'Action Today' over 'Action Tomorrow'.
3. Assign session durations based on severity: 'Critical' or 'High' gets a 60-minute slot. 'Medium' gets a 30-minute slot.
4. Do not allow overlapping time slots under any circumstances.
5. If the schedule fills up completely between 09:00 AM and 05:00 PM, any remaining students MUST be placed into the 'deferred_tomorrow' list with an explanation."""),
        ("user", "Current Pending Signals:\n{incoming_signals}")

    ])

    # Construct the LangChain executable pipeline (LCEL syntax)
    chain = prompt_template | structured_llm

    try:
        # Run the chain to get a strongly-typed Pydantic object back
        itinerary_object = chain.invoke({"incoming_signals": signals_context})
        
        # Convert the Pydantic object directly into a standard Python dict for the calendar manager
        schedule_data = itinerary_object.model_dump()
        return schedule_data, signals
        
    except Exception as e:
        print(f"Error generating schedule via LangChain: {e}")
        return None, []