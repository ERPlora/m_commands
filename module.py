"""
Commands Module Configuration

Production command management for kitchens, workshops, bakeries, and factories.
Tracks items through preparation stations with real-time status updates.
"""

from app.core.i18n import LazyString

# ---------------------------------------------------------------------------
# Module identity
# ---------------------------------------------------------------------------
MODULE_ID = "commands"
MODULE_NAME = LazyString("Commands", module_id="commands")
MODULE_VERSION = "2.0.0"
MODULE_ICON = "clipboard-outline"
MODULE_DESCRIPTION = LazyString(
    "Production commands — kitchens, workshops, bakeries, factories",
    module_id="commands",
)
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
    "label": LazyString("Commands", module_id="commands"),
    "icon": "clipboard-outline",
    "order": 45,
    "show": True,
}

# ---------------------------------------------------------------------------
# Navigation tabs (bottom tabbar in module views)
# ---------------------------------------------------------------------------
NAVIGATION = [
    {"id": "dashboard", "label": LazyString("Overview", module_id="commands"), "icon": "grid-outline", "view": ""},
    {"id": "active", "label": LazyString("Active", module_id="commands"), "icon": "time-outline", "view": "active"},
    {"id": "history", "label": LazyString("History", module_id="commands"), "icon": "archive-outline", "view": "history"},
    {"id": "settings", "label": LazyString("Settings", module_id="commands"), "icon": "settings-outline", "view": "settings"},
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
    ("view_order", LazyString("Can view commands", module_id="commands")),
    ("add_order", LazyString("Can add commands", module_id="commands")),
    ("change_order", LazyString("Can change commands", module_id="commands")),
    ("delete_order", LazyString("Can delete commands", module_id="commands")),
    ("cancel_order", LazyString("Can cancel commands", module_id="commands")),
    ("complete_order", LazyString("Can complete commands", module_id="commands")),
    ("view_history", LazyString("Can view command history", module_id="commands")),
    ("view_settings", LazyString("Can view settings", module_id="commands")),
    ("change_settings", LazyString("Can change settings", module_id="commands")),
    ("manage_settings", LazyString("Can manage commands settings", module_id="commands")),
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
