"""
Robust JSON output parser for local LLMs (Llama, etc.).

Handles common issues with local model output:
- Markdown code fences (```json ... ```)
- JavaScript-style comments (// ...)
- Trailing text after JSON
- Leading/trailing whitespace
"""

import re
import json
import logging
from typing import Type, TypeVar

from langchain_core.output_parsers import BaseOutputParser
from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def clean_llm_json(text: str) -> str:
    """Extract and clean JSON from LLM output that may contain markdown fences, comments, etc."""
    # Strip leading/trailing whitespace
    text = text.strip()

    # Extract content from markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    # Remove single-line comments (// ...) — but not inside strings
    # Simple approach: remove lines that are only comments, and trailing comments
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        # Remove trailing // comments (not inside strings)
        # Find // that's not inside a quoted string
        in_string = False
        escape = False
        comment_pos = None
        for i, ch in enumerate(line):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
            elif ch == "/" and not in_string and i + 1 < len(line) and line[i + 1] == "/":
                comment_pos = i
                break
        if comment_pos is not None:
            line = line[:comment_pos].rstrip()
        if line.strip():  # Keep non-empty lines
            cleaned_lines.append(line)
        elif cleaned_lines:  # Keep blank lines in middle
            cleaned_lines.append(line)

    text = "\n".join(cleaned_lines).strip()

    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)

    return text


def _describe_schema(schema: dict, defs: dict, indent: int = 0) -> str:
    """Recursively render a JSON schema as a human-readable structure for LLM prompts."""
    # Resolve $ref
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return _describe_schema(defs.get(ref_name, {}), defs, indent)

    s_type = schema.get("type", "")

    if s_type == "object":
        props = schema.get("properties", {})
        required = schema.get("required", [])
        pad = "  " * (indent + 1)
        close_pad = "  " * indent
        items = []
        for name, prop in props.items():
            req = " (required)" if name in required else " (optional)"
            items.append(f'{pad}"{name}": {_describe_schema(prop, defs, indent + 1)}{req}')
        return "{\n" + ",\n".join(items) + "\n" + close_pad + "}"

    if s_type == "array":
        item_desc = _describe_schema(schema.get("items", {}), defs, indent)
        return f"[{item_desc}, ...]"

    return s_type or "any"


def _coerce_schema_types(data: dict, schema: dict, defs: dict) -> dict:
    """
    Recursively coerce data values to match schema types.

    Handles the common local-LLM mistake of returning a plain string where
    the schema expects an array (list), e.g.::

        "coverage_goals": "Cover the login happy path"
        →
        "coverage_goals": ["Cover the login happy path"]
    """
    if not isinstance(data, dict):
        return data

    props = schema.get("properties", {})

    for key, val in list(data.items()):
        if key not in props:
            continue

        prop = props[key]

        # Resolve $ref to get the real schema
        if "$ref" in prop:
            ref_name = prop["$ref"].split("/")[-1]
            ref_schema = defs.get(ref_name, {})
            if isinstance(val, dict):
                data[key] = _coerce_schema_types(val, {**ref_schema, "$defs": defs}, defs)
            continue

        prop_type = prop.get("type")

        if prop_type == "array" and isinstance(val, str):
            # Split on semicolons, newlines, or wrap as single item
            if ";" in val:
                data[key] = [item.strip() for item in val.split(";") if item.strip()]
            elif "\n" in val:
                data[key] = [item.strip().lstrip("-•* ").strip() for item in val.split("\n") if item.strip()]
            else:
                data[key] = [val] if val else []
            logger.debug("Coerced string→list for field '%s': %s", key, data[key])

        elif prop_type == "object" and isinstance(val, dict):
            data[key] = _coerce_schema_types(val, {**prop, "$defs": defs}, defs)

    return data


class RobustPydanticOutputParser(BaseOutputParser[T]):
    """Output parser that handles messy LLM JSON output and parses into a Pydantic model."""

    pydantic_model: Type[T]

    class Config:
        arbitrary_types_allowed = True

    def get_format_instructions(self) -> str:
        schema = self.pydantic_model.model_json_schema()
        defs = schema.get("$defs", {})
        structure = _describe_schema(schema, defs)
        return (
            "You must respond with ONLY valid JSON, no additional text, no markdown code fences, no comments.\n"
            "Every field typed as an array MUST be a JSON array (use [] for empty), never a plain string.\n"
            "The JSON must match this exact structure:\n"
            + structure
        )

    def parse(self, text: str) -> T:
        # If it's an AIMessage, get the content
        if hasattr(text, "content"):
            text = text.content

        cleaned = clean_llm_json(str(text))

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.warning("JSON parse failed, attempting to extract JSON object: %s", str(e))
            # Try to find a JSON object in the text
            obj_match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", cleaned, re.DOTALL)
            if obj_match:
                try:
                    data = json.loads(obj_match.group())
                except json.JSONDecodeError:
                    raise ValueError(
                        f"Could not parse JSON from LLM output. Cleaned text:\n{cleaned[:500]}"
                    )
            else:
                raise ValueError(
                    f"No JSON object found in LLM output. Cleaned text:\n{cleaned[:500]}"
                )

        # Coerce types before validation (handles string→list mismatches from local LLMs)
        schema = self.pydantic_model.model_json_schema()
        defs = schema.get("$defs", {})
        data = _coerce_schema_types(data, schema, defs)

        return self.pydantic_model.model_validate(data)
