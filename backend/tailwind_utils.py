import re

def infer_tailwind_group(cls: str):
    groups = {
        "background": r"^(bg-|from-|via-|to-)",
        "text-size": r"^text-(xs|sm|base|lg|xl|\d?xl)$",
        "text-color": r"^text-(?!xs|sm|base|lg|xl|\d?xl)[a-z]+-\d{3}$",
        "padding": r"^p[trblxy]?-\d+$",
        "margin": r"^m[trblxy]?-\d+$",
        "rounded": r"^rounded",
        "border-width": r"^border(-\d+)?$",
        "width": r"^w-",
        "height": r"^h-"
    }

    for name, pattern in groups.items():
        if re.match(pattern, cls):
            return name

    return None
