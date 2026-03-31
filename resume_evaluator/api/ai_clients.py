import frappe
from frappe.utils.password import get_decrypted_password

LOG_TITLE = "CV Evaluator"


def _log():
    return frappe.logger(LOG_TITLE, allow_site=True)


# ─────────────────────────────────────────────
# Settings helper
# ─────────────────────────────────────────────

def get_settings_name():
    name = frappe.db.get_value("Cv Evaluator Settings", {}, "name")
    if not name:
        _log().warning("No Cv Evaluator Settings record found. Please create one.")
    return name


def get_setting(fieldname):
    name = get_settings_name()
    if not name:
        return None
    return frappe.db.get_value("Cv Evaluator Settings", name, fieldname)


def get_decrypted_key(fieldname):
    try:
        name = get_settings_name()
        if not name:
            return None
        return get_decrypted_password("Cv Evaluator Settings", name, fieldname)
    except Exception as e:
        _log().error(f"Could not decrypt field '{fieldname}': {e}")
        return None


# ─────────────────────────────────────────────
# Client factory
# ─────────────────────────────────────────────

def get_ai_client():
    provider = get_setting("ai_provider")

    if not provider:
        _log().warning("AI provider not set. Configure in Cv Evaluator Settings.")
        return None, None, None

    if provider == "OpenAI":
        return _get_openai_client()
    elif provider == "Gemini":
        return _get_gemini_client()
    else:
        _log().error(f"Unknown AI provider: {provider}")
        return None, None, None


def _get_openai_client():
    from openai import OpenAI

    api_key = get_decrypted_key("openai_bot_key")
    if not api_key or not api_key.strip():
        _log().warning("OpenAI API key not set. Configure in Cv Evaluator Settings.")
        return None, None, None

    model = get_setting("openai_model") or "gpt-4"
    client = OpenAI(api_key=api_key.strip())
    _log().info(f"Initialized OpenAI client — model: {model}")
    return client, "OpenAI", model


def _get_gemini_client():
    import google.generativeai as genai

    api_key = get_decrypted_key("gemini_bot_key")
    if not api_key or not api_key.strip():
        _log().warning("Gemini API key not set. Configure in Cv Evaluator Settings.")
        return None, None, None

    model = get_setting("gemini_model") or "gemini-1.5-pro"
    genai.configure(api_key=api_key.strip())
    client = genai.GenerativeModel(model)
    _log().info(f"Initialized Gemini client — model: {model}")
    return client, "Gemini", model
