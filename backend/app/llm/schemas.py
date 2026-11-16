"""Pydantic schemas for everything the LLM returns.

The JSON Schema sent to the API is generated from these models (see `strict_json_schema`),
and every response is validated against the same model in code.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Experience(_Strict):
    title: str
    company: str
    period: str | None = None
    activities: list[str] = Field(default_factory=list)


class SkillCategory(_Strict):
    category: str
    items: list[str] = Field(default_factory=list)


class Project(_Strict):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    link: str | None = None


class Education(_Strict):
    institution: str
    degree: str | None = None
    period: str | None = None


class Certification(_Strict):
    name: str
    issuer: str | None = None
    year: str | None = None


class Language(_Strict):
    language: str
    level: str | None = None


class ProfileData(_Strict):
    summary: str | None = None
    experiences: list[Experience] = Field(default_factory=list)
    skills: list[SkillCategory] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema for structured outputs: every object closed and every property required.

    Optional values stay expressible as `null` (anyOf with null), so the model is never
    pushed to fill a field it has no information for.
    """
    schema = model.model_json_schema()

    def walk(node: Any) -> None:
        """`node` is always a schema node, never a name->schema mapping."""
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if not isinstance(node, dict):
            return
        node.pop("title", None)  # pydantic metadata, not a field
        node.pop("default", None)
        if "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"])
            for prop_schema in node["properties"].values():
                walk(prop_schema)
        for key in ("$defs",):
            for sub in node.get(key, {}).values():
                walk(sub)
        for key in ("items", "anyOf"):
            if key in node:
                walk(node[key])

    walk(schema)
    return schema
