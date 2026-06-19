import os
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables for local development
load_dotenv()

def get_openai_key():
    try:
        # Try to pull from Streamlit Cloud Secrets first
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass # Ignore if st.secrets doesn't exist locally
        
    # Fallback for local development
    return os.getenv("OPENAI_API_KEY")

# Initialize OpenAI Client explicitly with the key
client = OpenAI(api_key=get_openai_key())

# ==========================================
# OPENAI TOOL DEFINITION
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