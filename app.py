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

from fpdf.enums import XPos, YPos

# --- PDF GENERATION CLASS ---
# Using fpdf2 with Landscape mode
# Attempt to use Windows system fonts for full Unicode support
SYSTEM_FONTS = [
    ("Nirmala", "C:/Windows/Fonts/Nirmala.ttf"),       # Best for Indic + English
    ("ArialUnicode", "C:/Windows/Fonts/arialuni.ttf"), # Good fallback
    ("Arial", "C:/Windows/Fonts/arial.ttf")            # Standard English
]
LOCAL_HINDI_FONT = os.path.join(os.path.dirname(__file__), "NotoSansDevanagari-Regular.ttf")

class QuizPDF(FPDF):
    def __init__(self):
        super().__init__(orientation='L')
        self.set_margins(8, 8, 8)
        self.set_auto_page_break(True, 10)
        
        self.main_font = None
        self.hindi_font = None
        
        # 1. Try to load a Universal System Font (English + Hindi)
        for name, path in SYSTEM_FONTS:
            if os.path.exists(path):
                try:
                    self.add_font(name, "", path)
                    self.main_font = name
                    print(f"DEBUG: Loaded system font {name}")
                    break
                except Exception as e:
                    print(f"DEBUG: Failed to load {name}: {e}")
        
        # 2. If no system font or assumed basic arial, try loading local NotoSans for Hindi
        if os.path.exists(LOCAL_HINDI_FONT):
            try:
                self.add_font("NotoSans", "", LOCAL_HINDI_FONT)
                self.hindi_font = "NotoSans"
            except:
                pass

        # Fallback: If no main font found, rely on core fonts (Helvetica) which creates the crash risk
        if not self.main_font:
            self.main_font = 'helvetica'

    def header(self):
        # Use main font (presumably supports English)
        self.set_font(self.main_font, 'B', 16)
        self.cell(0, 10, 'Teaching Pariksha: AI Generated Quiz', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.main_font, 'I', 10)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def safe_text(text, max_len=300):
    if not text: return ""
    clean = str(text).replace('\n', ' ').replace('\r', ' ')
    return clean[:max_len] + "..." if len(clean) > max_len else clean

def clean_latin(text):
    """Remove non-latin characters to prevent Helvetica crashes"""
    return "".join([c for c in text if ord(c) < 256])

