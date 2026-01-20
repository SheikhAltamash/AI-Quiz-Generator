"""
Audio Transcriber Module
- Downloads audio from YouTube using yt-dlp
- Transcribes audio using Groq's Whisper model (distil-whisper-large-v3-en)
"""

import os
import yt_dlp
import logging
from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_groq_client():
    """Get Groq client."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment variables.")
    return Groq(api_key=api_key)

def download_audio(video_url, output_path="temp_audio", proxy=None, cookies_path=None):
    """
    Download audio from YouTube video using yt-dlp.
    Returns the path to the downloaded file.
    """
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '64', # Low quality is fine for speech, saves size
            }],
            'outtmpl': f'{output_path}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
        }

        # Add Proxy if provided
        if proxy:
            ydl_opts['proxy'] = proxy
            logger.info(f"Using Proxy: {proxy}")

        # Add Cookies if provided
        if cookies_path and os.path.exists(cookies_path):
            ydl_opts['cookiefile'] = cookies_path
            logger.info(f"Using Cookies: {cookies_path}")

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Downloading audio from {video_url}...")
            ydl.download([video_url])
            
        # The file will be named temp_audio.mp3
        final_path = f"{output_path}.mp3"
        
        if os.path.exists(final_path):
            return final_path
        else:
            raise Exception("Audio file not found after download.")
            
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        raise e

# ... transcribe_audio function remains same ...

def get_video_script(video_url, proxy=None, cookies_path=None):
    """
    Main function to get script from YouTube URL.
    """
    # Use a unique filename
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    temp_filename = f"temp_{unique_id}"
    
    try:
        audio_path = download_audio(video_url, temp_filename, proxy, cookies_path)
        text = transcribe_audio(audio_path)
        return text
    except Exception as e:
        logger.error(f"Workflow failed: {e}")
        return None
