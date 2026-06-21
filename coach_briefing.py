import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from memory_manager import get_student_history, get_openai_key
from database import get_student_academic_data

def generate_student_brief(student_name):
    """Fetches all student context and generates a structured pre-meeting brief using LangChain."""
    
    # 1. Fetch M5 Memories (Factual + Session Summaries)
    facts, summaries = get_student_history(student_name)
    
    # 2. Fetch Academic Data from Google Sheets
    academic_data = get_student_academic_data(student_name)
    if not academic_data:
        academic_data = "No current academic data available."

    # 3. Initialize the correct LangChain OpenAI wrapper
    llm = ChatOpenAI(
        model="gpt-5.4-mini-2026-03-17", 
        api_key=get_openai_key(),
        temperature=0.2 # Kept low for factual synthesis instead of creative fiction
    )

    # 4. Design the strict System Prompt mapping directly to M8 requirements
    SYSTEM_PROMPT = """You are an expert Student Success Coach preparing for an upcoming 1-on-1 meeting.
Your task is to analyze the provided student data and generate a highly focused pre-meeting brief.

You MUST structure your response using the following Markdown headers exactly:

### 📊 Current Academic Situation
Summarize their current grades, attendance, and overall academic standing based on the database records.

### 🔄 What Has Changed Since Last Session
Compare their past session summaries with their current state. Have they improved? Declined? Mentioned new issues? If this is the first session, state that.

### ⚠️ Open Concerns
Identify any red flags from their factual traits, past summaries, or academic data (e.g., mental health, skipping classes, failing grades).

### 💬 Conversation Starters for Today
Provide 2-3 specific, empathetic questions the coach can use to open the meeting based directly on the student's unique context."""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", """
        **Student Name:** {student_name}
        
        **Academic Database Records:** {academic_data}
        
        **Permanent Factual Memory:** {facts}
        
        **Past Session Summaries:** {summaries}
        """)
    ])

    # 5. Build the LangChain pipeline using LCEL
    chain = prompt_template | llm | StrOutputParser()

    try:
        # 6. Execute the chain
        brief_markdown = chain.invoke({
            "student_name": student_name,
            "academic_data": academic_data,
            "facts": facts,
            "summaries": summaries
        })
        return brief_markdown
        
    except Exception as e:
        print(f"Error generating brief: {e}")
        return f"**Error generating brief for {student_name}. Please check the server logs.**"