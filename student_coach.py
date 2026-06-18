import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

# Load your API key
load_dotenv()
client = OpenAI()

# --- THE FRONTEND UI ---
st.title("🎓 Simple Student Coach")
st.write("Welcome! I'm your pure OpenAI web coach.")

# --- THE MEMORY ---
# We store the chat_history inside Streamlit's "session_state" so the webpage remembers it
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "system", "content": "You are a friendly, encouraging Student Success Coach."}
    ]

# Draw all past messages on the screen (except the hidden system prompt)
for msg in st.session_state.chat_history:
    if msg["role"] != "system":
        st.chat_message(msg["role"]).write(msg["content"])

# --- THE CHAT LOOP ---
# This creates the text box at the bottom of the screen
if user_input := st.chat_input("Type your message here..."):
    
    # 1. Show the user's message on screen and save it to memory
    st.chat_message("user").write(user_input)
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    # 2. Send the memory to OpenAI
    with st.spinner("Thinking..."):
        response = client.chat.completions.create(
            model="gpt-5.4-mini-2026-03-17",
            messages=st.session_state.chat_history,
            temperature=0.7
        )
        ai_reply = response.choices[0].message.content
        
    # 3. Show the AI's reply on screen and save it to memory
    st.chat_message("assistant").write(ai_reply)
    st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})