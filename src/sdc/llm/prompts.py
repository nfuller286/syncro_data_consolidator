from __future__ import annotations
# -*- coding: utf-8 -*-
"""Functions for building structured LLM prompts."""

import json
import re
from typing import Optional, Dict, Any, List
from langchain_core.messages import SystemMessage, HumanMessage
from sdc.models.session_v2 import Session

def _get_value_from_path(obj: Any, path: str) -> Any:
    """Safely gets a value from a nested object using a dot-separated path."""
    for key in path.split('.'):
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            obj = getattr(obj, key, None)
        if obj is None:
            return None
    return obj

def _split_outside_parens(text: str, delimiter: str) -> List[str]:
    """Splits a string by a delimiter, but ignores delimiters inside parentheses."""
    parts = []
    balance = 0
    last_split = 0
    for i, char in enumerate(text):
        if char == '(':
            balance += 1
        elif char == ')':
            balance -= 1
        elif char == delimiter and balance == 0:
            parts.append(text[last_split:i])
            last_split = i + 1
    parts.append(text[last_split:])
    return parts

def _process_placeholder(placeholder: str, session: Optional[Session], logger, **kwargs) -> str:
    """Helper to process the content of a single placeholder."""
    parts = _split_outside_parens(placeholder.strip(), ':')
    path = parts[0]
    
    # Determine the data source: session object or kwargs
    if path.startswith('session.') and session:
        data_source = session
        value_path = path.split('session.', 1)[1]
    else:
        data_source = kwargs
        value_path = path

    value = _get_value_from_path(data_source, value_path)

    if value is None:
        return "" # Return empty string for missing values

    if isinstance(value, list) and len(parts) > 1:
        # Handle list formatting directives, e.g., :each(...):join(...)
        item_template = "{item}"
        join_char = "\n"
        for directive in parts[1:]:
            if directive.startswith("each("):
                item_template = directive[5:-1]
            elif directive.startswith("join("):
                join_char = directive[5:-1].encode().decode('unicode_escape') # Handle \n, \t etc.
        
        # Recursively format each item in the list.
        # Pass the item itself as kwargs for the next level of formatting.
        formatted_items = [_format_prompt_string(item_template, None, logger, **(item.model_dump() if hasattr(item, 'model_dump') else item)) for item in value]
        return join_char.join(formatted_items)

    if isinstance(value, list):
        # Default list formatting if no directives are provided
        return json.dumps(value, indent=2)

    return str(value)

def _format_prompt_string(template: str, session: Optional[Session], logger, **kwargs) -> str:
    """Replaces placeholders in a template string with data from a Session object or kwargs."""
    output = []
    last_index = 0
    i = 0
    while i < len(template):
        if template[i] == '{':
            output.append(template[last_index:i])
            
            # Find the matching '}' brace, respecting nested braces
            balance = 1
            j = i + 1
            while j < len(template):
                if template[j] == '{':
                    balance += 1
                elif template[j] == '}':
                    balance -= 1
                
                if balance == 0:
                    break
                j += 1
            
            if balance != 0:
                logger.error(f"Mismatched braces in prompt template starting at index {i}: '{template[i:i+20]}...'")
                output.append(template[i:])
                break

            placeholder = template[i+1:j]
            value_str = _process_placeholder(placeholder, session, logger, **kwargs)
            output.append(value_str)
            
            i = j + 1
            last_index = i
        else:
            i += 1
    
    if last_index < len(template):
        output.append(template[last_index:])
        
    return "".join(output)

def build_prompt_messages(prompt_key: str, config: Dict[str, Any], logger, session: Optional[Session] = None, **kwargs) -> Optional[List[HumanMessage | SystemMessage]]:
    """
    Builds a structured list of messages for an LLM call.

    This function reads a prompt template from the config file using a key.
    It formats the template by replacing placeholders with data from the `session`
    object or other provided kwargs.

    Args:
        prompt_key: A dot-separated key to find the prompt in the config (e.g., 'disambiguation').
        config: The application's configuration dictionary.
        logger: The SDC logger instance.
        session: An optional Session object to use as a data source for placeholders.
        **kwargs: The values to format into the prompt template(s).

    Returns:
        A list of LangChain message objects, or None on failure.
    """
    try:
        prompt_template = config.get('llm_configs', {}).get('prompts', {})
        for key in prompt_key.split('.'):
            prompt_template = prompt_template[key]

        if isinstance(prompt_template, str):
            content = _format_prompt_string(prompt_template, session, logger, **kwargs)
            return [HumanMessage(content=content)]
        elif isinstance(prompt_template, dict):
            system_prompt = _format_prompt_string(prompt_template['system'], session, logger, **kwargs)
            user_prompt = _format_prompt_string(prompt_template['user'], session, logger, **kwargs)
            return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        else:
            logger.error(f"Unsupported prompt format for key '{prompt_key}'. Must be a string or a dict.")
            return None
    except KeyError as e:
        logger.error(f"Could not find required prompt template key in config: 'llm_configs.prompts.{prompt_key}' (missing key: {e})")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while building prompt for key '{prompt_key}': {e}")
        return None