def create_quiz_pdf(quiz_data, include_hindi=True):
    pdf = QuizPDF()
    pdf.add_page()
    
    # Strategy:
    # A) If we have Nirmala/ArialUnicode -> Use it for EVERYTHING.
    # B) If we only have Arial/Helvetica -> Use it for English, NotoSans for Hindi.
    
    universal_mode = (pdf.main_font in ["Nirmala", "ArialUnicode"])
    english_font = pdf.main_font
    hindi_font = pdf.hindi_font if pdf.hindi_font else pdf.main_font
    
    use_hindi_content = include_hindi and (universal_mode or pdf.hindi_font)

    # Questions Section
    for i, q in enumerate(quiz_data, 1):
        try:
            # 1. Question (English Field)
            # If universal, print raw. If split mode, sanitize English to remove stray Hindi chars.
            q_en_raw = f"Q{i}: {q.get('question_en', 'Question not available')}"
            
            if universal_mode:
                pdf.set_font(english_font, '', 12)
                pdf.multi_cell(0, 6, safe_text(q_en_raw), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                # Split mode: Sanitize English to prevent crash
                pdf.set_font(english_font, '', 12)
                pdf.multi_cell(0, 6, safe_text(clean_latin(q_en_raw)), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            # 2. Hindi Question
            if use_hindi_content and 'question_hi' in q and q['question_hi'].strip():
                font_to_use = english_font if universal_mode else hindi_font
                pdf.set_font(font_to_use, '', 11)
                pdf.multi_cell(0, 6, safe_text(f"({q['question_hi']})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.ln(3)
            
            # 3. Arguments
            if 'options_en' in q:
                opts_en = q['options_en']
                opts_hi = q.get('options_hi', {})
            else:
                opts_en = q.get('options', {})
                opts_hi = {}

            for letter in ['A', 'B', 'C', 'D']:
                en_text = opts_en.get(letter, '')
                hi_text = opts_hi.get(letter, '')
                
                # Option English
                if universal_mode:
                    pdf.set_font(english_font, '', 11)
                    pdf.multi_cell(0, 6, f"{letter}) {safe_text(en_text)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                else:
                    pdf.set_font(english_font, '', 11)
                    pdf.multi_cell(0, 6, f"{letter}) {safe_text(clean_latin(en_text))}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

                # Option Hindi
                if use_hindi_content and hi_text:
                    font_to_use = english_font if universal_mode else hindi_font
                    pdf.set_font(font_to_use, '', 10)
                    pdf.set_x(pdf.get_x() + 5)
                    pdf.multi_cell(0, 6, safe_text(hi_text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            
            pdf.ln(4)
            
        except Exception as e:
            print(f"Error rendering Q{i}: {e}")
            # Emergency Fallback
            pdf.set_font('helvetica', '', 10)
            pdf.cell(0, 5, f"Q{i}: [Error]", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Answer Key
    pdf.add_page()
    pdf.set_font(english_font, 'B', 14)
    pdf.cell(0, 10, "Answer Key", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(5)

    for i, q in enumerate(quiz_data, 1):
        pdf.set_font(english_font, 'B', 11)
        pdf.cell(0, 6, f"Q{i}: {q.get('correct_option', '?')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        # English Explanation
        exp_en = q.get('explanation_en', q.get('explanation', ''))
        if exp_en:
            pdf.set_font(english_font, '', 10)
            if universal_mode:
                 pdf.multi_cell(0, 5, safe_text(f"EN: {exp_en}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            else:
                 pdf.multi_cell(0, 5, safe_text(clean_latin(f"EN: {exp_en}")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Hindi Explanation
        exp_hi = q.get('explanation_hi', '')
        if use_hindi_content and exp_hi:
            font_to_use = english_font if universal_mode else hindi_font
            pdf.set_font(font_to_use, '', 10)
            
            # Universal mode handles English prefix fine. Split mode logic:
            prefix = "HI: " if universal_mode else ""
            pdf.multi_cell(0, 5, safe_text(f"{prefix}{exp_hi}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        
        pdf.ln(3)

    return bytes(pdf.output())


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
if 'model_used' not in st.session_state:
    st.session_state.model_used = ""

# Generate Button
if st.button("Generate Quiz 🚀"):
    if not video_url:
        st.warning("Please paste a YouTube URL.")
    else:
        # CLEAR OLD QUIZ DATA FIRST
        st.session_state.quiz_data = None
        st.session_state.quiz_generated = False
        
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
    
    # PDF DOWNLOAD BUTTON - WITH FALLBACK
    pdf_bytes = None
    try:
        # Try generating standard bilingual PDF
        pdf_bytes = create_quiz_pdf(st.session_state.quiz_data, include_hindi=True)
        pdf_label = "📄 Download Quiz PDF (Hindi + English)"
    except Exception as e:
        print(f"Bilingual PDF generation failed: {e}")
        try:
            # Fallback to English only
            pdf_bytes = create_quiz_pdf(st.session_state.quiz_data, include_hindi=False)
            st.warning("⚠️ Could not render Hindi PDF due to layout issues. Download English-only PDF instead.")
            pdf_label = "📄 Download Quiz PDF (English Only)"
        except Exception as e2:
             st.error(f"Failed to generate PDF: {e2}")

    if pdf_bytes:
        st.download_button(
            label=pdf_label,
            data=pdf_bytes,
            file_name="teaching_pariksha_quiz.pdf",
            mime="application/pdf"
        )

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