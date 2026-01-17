import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import json
import os
from dotenv import load_dotenv
from gemini_api_manager import get_api_manager
import re

load_dotenv()

st.set_page_config(page_title="Teaching Pariksha: AI Quiz Gen", page_icon="📝")

st.sidebar.header("⚙️ System Status")

api_manager = get_api_manager()
status = api_manager.get_status()

st.sidebar.metric("Total API Keys", status["total_keys"])
st.sidebar.metric("Current Model", status["current_model"])

if status["failed_keys"] > 0:
    st.sidebar.warning(f"⚠️ {status['failed_keys']} keys have failed")
    
if st.sidebar.button("🔄 Reset API Manager"):
    api_manager.reset()
    st.sidebar.success("API Manager reset!")
    st.rerun()

# Show available models
with st.sidebar.expander("📋 Model Fallback Order"):
    for i, model in enumerate(status["available_models"], 1):
        prefix = "✅" if i - 1 == status["current_model_index"] else "⏳"
        st.write(f"{prefix} {i}. {model}")

# --- MAIN UI ---
st.title("🎓 Teaching Pariksha: AI Quiz Generator")
st.markdown("Generate a **BPSC/CTET Mock Test** instantly from any YouTube lecture.")

# Check if API keys are configured
if status["total_keys"] == 0:
    st.error("⚠️ No API keys configured! Please add your Gemini API keys to the `.env` file.")
    st.code("""
# Create a .env file with your API keys:
GEMINI_API_KEY_1=your_key_here
GEMINI_API_KEY_2=your_key_here
# ... up to 20 keys
    """, language="bash")
    st.stop()

# Input Field
video_url = st.text_input("Paste Danish Sir's YouTube Video URL here:")

# --- FUNCTIONS ---
def get_transcript(url):
    try:
        # Handle different YouTube URL formats
        if "youtu.be/" in url:
            video_id = url.split("youtu.be/")[1].split("?")[0]
        elif "/live/" in url:
            video_id = url.split("/live/")[1].split("?")[0]
        elif "v=" in url:
            video_id = url.split("v=")[1].split("&")[0]
        else:
            st.error("Invalid YouTube URL format")
            return None
        
        st.info(f"📹 Fetching transcript for video ID: {video_id}")
        
        # Fetch transcript using the API
        ytt_api = YouTubeTranscriptApi()
        
        try:
            # Try to get transcript in preferred languages
            transcript = ytt_api.fetch(video_id, languages=['hi', 'en', 'hi-IN'])
            text = " ".join([i.text for i in transcript])
            st.success(f"✅ Transcript fetched! ({len(text)} characters)")
            return text
        except NoTranscriptFound:
            st.error("No transcript found for this video in Hindi or English")
            return None
        except TranscriptsDisabled:
            st.error("Transcripts are disabled for this video")
            return None
            
    except Exception as e:
        st.error(f"Error: {e}")
        return None

from fpdf import FPDF
import os

# --- PDF GENERATION CLASS ---
# Using fpdf2 with a Unicode font for Hindi support
FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoSansDevanagari-Regular.ttf")

class QuizPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Set smaller margins for more horizontal space
        self.set_margins(10, 10, 10)  # left, top, right
        self.set_auto_page_break(True, 15)
        
        # Register the Unicode font for Hindi (Devanagari)
        if os.path.exists(FONT_PATH):
            self.add_font("NotoSans", "", FONT_PATH)
        else:
            print(f"Warning: Font not found at {FONT_PATH}. Hindi text may not render correctly.")
            
    def header(self):
        self.set_font('NotoSans' if os.path.exists(FONT_PATH) else 'Arial', '', 14)
        self.cell(0, 8, 'Teaching Pariksha: AI Generated Quiz', 0, 1, 'C')
        self.ln(3)

    def footer(self):
        self.set_y(-12)
        self.set_font('NotoSans' if os.path.exists(FONT_PATH) else 'Arial', '', 7)
        self.cell(0, 8, f'Page {self.page_no()}', 0, 0, 'C')

