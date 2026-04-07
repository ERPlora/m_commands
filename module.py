"""
Commands Module Configuration

Production command management for kitchens, workshops, bakeries, and factories.
Tracks items through preparation stations with real-time status updates.
"""


# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "commands"
MODULE_NAME = "Commands"
MODULE_VERSION = "2.1.0"
MODULE_ICON = "clipboard-outline"
MODULE_DESCRIPTION = "Production commands — kitchens, workshops, bakeries, factories"
MODULE_AUTHOR = "ERPlora"
MODULE_CATEGORY = "pos"

# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------
HAS_MODELS = True
MIDDLEWARE = ""

MODULE_INDUSTRIES = ["restaurant", "bar", "cafe", "fast_food", "catering"]

# ---------------------------------------------------------------------------
# Menu (sidebar entry)
# ---------------------------------------------------------------------------
MENU = {
    "label": "Commands",
    "icon": "clipboard-outline",
    "order": 45,
    "show": True,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": "Overview", "icon": "grid-outline", "view": ""},
    {"id": "active", "label": "Active", "icon": "time-outline", "view": "active"},
    {"id": "history", "label": "History", "icon": "archive-outline", "view": "history"},
    {"id": "settings", "label": "Settings", "icon": "settings-outline", "view": "settings"},
]

# ---------------------------------------------------------------------------
# Dependencies (other modules required to be active)
# ---------------------------------------------------------------------------
DEPENDENCIES = ["tables", "sales", "customers", "inventory"]

# ---------------------------------------------------------------------------
# Settings (default values)
# ---------------------------------------------------------------------------
SETTINGS = {
    "auto_accept_orders": True,
    "default_prep_time": 15,
    "notify_kitchen": True,
}

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
PERMISSIONS = [
    ("view_order", "Can view commands"),
    ("add_order", "Can add commands"),
    ("change_order", "Can change commands"),
    ("delete_order", "Can delete commands"),
    ("cancel_order", "Can cancel commands"),
    ("complete_order", "Can complete commands"),
    ("view_history", "Can view command history"),
    ("view_settings", "Can view settings"),
    ("change_settings", "Can change settings"),
    ("manage_settings", "Can manage commands settings"),
]

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "manager": [
        "view_order", "add_order", "change_order", "delete_order",
        "cancel_order", "complete_order", "view_history", "view_settings",
    ],
    "employee": ["view_order", "add_order", "complete_order"],
}

# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------
SCHEDULED_TASKS: list[dict] = []
