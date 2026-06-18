import logging
import random
from google.api_core.exceptions import ResourceExhausted
import google.generativeai as genai

from app.config import settings
from app.utils.exceptions import ServiceException

logger = logging.getLogger("app")

# Global state to keep track of the current key index
_current_key_index = 0

def _get_api_keys() -> list[str]:
    """Parse all available Gemini API keys from settings."""
    keys = []
    # If the user provided a comma-separated list of keys
    if hasattr(settings, "gemini_api_keys") and settings.gemini_api_keys:
        keys = [k.strip() for k in settings.gemini_api_keys.split(",") if k.strip()]
    
    # Fallback to single key if list is empty
    if not keys and settings.gemini_api_key:
        keys = [settings.gemini_api_key.strip()]
        
    return keys

async def call_gemini_api_with_rotation(prompt: str, system_prompt: str) -> str:
    """
    Call Gemini API and automatically rotate to the next API key 
    if a Rate Limit (ResourceExhausted 429) error occurs.
    """
    global _current_key_index
    keys = _get_api_keys()
    
    if not keys:
        raise ServiceException("No Gemini API keys configured. Please add them to your .env file.")

    attempts = 0
    max_attempts = len(keys)
    
    while attempts < max_attempts:
        current_key = keys[_current_key_index]
        genai.configure(api_key=current_key)
        
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=system_prompt
        )
        
        try:
            response = await model.generate_content_async(prompt)
            return response.text
            
        except ResourceExhausted as e:
            logger.warning(f"Key {_current_key_index + 1}/{len(keys)} hit rate limit. Rotating to next key...")
            # Move to the next key in the list
            _current_key_index = (_current_key_index + 1) % len(keys)
            attempts += 1
            
        except Exception as e:
            # For any other error (like bad prompt, disconnected), fail immediately
            logger.error(f"Gemini API Error: {e}", exc_info=True)
            raise ServiceException(f"Gemini API failed: {str(e)}")

    # If we tried all keys and all of them are exhausted
    logger.warning("All Gemini API keys exhausted. Falling back to Groq API...")
    try:
        import httpx
        import os
        groq_api_key = os.getenv("GROQ_API_KEY", "fallback_key_here")
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        async with httpx.AsyncClient() as client:
            res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=60.0)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"]
    except Exception as groq_err:
        logger.error(f"Groq API Fallback Error: {groq_err}", exc_info=True)
        raise ServiceException("All Gemini API keys are currently rate-limited, and the Groq fallback failed. Please wait or add more keys to your .env file.")
