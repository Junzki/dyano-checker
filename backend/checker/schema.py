from typing import Any

# Only PDF is supported for now; the accept value is uniform so the browser
# restricts the picker to PDFs while non-PDF kinds still render as PDF inputs.
PDF_ACCEPT = "application/pdf,.pdf"


def parse_ruleset(data: dict[str, Any]) -> dict[str, Any]:
    categories: list[dict[str, Any]] = []
    for category_index, category in enumerate(data.get("check-requirements", [])):
        file_requirements: list[dict[str, Any]] = []
        for req_index, req in enumerate(category.get("file-requirements", [])):
            key = f"{category_index}-{req_index}"
            file_requirements.append(
                {
                    "key": key,
                    "name": req.get("name", ""),
                    "description": req.get("description", ""),
                    "kind": req.get("kind", "PDF"),
                    "accept": PDF_ACCEPT,
                }
            )
        categories.append(
            {
                "name": category.get("name", ""),
                "file_requirements": file_requirements,
            }
        )
    return {"categories": categories}


def build_requirement_map(schema: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Map requirement key -> {category_name, requirement_name} for uploads."""
    mapping: dict[str, dict[str, str]] = {}
    for category in schema.get("categories", []):
        for req in category.get("file_requirements", []):
            mapping[req["key"]] = {
                "category_name": category.get("name", ""),
                "requirement_name": req.get("name", ""),
            }
    return mapping
