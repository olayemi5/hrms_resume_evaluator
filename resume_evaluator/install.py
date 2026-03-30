import frappe
from resume_evaluator.api.fields import ensure_settings_doctype, ensure_custom_fields


def after_install():
    """Auto-setup on app install: create settings doctype and custom fields."""
    ensure_settings_doctype()
    ensure_custom_fields()
    frappe.db.commit()
