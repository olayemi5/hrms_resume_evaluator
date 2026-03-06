import frappe
from frappe.utils.password import get_decrypted_password


# ─────────────────────────────────────────────
# Settings helper
# ─────────────────────────────────────────────

def get_settings_name():
    """Get the name of the first Cv Evaluator Settings row."""
    name = frappe.db.get_value("Cv Evaluator Settings", {}, "name")
    if not name:
        print("[CV Evaluator] No Cv Evaluator Settings record found. Please create one.")
    return name


def get_setting(fieldname):
    """Fetch a plain value from Cv Evaluator Settings."""
    name = get_settings_name()
    if not name:
        return None
    return frappe.db.get_value("Cv Evaluator Settings", name, fieldname)


def get_decrypted_key(fieldname):
    """Safely fetch and decrypt a password field from Cv Evaluator Settings."""
    try:
        name = get_settings_name()
        if not name:
            return None
        return get_decrypted_password("Cv Evaluator Settings", name, fieldname)
    except Exception as e:
        print(f"[CV Evaluator] Could not decrypt field '{fieldname}': {e}")
        return None


# ─────────────────────────────────────────────
# Client factory
# ─────────────────────────────────────────────

def get_ai_client():
    """
    Returns a tuple of (client, provider, model) based on
    the selected AI provider in Cv Evaluator Settings.
    Returns (None, None, None) if setup is incomplete.
    """
    provider = get_setting("ai_provider")

    if not provider:
        print(
            "[CV Evaluator] AI provider not set. "
            "Please configure it in Cv Evaluator Settings → AI Provider."
        )
        return None, None, None

    if provider == "OpenAI":
        return _get_openai_client()
    elif provider == "Gemini":
        return _get_gemini_client()
    else:
        print(f"[CV Evaluator] Unknown AI provider: {provider}")
        return None, None, None


def _get_openai_client():
    """Build and return an OpenAI client."""
    from openai import OpenAI

    api_key = get_decrypted_key("openai_bot_key")
    if not api_key or not api_key.strip():
        print(
            "[CV Evaluator] OpenAI API key not set. "
            "Please configure it in Cv Evaluator Settings → OpenAI API Key."
        )
        return None, None, None

    model = get_setting("openai_model") or "gpt-4"
    client = OpenAI(api_key=api_key.strip())
    print(f"[CV Evaluator] Using OpenAI model: {model}")
    return client, "OpenAI", model


def _get_gemini_client():
    """Build and return a Gemini client."""
    import google.generativeai as genai

    api_key = get_decrypted_key("gemini_bot_key")
    if not api_key or not api_key.strip():
        print(
            "[CV Evaluator] Gemini API key not set. "
            "Please configure it in Cv Evaluator Settings → Gemini API Key."
        )
        return None, None, None

    model = get_setting("gemini_model") or "gemini-1.5-pro"
    genai.configure(api_key=api_key.strip())
    client = genai.GenerativeModel(model)
    print(f"[CV Evaluator] Using Gemini model: {model}")
    return client, "Gemini", model
