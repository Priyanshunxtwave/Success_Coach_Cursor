import time
import streamlit as st
import json
import os
# Add these to your existing imports at the top of app.py
from database import mark_signals_actioned
from coach_scheduler import generate_daily_schedule
from calendar_manager import push_schedule_to_calendar
from database import get_all_student_names, get_student_academic_data
from ai_coach import client, tools
from knowledge_base import search_course_material
from memory_manager import save_full_session, get_student_history
from database import get_all_student_names # Ensure you have this helper in database.py
from coach_briefing import generate_student_brief
st.set_page_config(page_title="Success Coach AI", page_icon="🎓")

# ==========================================
# LOGIN SYSTEM
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.user_name = None

# If not logged in, show the Login Page
if not st.session_state.logged_in:
    st.title("🎓 Success Coach Portal Login")
    
    tab1, tab2 = st.tabs(["🧑‍🎓 Student Login", "👨‍🏫 Coach Login"])
    
    with tab1:
        st.subheader("Student Access")
        try:
            student_list = get_all_student_names()
            selected_student = st.selectbox("Select your profile:", ["-- Select --"] + student_list)
            roll_number = st.text_input("Enter Roll Number:", type="password") # Simple mock auth
            
            if st.button("Login as Student", type="primary"):
                if selected_student != "-- Select --" and roll_number:
                    st.session_state.logged_in = True
                    st.session_state.role = "student"
                    st.session_state.user_name = selected_student
                    st.rerun()
                else:
                    st.error("Please select a name and enter your roll number.")
        except Exception as e:
            st.error("Database connection error.")

    with tab2:
        st.subheader("Coach Access")
        if st.button("Login as Coach", type="primary"):
            st.session_state.logged_in = True
            st.session_state.role = "coach"
            st.rerun()
            
    st.stop() # Halts the script here until login is successful

# ==========================================
# COACH DASHBOARD (Placeholder)
# ==========================================
# ==========================================
# COACH DASHBOARD (M7 Complete)

# ... existing code ...

if st.session_state.role == "coach":
    st.title("👨‍🏫 Coach Dashboard")
    st.write("Welcome to your daily command center.")
    
    # ==========================================
    # M9: PERSISTENT SUMMARY ON LOGIN
    # ==========================================
    SUMMARY_FILE = "latest_plan_summary.txt"
    if os.path.exists(SUMMARY_FILE):
        with open(SUMMARY_FILE, "r") as f:
            saved_summary = f.read()
        if saved_summary.strip():
            st.info(f"**🔔 Latest System Adjustments:** {saved_summary}")

    # ==========================================
    # M9: THE SCHEDULING ENGINE
    # ==========================================
    if st.button("📅 Run Autonomous Replanner", type="primary"):
        with st.spinner("Analyzing signals and replanning schedule..."):
            
            override = st.session_state.get("conflict_winner", None)
            schedule_data, raw_signals = generate_daily_schedule(coach_override=override)
            
            if not schedule_data:
                st.info("No critical student signals require attention today.")
            else:
                # 1. Check for Conflicts first
                conflict_info = schedule_data.get("conflict", {})
                
                if conflict_info.get("has_conflict") and not override:
                    st.error("⚠️ CRITICAL SCHEDULING CONFLICT DETECTED")
                    st.warning(f"**System Halted. Tradeoff Required:** {conflict_info.get('tradeoff_explanation')}")
                    
                    competing = conflict_info.get("competing_students", [])
                    if len(competing) >= 2:
                        st.write("**You must make the manual call. Who gets the final slot today?**")
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"Prioritize {competing[0]}", use_container_width=True):
                                st.session_state.conflict_winner = competing[0]
                                st.rerun()
                        with col2:
                            if st.button(f"Prioritize {competing[1]}", use_container_width=True):
                                st.session_state.conflict_winner = competing[1]
                                st.rerun()
                    st.stop() # Halts app until coach decides
                
                # 2. Proceed with booking if no conflicts (or if conflict resolved)
                if "conflict_winner" in st.session_state:
                    del st.session_state["conflict_winner"]

                calendar_success = push_schedule_to_calendar(schedule_data)
                
                if calendar_success:
                    st.success("✅ Schedule successfully pushed to Google Calendar!")
                    
                    # Write the summary to the local file for the next login
                    summary_text = schedule_data.get('changes_summary', 'No major changes.')
                    with open(SUMMARY_FILE, "w") as f:
                        f.write(summary_text)
                    
                    st.info(f"**Plan Updates:** {summary_text}")
                    
                    # Update database
                    scheduled_names = [slot["student_name"] for slot in schedule_data.get("scheduled_today", [])]
                    rows_to_update = [
                        signal["sheet_row_index"] for signal in raw_signals 
                        if signal.get("student_id", signal.get("student_name")) in scheduled_names
                    ]
                    mark_signals_actioned(rows_to_update)
                    
                    # Render UI
                    st.subheader("🗓️ Today's Itinerary")
                    for slot in schedule_data.get("scheduled_today", []):
                        with st.expander(f"{slot['start_time']} - {slot['end_time']} | {slot['student_name']}"):
                            st.markdown(f"**Type:** {slot['session_type']}")
                            st.markdown(f"**Focus:** {slot['reason']}")
                            
                    if schedule_data.get("deferred_tomorrow"):
                        st.subheader("⏭️ Deferred to Tomorrow")
                        for deferred in schedule_data["deferred_tomorrow"]:
                            st.warning(f"**{deferred['student_name']}**: {deferred['reason']}")
    # M8: PRE-MEETING BRIEF GENERATOR
    # ==========================================
    st.divider()
    st.header("📋 Pre-Meeting Student Brief")
    
    # Fetch all students to populate the dropdown
    all_students = get_all_student_names() 
    
    if all_students:
        # Layout with columns for a cleaner interface
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_student = st.selectbox("Select a student to brief:", all_students)
            
        with col2:
            # Align the button to the bottom of the column
            st.write("") 
            st.write("")
            generate_brief_btn = st.button("Generate Brief", type="secondary", use_container_width=True)

        # Trigger the LangChain engine when clicked
        if generate_brief_btn and selected_student:
            with st.spinner(f"Synthesizing memories and academic records for {selected_student}..."):
                student_brief = generate_student_brief(selected_student)
                
                # Display the beautifully formatted Markdown in an expander container
                with st.container(border=True):
                    st.markdown(student_brief)
    else:
        st.info("No students found in the database to brief.")

    st.divider()
    if st.button("Log Out"):
        st.session_state.clear()
        st.rerun()
    st.stop()

