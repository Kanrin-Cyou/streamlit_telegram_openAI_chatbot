from typing import Callable, Optional

# Registry for storing only the function schemas
REGISTERED_TOOLS: dict[str, Callable] = {}

# Registry for storing the wrappers (with type/function)
REGISTERED_TOOL_DESCRIPTIONS = []

TOOL_DISPLAY: dict[str, str] = {}

def tool(name: str,
         description: str,
         parameters: dict,
         strict: bool = False,
         display_name: Optional[str] = None,
        ):
    """
    Decorator:
      1) Attach __tool_meta__ to the function
      2) Add the function object to REGISTERED_TOOLS
      3) Add the wrapped dict to REGISTERED_TOOL_DESCRIPTIONS
    """
    def deco(func):
        meta = {
            "name":        name,
            "description": description,
            "parameters":  parameters,
            "strict":      strict
        }
        # Attach metadata to the function object (for later use)
        func.__tool_meta__ = meta

        # Register the pure schema
        REGISTERED_TOOLS[name] = func
        # Register the wrapped item (with type/function)
        REGISTERED_TOOL_DESCRIPTIONS.append({
            "type":        "function",
            "name":        name,
            "description": description,
            "parameters":  parameters,
            "strict":      strict
        })
        TOOL_DISPLAY[name] = display_name or name
        return func
    return deco