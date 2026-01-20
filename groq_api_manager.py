"""
Groq API Key Manager
- Handles connections to Groq API
- Supports model verification and simple failover
- Returns response in compatible format for existing app
"""

import os
from groq import Groq
from typing import Optional, List, Tuple
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GroqAPIManager:
    """
    Manages Groq API interactions.
    """
    
    # Model priority list
    # We prioritize 70b (versatile) for quality, then 8b (instant) for speed/backup
    MODEL_PRIORITY = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]
    
    def __init__(self):
        self.api_key = self._load_api_key()
        self.client = None
        if self.api_key:
            self.client = Groq(api_key=self.api_key)
        
    def _load_api_key(self) -> Optional[str]:
        """Load API key from environment variable."""
        # Try specific GROQ key first
        key = os.getenv("GROQ_API_KEY")
        
        if not key:
            # Fallback or check for list if user put it there
            # For now, we assume a single key mostly, but we can support multiple if needed later
            pass
            
        if key:
            logger.info("✅ Groq API Key found.")
        else:
            logger.warning("⚠️ GROQ_API_KEY not found in environment variables.")
            
        return key

    def generate_content(self, prompt: str) -> Tuple[str, str]:
        """
        Generate content using Groq.
        
        Args:
            prompt: The prompt to send to the model
            
        Returns:
            Tuple of (response_text, model_used)
            
        Raises:
            Exception: If generation fails
        """
        if not self.client:
            raise Exception("Groq Client not initialized. Check if GROQ_API_KEY is set in .env")

        last_error = None
        
        # Iterate through models in priority
        for model in self.MODEL_PRIORITY:
            try:
                # msg_model = f"   🤖 [Groq] Attempting model: {model}"
                # print(msg_model) # Optional: reduce console spam
                
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=model,
                    temperature=0.7, # Adjustable
                )
                
                response_text = chat_completion.choices[0].message.content
                
                # Success
                logger.info(f"✅ [SUCCESS] Generated with Groq model: {model}")
                return response_text, model
                
            except Exception as e:
                last_error = e
                logger.warning(f"   ❌ [FAILED] Groq Model {model}: {str(e)[:100]}...")
                # Try next model
                try: 
                   # simple check if it is a rate limit error, maybe wait a tiny bit?
                   # usually Groq 429s are immediate, so switching model is good
                   pass
                except:
                   pass

        # If we get here, all models failed
        raise Exception(f"Unable to fetch response from Groq. Last error: {last_error}")

    def get_status(self) -> dict:
        """Get the current status (static info for UI)."""
        return {
            "provider": "Groq",
            "available_models": self.MODEL_PRIORITY,
            "current_key_status": "Active" if self.client else "Missing"
        }

# Global instance
_api_manager: Optional[GroqAPIManager] = None

def get_api_manager() -> GroqAPIManager:
    """Get the global API manager instance."""
    global _api_manager
    if _api_manager is None:
        _api_manager = GroqAPIManager()
    return _api_manager
