import os
import streamlit as st
from mem0 import MemoryClient
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

def get_mem0_key():
   try:
       if "MEM0_API_KEY" in st.secrets:
           return st.secrets["MEM0_API_KEY"]
   except Exception:
       pass
   return os.getenv("MEM0_API_KEY")

def get_openai_key():
   try:
       if "OPENAI_API_KEY" in st.secrets:
           return st.secrets["OPENAI_API_KEY"]
   except Exception:
       pass
   return os.getenv("OPENAI_API_KEY")

def save_full_session(student_name, chat_history):
    """Processes an entire session's chat history and saves facts and a single summary."""
    # FIX 1: Clients are initialized inside the function to prevent Cloud crashes
    mem0_client = MemoryClient(api_key=get_mem0_key())
    llm_client = OpenAI(api_key=get_openai_key())
    
    try:
        # 1. Build a clean transcript from the chat history
        transcript = ""
        for msg in chat_history:
            if msg["role"] == "user":
                transcript += f"User: {msg['content']}\n"
            # We only want to log text content, not raw JSON tool calls
            elif msg["role"] == "assistant" and msg.get("content"): 
                transcript += f"AI: {msg['content']}\n"

        # If the transcript is empty (user just logged in and clicked end), do nothing
        if not transcript.strip():
            print("No conversation to save.")
            return

        print(f"Processing end-of-session memory for {student_name}...")

        # 2. PROCESS FACTUAL MEMORY (Whole session context)
        fact_prompt = (
            "Review this entire coaching session transcript. Extract ONLY permanent personal facts, "
            "stress triggers, study preferences, or recurring behavioral patterns about the user. "
            "Ignore temporary session topics or pleasantries. "
            f"If no permanent facts exist, reply with 'NONE'.\n\nTranscript:\n{transcript}"
        )
        fact_res = llm_client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=[{"role": "user", "content": fact_prompt}]
        )
        fact_content = fact_res.choices[0].message.content.strip()

        if fact_content and "NONE" not in fact_content.upper():
            # FIX 2: Changed "assistant" to "user" so Mem0 actually saves it permanently
            mem0_client.add([{"role": "user", "content": fact_content}], user_id=f"{student_name}_facts")
            print(f"Saved Session Facts: {fact_content}")

        # 3. PROCESS SESSION SUMMARY (Whole session context)
        summary_prompt = f"""Review this entire coaching session transcript. Summarize what concrete topics were discussed and what was decided or advised in 1-2 short sentences.

Transcript:
{transcript}"""
        summary_res = llm_client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=[{"role": "user", "content": summary_prompt}]
        )
        summary_content = summary_res.choices[0].message.content.strip()

        # FIX 2: Changed "assistant" to "user" so Mem0 actually saves it permanently
        mem0_client.add([{"role": "user", "content": summary_content}], user_id=f"{student_name}_summaries")
        print(f"Saved Session Summary: {summary_content}")

    except Exception as e:
        print(f"Memory processing failed: {e}")

def get_student_history(student_name):
    """Retrieves both factual profile data and past session briefings separately."""
    # FIX 1: Client initialized inside the function to prevent Cloud crashes
    mem0_client = MemoryClient(api_key=get_mem0_key())
    
    try:
        # 1. Fetch Factual Profile
        fact_response = mem0_client.get_all(filters={"user_id": f"{student_name}_facts"})
        
        # Safely extract the list from the "results" key (or "memories" in older package versions)
        if isinstance(fact_response, dict):
            fact_results = fact_response.get("results", fact_response.get("memories", []))
        else:
            fact_results = fact_response # Fallback if it returns a list directly
            
        facts = [item['memory'] for item in fact_results] if fact_results else []
        facts_str = "\n- ".join(facts) if facts else "No recurring patterns or personal traits recorded yet."

        # 2. Fetch Session Summaries
        summary_response = mem0_client.get_all(filters={"user_id": f"{student_name}_summaries"})
        
        if isinstance(summary_response, dict):
            summary_results = summary_response.get("results", summary_response.get("memories", []))
        else:
            summary_results = summary_response
            
        summaries = [item['memory'] for item in summary_results] if summary_results else []
        summaries_str = "\n- ".join(summaries) if summaries else "No previous session logs found."

        return facts_str, summaries_str
        
    except Exception as e:
        print(f"Failed to fetch memories: {e}")
        return "Error fetching facts.", "Error fetching summaries."