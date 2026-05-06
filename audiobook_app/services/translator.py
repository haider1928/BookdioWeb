import os
import time
import groq
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

GROQ_MODEL = "llama-3.1-8b-instant"

_api_keys: list[str] = []
_current_key_index = 0
_key_cooldowns: dict[int, float] = {}
_key_rotation_locked = False

_URDU_TRANSLATION_PROMPT = """Translate the following English text to natural Urdu Nastaliq script.
Maintain literary style, keep context in mind from previous paragraphs.
Output ONLY the Urdu translation - no English, no explanations.
Previous context:
{context}

English text to translate:
{text}"""


def _get_api_keys() -> list[str]:
    global _api_keys
    if not _api_keys:
        keys_str = os.getenv("GROQ_API_KEYS", "")
        if keys_str:
            _api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
        if not _api_keys:
            print("[Translator] Warning: No Groq API keys found in .env")
    return _api_keys


def _get_next_available_key() -> Optional[str]:
    global _current_key_index, _key_cooldowns, _key_rotation_locked
    keys = _get_api_keys()
    if not keys:
        return None
    
    if _key_rotation_locked:
        return None
    
    current_time = time.time()
    checked = 0
    start_index = _current_key_index
    
    while checked < len(keys):
        if _current_key_index not in _key_cooldowns or current_time >= _key_cooldowns[_current_key_index]:
            key = keys[_current_key_index]
            _current_key_index = (_current_key_index + 1) % len(keys)
            return key
        
        checked += 1
        _current_key_index = (_current_key_index + 1) % len(keys)
        
        if _current_key_index == start_index:
            break
    
    return None


def _mark_key_cooldown(key_index: int, retry_after: int = 60):
    global _key_cooldowns
    _key_cooldowns[key_index] = time.time() + retry_after
    print(f"[Translator] Key {key_index} hitting rate limit, cooling down for {retry_after}s")


def translate_to_urdu(text: str, context_window: list[str] | None = None) -> Optional[str]:
    global _key_rotation_locked
    
    keys = _get_api_keys()
    if not keys:
        print("[Translator] No API keys available")
        return None
    
    print(f"[Translator] Translating {len(text)} chars, context: {len(context_window) if context_window else 0} sentences")
    
    context_str = "\n".join(context_window[-3:]) if context_window else ""
    prompt = _URDU_TRANSLATION_PROMPT.format(
        context=context_str if context_str else "(No previous context)",
        text=text
    )
    
    attempts = 0
    max_attempts = len(keys) * 2
    
    while attempts < max_attempts:
        time.sleep(2)
        
        api_key = _get_next_available_key()
        if not api_key:
            print("[Translator] All keys in cooldown, waiting...")
            time.sleep(5)
            attempts += 1
            continue
        
        key_index = _current_key_index - 1 if _current_key_index > 0 else len(keys) - 1
        
        result = None
        try:
            client = groq.Groq(api_key=api_key)
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional English to Urdu translator. Translate to natural, literary Urdu Nastaliq script. Output ONLY Urdu text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4096
            )
            result = response.choices[0].message.content.strip()
            
        except groq.RateLimitError as e:
            print(f"[Translator] Rate limit on key {key_index}: {e}")
            _mark_key_cooldown(key_index, 60)
            attempts += 1
            continue
            
        except Exception as e:
            print(f"[Translator] Error on key {key_index}: {e}")
            attempts += 1
            continue
        
        if result:
            status = result[:100]
            print(f"[Translator] Translated successfully (length: {len(status)})...")
        else:
            status = 'None'
            print(f"[Translator] Translation failed")
        return result
    
    print("[Translator] Failed after all retry attempts")
    return None


def translate_batch(texts: list[str], context_window: list[str] | None = None) -> list[Optional[str]]:
    results = []
    context = context_window.copy() if context_window else []
    
    for text in texts:
        result = translate_to_urdu(text, context)
        results.append(result)
        context.append(text if result else text)
    
    return results
