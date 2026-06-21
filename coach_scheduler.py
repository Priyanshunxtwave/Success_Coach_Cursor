import os
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from memory_manager import get_openai_key
from database import fetch_pending_signals

load_dotenv()

# ==========================================
# 1. M9 SCHEMAS (Strict Formatting)
# ==========================================
class ScheduledSlot(BaseModel):
    student_name: str = Field(description="Full name of the student.")
    start_time: str = Field(description="Start time (e.g., 09:00). Must be unique.")
    end_time: str = Field(description="End time (e.g., 10:00).")
    session_type: str = Field(description="Category of session.")
    reason: str = Field(description="Why this student requires attention today.")

class DeferredSlot(BaseModel):
    student_name: str = Field(description="Student bumped/deferred to tomorrow.")
    reason: str = Field(description="Clear reason explaining why they were bumped (e.g., replaced by a critical incident).")

class ConflictDetails(BaseModel):
    has_conflict: bool = Field(description="TRUE ONLY if all slots are full and multiple Critical students are competing for the same spot.")
    competing_students: List[str] = Field(description="Names of the students in conflict.", default=[])
    tradeoff_explanation: str = Field(description="Clear explanation of the tradeoff for the coach.", default="")

class DailyItinerary(BaseModel):
    scheduled_today: List[ScheduledSlot] = Field(description="List of scheduled students. NO OVERLAPPING TIMES.")
    deferred_tomorrow: List[DeferredSlot] = Field(description="List of bumped/deferred students.")
    changes_summary: str = Field(description="A brief summary of who was added, moved, or bumped to accommodate the current queue.")
    conflict: ConflictDetails = Field(description="Details regarding any unresolvable critical conflicts.")


# ==========================================
# 2. CORE REPLANNING FUNCTION
# ==========================================
def generate_daily_schedule(coach_override: str = None):
    """Generates the schedule, handles dynamic bumping, and detects conflicts."""
    signals = fetch_pending_signals()
    if not signals:
        return None, []

    signals_context = ""
    for s in signals:
        student_identifier = s.get('student_id', s.get('student_name', 'Unknown'))
        signals_context += (
            f"- Student: {student_identifier} | Type: {s.get('signal_type')} | "
            f"Severity: {s.get('severity')} | Reason: {s.get('reason')}\n"
        )

    # Force the AI to obey the coach's manual tie-breaker
    if coach_override:
        signals_context += f"\n*** SYSTEM OVERRIDE: {coach_override} MUST be scheduled today. Resolve conflict accordingly. ***"

    llm = ChatOpenAI(model="gpt-5.4-mini-2026-03-17", api_key=get_openai_key(), temperature=0.0) # Temp 0.0 for strict math
    structured_llm = llm.with_structured_output(DailyItinerary)

    SYSTEM_PROMPT = """You are an elite, autonomous Student Success scheduling agent.
Your job is to read the queue of pending student signals and pack them into a strict workday.

M9 STRICT SCHEDULING RULES:
1. Available Slots: You only have exactly 6 slots (09:00, 10:00, 11:00, 13:00, 14:00, 15:00).
2. NO DOUBLE BOOKING: You may NEVER assign two students to the same start_time.
3. REPLANNING & BUMPING: Rank students by Severity (Critical > High > Medium). Fill the slots top-down. If you run out of slots, you MUST bump the remaining lower-priority students to the 'deferred_tomorrow' list.

M9 CONFLICT RESOLUTION:
If the schedule is completely full of 'High' or 'Critical' students, and a NEW 'Critical' student needs a slot, causing a tie where you cannot fit them all:
- DO NOT randomly guess.
- Set 'has_conflict' to True.
- List the names in 'competing_students'.
- Explain the exact tradeoff in 'tradeoff_explanation' so the human coach can make the manual call.
- Leave the disputed slot empty."""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "Current Pending Signals Queue:\n{incoming_signals}")
    ])

    chain = prompt_template | structured_llm

    try:
        itinerary_object = chain.invoke({"incoming_signals": signals_context})
        schedule_data = itinerary_object.model_dump()
        return schedule_data, signals
    except Exception as e:
        print(f"Error generating schedule: {e}")
        return None, []