# ==========================================
# STUDENT CHAT APP (Original logic)
# ==========================================
if st.session_state.role == "student":
    selected_student = st.session_state.user_name
    
    # Sidebar logout & end session
    with st.sidebar:
        st.header(f"👤 {selected_student}")
        if st.button("🛑 End Session & Save", type="primary", use_container_width=True):
            with st.spinner("Analyzing and saving session..."):
                save_full_session(selected_student, st.session_state.chat_history)
                del st.session_state.chat_history 
                st.success("Session saved! Signals evaluated.")
                time.sleep(2)
                st.session_state.clear() # Log them out entirely when ending session
                st.rerun()
                
        if st.button("Log Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.title("🎓 Success Coach AI")
    st.write(f"Welcome back, **{selected_student}**! I'm your Success Coach. How can I help you today?")

    # --- CHAT MEMORY & INITIALIZATION ---
    if "chat_history" not in st.session_state or st.session_state.get("current_student") != selected_student:
        st.session_state.current_student = selected_student
        
        factual_profile, past_sessions = get_student_history(selected_student)
        
        st.session_state.chat_history = [
            {
                "role": "system",
                "content": (
                    f"You are a supportive Student Success Coach chatting with {selected_student}. "
                    "Keep your tone warm, conversational, and encouraging—never sound judgmental. "
                    "Whenever they ask about their grades, schedule, or attendance, you must use "
                    "the get_student_academic_data tool to check their records.\n\n"
                    
                    "CRITICAL: You must dynamically adapt your communication tone, empathy levels, and "
                    "coaching guidance based on the student's historical background and preferences below. "
                    "If students asks some questions unrelated to academics ,politely tell him that it is out of your scope and don't answer"
                    "A student with multiple past sessions should receive contextually advanced, deep responses "
                    "compared to a first-time student.\n\n"
                    
                    f"--- TYPE 1: FACTUAL MEMORY (Traits, Triggers, Patterns) ---\n- {factual_profile}\n\n"
                    f"--- TYPE 2: SESSION SUMMARIES (Past Discussions & Decisions) ---\n- {past_sessions}"
                )
            }
        ]

    for msg in st.session_state.chat_history:
        # Safely extract role and content whether it is a dict or an OpenAI object
        role = msg["role"] if isinstance(msg, dict) else msg.role
        content = msg["content"] if isinstance(msg, dict) else msg.content
        
        # Only draw if it's not a background system message AND it actually has text
        if role not in ["system", "tool"] and content:
            st.chat_message(role).write(content)

    # --- CHAT LOOP ---
    if user_input := st.chat_input("Ask me about your grades, attendance, or upcoming exams..."):
        st.chat_message("user").write(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("Thinking..."):
            response = client.chat.completions.create(
                model="gpt-5.4-mini-2026-03-17",
                messages=st.session_state.chat_history,
                tools=tools,
                tool_choice="auto"
            )
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                st.session_state.chat_history.append(response_message)
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "get_student_academic_data":
                        function_args = json.loads(tool_call.function.arguments)
                        tool_data = get_student_academic_data(student_name=function_args.get("student_name"))
                        st.session_state.chat_history.append({
                            "role": "tool", "tool_call_id": tool_call.id,
                            "name": tool_call.function.name, "content": json.dumps(tool_data)
                        })
                    elif tool_call.function.name == "search_course_material":
                        function_args = json.loads(tool_call.function.arguments)
                        tool_data = search_course_material(query=function_args.get("query"))
                        st.session_state.chat_history.append({
                            "role": "tool", "tool_call_id": tool_call.id,
                            "name": tool_call.function.name, "content": tool_data
                        })
                
                second_response = client.chat.completions.create(
                    model="gpt-5.4-mini-2026-03-17",
                    messages=st.session_state.chat_history
                )
                final_reply = second_response.choices[0].message.content
            else:
                final_reply = response_message.content

        st.chat_message("assistant").write(final_reply)
        st.session_state.chat_history.append({"role": "assistant", "content": final_reply})