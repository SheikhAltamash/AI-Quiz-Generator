"""
Gemini API Key Manager with Fast Failover System
- Prioritizes switching keys immediately on failure
- Tries all models for a key before switching to the next key
- No waiting or sleep times
"""

from google import genai
import os
from typing import Optional, List, Tuple
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeminiAPIManager:
    """
    Manages multiple Gemini API keys with immediate failover.
    
    Strategy:
    1. Select Key N
    2. Try Model A -> B -> C -> D
    3. If all models fail for Key N, move to Key N+1
    4. If all keys fail, raise Exception
    5. No waiting/sleeping for rate limits (fail fast)
    """
    
    # Model priority list (fallback order)
    MODEL_PRIORITY = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash-lite",
    ]
    
    def __init__(self):
        self.api_keys: List[str] = self._load_api_keys()
        
    def _load_api_keys(self) -> List[str]:
        """Load API keys from environment variable or config file."""
        keys = []
        
        # Load 20 API keys from environment variables
        # Supports both formats: GEMINI_API_KEY_X and GOOGLE_API_KEY_X
        for i in range(1, 21):
            # Try GEMINI format first
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            # Fallback to GOOGLE format
            if not key:
                key = os.getenv(f"GOOGLE_API_KEY_{i}")
            if key:
                keys.append(key)
        
        # Also load from a single GEMINI_API_KEYS environment variable (comma-separated)
        bulk_keys = os.getenv("GEMINI_API_KEYS", "")
        if bulk_keys:
            keys.extend([k.strip() for k in bulk_keys.split(",") if k.strip()])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keys = []
        for key in keys:
            if key not in seen:
                seen.add(key)
                unique_keys.append(key)
        
        logger.info(f"Loaded {len(unique_keys)} API keys")
        return unique_keys
    
    def generate_content(self, prompt: str) -> Tuple[str, str]:
        """
        Generate content by iterating through Keys and Models.
        
        Args:
            prompt: The prompt to send to the model
            
        Returns:
            Tuple of (response_text, model_used)
            
        Raises:
            Exception: If all keys and models fail
        """
        if not self.api_keys:
            raise Exception("No API keys found. Please check your .env file.")

        last_error = None
        
        # Outer Loop: Iterate through all available API Keys
        for i, api_key in enumerate(self.api_keys):
            key_preview = f"...{api_key[-4:]}" if len(api_key) > 4 else "Unknown"
            msg_key = f"\n🔑 [DEBUG] Trying API Key {i+1}/{len(self.api_keys)} (Ends with {key_preview})"
            print(msg_key)
            logger.info(msg_key)
            
            client = genai.Client(api_key=api_key)
            
            # Inner Loop: Iterate through all Models for this Key
            for model in self.MODEL_PRIORITY:
                try:
                    msg_model = f"   🤖 [DEBUG] Attempting model: {model}"
                    print(msg_model)
                    logger.info(msg_model)
                    
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt
                    )
                    
                    # If we get here, it worked!
                    success_msg = f"   ✅ [SUCCESS] Generated content using Key {i+1} and Model {model}"
                    print(success_msg)
                    logger.info(success_msg)
                    return response.text, model
                    
                except Exception as e:
                    # Capture error and continue immediately to next model
                    last_error = e
                    error_msg = str(e).lower()
                    fail_msg = f"   ❌ [FAILED] Key {i+1} + {model}: {error_msg[:100]}..." # Truncate error for readability
                    print(fail_msg)
                    logger.warning(fail_msg)
                    
                    # Add a small delay before retrying the next model to avoid spamming
                    time.sleep(2) 
                    # Continue to next model
            
            # If we are here, all models failed for this key. Move to next key.
            print(f"   ⚠️ [WARNING] All models failed for Key {i+1}. Switching to next key.")
            time.sleep(1) # Small pause before switching keys

        # If we exit the loops, everything failed
        logger.error("All API keys and models exhausted.")
        raise Exception(f"Unable to fetch response. All {len(self.api_keys)} keys and models failed. Last error: {last_error}")
    
    def get_status(self) -> dict:
        """Get the current status (static info for UI)."""
        return {
            "total_keys": len(self.api_keys),
            "available_models": self.MODEL_PRIORITY,
            # Legacy fields for compatibility with app.py
            "failed_keys": 0, 
            "current_model": "Auto-switching",
            "current_model_index": 0,
        }
    
    def reset(self):
        """Reset is not needed in the new stateless approach, but kept for compatibility."""
        pass


# Global instance for easy access
_api_manager: Optional[GeminiAPIManager] = None


def get_api_manager() -> GeminiAPIManager:
    """Get the global API manager instance."""
    global _api_manager
    if _api_manager is None:
        _api_manager = GeminiAPIManager()
    return _api_manager

