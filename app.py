import streamlit as st
import json


# Import logic from our custom modules
from database import get_all_student_names, get_student_academic_data
from ai_coach import client, tools
from knowledge_base import search_course_material
from memory_manager import save_full_session, get_student_history
# ==========================================
# STREAMLIT FRONTEND UI
# ==========================================
st.set_page_config(page_title="Success Coach AI", page_icon="🎓")


# Sidebar for Student Selection
# Sidebar for Student Selection
with st.sidebar:
    st.header("👤 Student Login")
    try:
        student_list = get_all_student_names()
        selected_student = st.selectbox("Select your profile:", ["-- Select --"] + student_list)
    except Exception as e:
        st.error("Error connecting to Google Sheets. Check your credentials.")
        selected_student = "-- Select --"
        
    # --- ADD THE NEW BUTTON HERE ---
    if selected_student != "-- Select --":
        st.divider() # Adds a nice visual line
        if st.button("🛑 End Session & Save", type="primary", use_container_width=True):
            with st.spinner("Saving session memories..."):
                save_full_session(selected_student, st.session_state.chat_history)
                # Delete the chat history to clear the screen
                del st.session_state.chat_history 
                st.success("Session saved successfully!")
                st.rerun() # Refresh the app
      
st.title("🎓 Success Coach AI")


if selected_student == "-- Select --":
   st.info("Please select your name from the sidebar to begin.")
   st.stop() # Stops the rest of the app from running until a student is selected


st.write(f"Welcome back, **{selected_student}**! I'm your Success Coach. How can I help you today?")


# ==========================================
# CHAT MEMORY & INITIALIZATION
# ==========================================
# ==========================================
# CHAT MEMORY & INITIALIZATION
# ==========================================
if "chat_history" not in st.session_state or st.session_state.get("current_student") != selected_student:
   st.session_state.current_student = selected_student
  
   # Fetch both memory types securely from our updated manager
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
               "A student with multiple past sessions should receive contextually advanced, deep responses "
               "compared to a first-time student.\n\n"
              
               f"--- TYPE 1: FACTUAL MEMORY (Traits, Triggers, Patterns) ---\n- {factual_profile}\n\n"
               f"--- TYPE 2: SESSION SUMMARIES (Past Discussions & Decisions) ---\n- {past_sessions}"
           )
       }
   ]
# Draw past messages
for msg in st.session_state.chat_history:
   if msg["role"] not in ["system", "tool"]: # Hide system prompts and raw tool data from the UI
       st.chat_message(msg["role"]).write(msg["content"])


# ==========================================
# THE CHAT LOOP WITH AI TOOL CALLING
# ==========================================
if user_input := st.chat_input("Ask me about your grades, attendance, or upcoming exams..."):
  
   # Show user message
   st.chat_message("user").write(user_input)
   st.session_state.chat_history.append({"role": "user", "content": user_input})


   with st.spinner("Analyzing your profile..."):
       # 1st Call to OpenAI: Let AI decide if it needs a tool
       response = client.chat.completions.create(
           model="gpt-5.4-mini-2026-03-17",
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
              
               # --- TOOL 1: DATABASE LOOKUP ---
               if tool_call.function.name == "get_student_academic_data":
                   function_args = json.loads(tool_call.function.arguments)
                   tool_data = get_student_academic_data(
                       student_name=function_args.get("student_name")
                   )
                  
                   st.session_state.chat_history.append({
                       "role": "tool",
                       "tool_call_id": tool_call.id,
                       "name": tool_call.function.name,
                       "content": json.dumps(tool_data)
                   })
              
               # --- TOOL 2: RAG KNOWLEDGE BASE ---
               elif tool_call.function.name == "search_course_material":
                   function_args = json.loads(tool_call.function.arguments)
                   tool_data = search_course_material(
                       query=function_args.get("query")
                   )
                  
                   st.session_state.chat_history.append({
                       "role": "tool",
                       "tool_call_id": tool_call.id,
                       "name": tool_call.function.name,
                       "content": tool_data
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
  
   # Silently save the interaction to Mem0 in the background