def create_quiz_pdf(quiz_data):
    pdf = QuizPDF()
    pdf.add_page()
    
    font_name = 'NotoSans' if os.path.exists(FONT_PATH) else 'Arial'

    # Questions Section
    for i, q in enumerate(quiz_data, 1):
        # English Question
        pdf.set_font(font_name, '', 10)
        pdf.multi_cell(0, 6, f"Q{i}: {q['question_en']}")
        
        # Hindi Question
        pdf.set_font(font_name, '', 9)
        pdf.multi_cell(0, 5, f"({q['question_hi']})")
        pdf.ln(1)
        
        # Bilingual Options - format: "English (Hindi)"
        pdf.set_font(font_name, '', 9)
        # Handle both old format (options) and new format (options_en/options_hi)
        if 'options_en' in q and 'options_hi' in q:
            opts_en = q['options_en']
            opts_hi = q['options_hi']
            pdf.multi_cell(0, 5, f"A) {opts_en.get('A', '')} ({opts_hi.get('A', '')})")
            pdf.multi_cell(0, 5, f"B) {opts_en.get('B', '')} ({opts_hi.get('B', '')})")
            pdf.multi_cell(0, 5, f"C) {opts_en.get('C', '')} ({opts_hi.get('C', '')})")
            pdf.multi_cell(0, 5, f"D) {opts_en.get('D', '')} ({opts_hi.get('D', '')})")
        else:
            # Fallback for old format
            options = q.get('options', {})
            pdf.multi_cell(0, 5, f"A) {options.get('A', '')}")
            pdf.multi_cell(0, 5, f"B) {options.get('B', '')}")
            pdf.multi_cell(0, 5, f"C) {options.get('C', '')}")
            pdf.multi_cell(0, 5, f"D) {options.get('D', '')}")
        pdf.ln(3)

    # Answer Key Section
    pdf.add_page()
    pdf.set_font(font_name, '', 12)
    pdf.cell(0, 8, "Answer Key & Explanations", 0, 1, 'C')
    pdf.ln(3)

    for i, q in enumerate(quiz_data, 1):
        pdf.set_font(font_name, '', 9)
        pdf.cell(0, 5, f"Q{i}: {q['correct_option']}", 0, 1)
        
        # Bilingual explanations
        pdf.set_font(font_name, '', 8)
        if 'explanation_en' in q and 'explanation_hi' in q:
            pdf.multi_cell(0, 4, f"EN: {q['explanation_en']}")
            pdf.multi_cell(0, 4, f"HI: {q['explanation_hi']}")
        else:
            pdf.multi_cell(0, 4, f"Exp: {q.get('explanation', '')}")
        pdf.ln(2)
        
    return pdf.output()


# --- SIDEBAR SETTINGS ---
with st.sidebar.expander("🛠️ Quiz Settings", expanded=True):
    num_questions = st.number_input("Number of Questions", min_value=5, max_value=50, value=5, step=1)
    difficulty = st.selectbox("Difficulty Level", ["Easy", "Medium", "Hard"])

# --- FUNCTIONS ---
# ... get_transcript is same ...

def generate_questions(text, num=5, diff="Medium"):
    """Generate questions using the API manager with automatic fallback."""
    # Stricter prompt to enforce exact question count and bilingual options
    prompt = f"""
    You are a Senior Faculty at Teaching Pariksha. 
    
    CRITICAL: Generate EXACTLY {num} MCQs. Not more, not less. Count carefully before responding.
    
    Difficulty Level: {diff}
    
    Output ONLY a valid JSON array, no other text. Strictly follow this structure:
    [{{
        "question_en": "Question in English",
        "question_hi": "Question in Hindi",
        "options_en": {{"A": "Option A in English", "B": "Option B", "C": "Option C", "D": "Option D"}},
        "options_hi": {{"A": "Option A in Hindi", "B": "Option B", "C": "Option C", "D": "Option D"}},
        "correct_option": "A",
        "explanation_en": "Explanation in English",
        "explanation_hi": "Explanation in Hindi"
    }}, ...]
    
    Rules:
    - Exactly {num} questions
    - Keep options concise (max 40 characters each)
    - Provide both English AND Hindi for questions, options, and explanations
    - CTET/BPSC exam style
    
    TRANSCRIPT: {text[:12000]}
    """
    
    response_text, model_used = api_manager.generate_content(prompt)
    return response_text, model_used

# --- APP LOGIC ---

# Initialize session state for quiz data
if 'quiz_data' not in st.session_state:
    st.session_state.quiz_data = None
if 'quiz_generated' not in st.session_state:
    st.session_state.quiz_generated = False

