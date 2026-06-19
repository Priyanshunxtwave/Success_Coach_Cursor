from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI Client
client = OpenAI()

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