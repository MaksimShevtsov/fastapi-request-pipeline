"""OpenAPI schema enrichment — collects metadata from flow components."""

from __future__ import annotations

from typing import Any

from fastapi_request_pipeline.flow import ResolvedFlow


def collect_openapi_metadata(resolved: ResolvedFlow) -> dict[str, Any]:
    """Collect and merge OpenAPI metadata from all resolved components."""
    security_schemes: dict[str, Any] = {}
    security: list[dict[str, list[str]]] = []
    responses: dict[str, Any] = {}
    parameters: list[dict[str, Any]] = []
    extensions: dict[str, list[str]] = {}

    for component in resolved.components:
        spec = component.openapi_spec()
        if spec is None:
            continue

        if "security_schemes" in spec:
            security_schemes.update(spec["security_schemes"])
        if "security" in spec:
            for sec in spec["security"]:
                if sec not in security:
                    security.append(sec)
        if "responses" in spec:
            responses.update(spec["responses"])
        if "parameters" in spec:
            parameters.extend(spec["parameters"])

        # Collect vendor extensions (x-permissions, x-roles, etc.)
        for key, value in spec.items():
            if key.startswith("x-") and isinstance(value, list):
                extensions.setdefault(key, []).extend(value)

    result: dict[str, Any] = {}
    if security_schemes:
        result["security_schemes"] = security_schemes
    if security:
        result["security"] = security
    if responses:
        result["responses"] = responses
    if parameters:
        result["parameters"] = parameters
    if extensions:
        result.update(extensions)

    return result