# Generate Button
if st.button("Generate Quiz 🚀"):
    if not video_url:
        st.warning("Please paste a YouTube URL.")
    else:
        with st.spinner(f"🎧 Generating {num_questions} {difficulty} questions..."):
            # 1. Get Text
            transcript_text = get_transcript(video_url)
            
            if transcript_text:
                # 2. Generate AI Quiz
                try:
                    # PASS CONFIGURATION TO FUNCTION
                    raw_response, model_used = generate_questions(transcript_text, num_questions, difficulty)
                    print(f"DEBUG: Raw API Response:\n{raw_response}") 
                    
                    # Robust JSON extraction
                    try:
                        # Find the first '[' and last ']'
                        json_start = raw_response.find('[')
                        json_end = raw_response.rfind(']')
                        
                        if json_start != -1 and json_end != -1 and json_end > json_start:
                            clean_json = raw_response[json_start:json_end+1]
                        else:
                            # Fallback if no brackets found (unlikely for a valid list response)
                            clean_json = raw_response.strip()
                            
                        # Debugging
                        print(f"DEBUG: Extracted JSON (first 100 chars): {clean_json[:100]}...")

                        # STORE IN SESSION STATE
                        st.session_state.quiz_data = json.loads(clean_json)
                        st.session_state.quiz_generated = True
                        st.session_state.model_used = model_used
                        
                    except json.JSONDecodeError as e:
                        st.error("Failed to parse JSON response from AI.")
                        with st.expander("See Raw Response"):
                            st.code(raw_response)
                        # We do NOT raise here, so the app doesn't crash.
                        
                except Exception as e:
                    st.error(f"AI error: {e}")
                    st.info("💡 The system automatically tried all available API keys and models. Please check your API key configuration.")
            else:
                st.error("Could not retrieve transcript. Does the video have captions enabled?")

# --- DISPLAY QUIZ (From Session State) ---
if st.session_state.quiz_generated and st.session_state.quiz_data:
    st.success(f"✅ Quiz Generated Successfully using {st.session_state.get('model_used', 'Gemini')}!")
    
    # PDF DOWNLOAD BUTTON
    try:
        pdf_bytes = create_quiz_pdf(st.session_state.quiz_data)
        st.download_button(
            label="📄 Download Quiz PDF",
            data=pdf_bytes,
            file_name="teaching_pariksha_quiz.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.warning(f"Could not generate PDF (likely encoding issue): {e}")

    # Iterate through stored questions
    for i, q in enumerate(st.session_state.quiz_data, 1):
        st.markdown(f"### Q{i}: {q['question_en']}")
        st.markdown(f"**Hindi:** {q['question_hi']}")
        
        # Build options list with bilingual support
        if 'options_en' in q and 'options_hi' in q:
            opts_en = q['options_en']
            opts_hi = q['options_hi']
            options_list = [
                f"A) {opts_en.get('A', '')} ({opts_hi.get('A', '')})",
                f"B) {opts_en.get('B', '')} ({opts_hi.get('B', '')})",
                f"C) {opts_en.get('C', '')} ({opts_hi.get('C', '')})",
                f"D) {opts_en.get('D', '')} ({opts_hi.get('D', '')})"
            ]
        else:
            # Fallback for old format
            opts = q.get('options', {})
            options_list = [
                f"A) {opts.get('A', '')}",
                f"B) {opts.get('B', '')}",
                f"C) {opts.get('C', '')}",
                f"D) {opts.get('D', '')}"
            ]
        
        # Unique key for every radio button group to maintain state
        user_answer = st.radio(
            f"Select your answer for Q{i}:", 
            options_list, 
            key=f"q_{i}", 
            index=None # No default selection
        )
        
        # Logic to check answer immediately on frontend without API call
        if user_answer:
            selected_option = user_answer.split(")")[0] # Extract 'A', 'B', 'C', or 'D'
            correct_option = q['correct_option']
            
            if selected_option == correct_option:
                st.success(f"✅ Correct! The answer is **{correct_option}**")
            else:
                st.error(f"❌ Wrong. You selected **{selected_option}**, but the correct answer is **{correct_option}**.")
            
            # Show bilingual explanation
            with st.expander(f"View Explanation for Q{i}"):
                if 'explanation_en' in q and 'explanation_hi' in q:
                    st.info(f"**English:** {q['explanation_en']}")
                    st.info(f"**Hindi:** {q['explanation_hi']}")
                else:
                    st.info(f"**Explanation:** {q.get('explanation', '')}")
        
        st.divider()

    # Option to clear/reset
    if st.button("Start New Quiz"):
        st.session_state.quiz_data = None
        st.session_state.quiz_generated = False
        st.rerun()