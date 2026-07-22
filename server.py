"""stat-gov-mcp — MCP server for GUS Bank Danych Lokalnych (BDL) public API.

Wraps https://bdl.stat.gov.pl/api/v1/ — the Polish Central Statistical
Office's public REST API for Local Data Bank. No authentication required
for the free tier (5 req/sec, ~5000 req/day). Data flows only between your
machine and GUS.

Primary use case: research and reporting on Polish socioeconomic data —
population, prices, business demographics, unemployment — at the country /
voivodeship / powiat / gmina level.

Tools: search_subjects, search_variables, search_units, get_data,
get_unit_details.

Author: Bartosz Kuć <firma@bartosza.pl>
Repo:   https://github.com/bartosz-kuc/stat-gov-mcp
License: MIT
"""

import asyncio
import json
from typing import Any

import requests

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

BDL_BASE = "https://bdl.stat.gov.pl/api/v1"

LEVEL_LABELS = {
    0: "Kraj",
    1: "Makroregion",
    2: "Województwo",
    3: "Region",
    4: "Podregion",
    5: "Powiat",
    6: "Gmina",
    7: "Sub-gmina (dzielnica/miejscowość)",
}


def _get(path: str, params: dict | None = None) -> dict:
    p = {"format": "json"}
    if params:
        p.update(params)
    resp = requests.get(f"{BDL_BASE}/{path}", params=p, timeout=30)
    if resp.status_code == 404:
        return {"error": "Not found", "status": 404, "url": resp.url}
    resp.raise_for_status()
    return resp.json()


def _paginated(path: str, params: dict, max_results: int) -> list[dict]:
    """Fetch up to max_results across pages."""
    collected: list[dict] = []
    page = 0
    page_size = min(max_results, 100)
    while len(collected) < max_results:
        page_params = {**params, "page": page, "page-size": page_size}
        data = _get(path, page_params)
        results = data.get("results", [])
        collected.extend(results)
        if not data.get("links", {}).get("next"):
            break
        page += 1
        if len(collected) >= max_results:
            break
    return collected[:max_results]


server = Server("stat-gov")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_subjects",
            description=(
                "Browse or search GUS BDL subject categories (top-level topics like 'CENY', 'LUDNOŚĆ', "
                "'FINANSE PRZEDSIĘBIORSTW'). Use to discover subject IDs which then anchor variable searches."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string", "description": "Optional parent subject ID to browse children (omit for top-level)"},
                    "name": {"type": "string", "description": "Optional partial name to filter results (case-insensitive)"},
                    "limit": {"type": "integer", "default": 25, "description": "Max results"},
                },
            },
        ),
        Tool(
            name="search_variables",
            description=(
                "Search for variables (data series) in GUS BDL. Variables are the atomic units of statistical "
                "data — each has an ID used with `get_data`. Filter by subject_id (from search_subjects) and/or name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subject_id": {"type": "string", "description": "Optional subject ID to scope the search"},
                    "name": {"type": "string", "description": "Optional partial name to search for"},
                    "limit": {"type": "integer", "default": 25},
                },
            },
        ),
        Tool(
            name="search_units",
            description=(
                "Search for territorial units by name — voivodeships, powiats, gminas. Returns unit IDs used with `get_data`. "
                "Level meanings: 0=Kraj (country), 2=Województwo, 5=Powiat, 6=Gmina."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Partial name (case-insensitive), e.g. 'Warszawa'"},
                    "level": {"type": "integer", "description": "Optional territorial level (0..7)"},
                    "limit": {"type": "integer", "default": 25},
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="get_unit_details",
            description="Get full details of a territorial unit by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string", "description": "Unit ID (12-digit territorial code)"},
                },
                "required": ["unit_id"],
            },
        ),
        Tool(
            name="get_data",
            description=(
                "Get actual data (time series) for a variable in one or more territorial units. "
                "Example: GDP per capita for all voivodeships over 2015-2024. "
                "Returns the raw values with year, unit, and unit label."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "variable_id": {"type": "string", "description": "Variable ID from search_variables"},
                    "unit_ids": {"type": "array", "items": {"type": "string"}, "description": "List of unit IDs (from search_units). Default: all voivodeships."},
                    "year_from": {"type": "integer", "description": "Optional first year to include"},
                    "year_to": {"type": "integer", "description": "Optional last year to include"},
                    "limit_units": {"type": "integer", "default": 20, "description": "Max units to include when unit_ids is empty"},
                },
                "required": ["variable_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "search_subjects":
        params: dict[str, Any] = {}
        parent = arguments.get("parent_id")
        if parent:
            params["parent-id"] = parent
        name_q = (arguments.get("name") or "").strip()
        limit = int(arguments.get("limit", 25))

        results = _paginated("subjects", params, limit if not name_q else 500)
        if name_q:
            nq = name_q.lower()
            results = [r for r in results if nq in (r.get("name") or "").lower()][:limit]
        return [TextContent(type="text", text=json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))]

    if name == "search_variables":
        params: dict[str, Any] = {}
        if arguments.get("subject_id"):
            params["subject-id"] = arguments["subject_id"]
        name_q = (arguments.get("name") or "").strip()
        if name_q:
            params["name"] = name_q
        limit = int(arguments.get("limit", 25))

        results = _paginated("variables/search" if name_q else "variables", params, limit)
        return [TextContent(type="text", text=json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))]

    if name == "search_units":
        params: dict[str, Any] = {"name": arguments["name"]}
        if "level" in arguments and arguments["level"] is not None:
            params["level"] = int(arguments["level"])
        limit = int(arguments.get("limit", 25))
        results = _paginated("units/search", params, limit)
        # Annotate with human-readable level label
        for r in results:
            lvl = r.get("level")
            if lvl in LEVEL_LABELS:
                r["level_label"] = LEVEL_LABELS[lvl]
        return [TextContent(type="text", text=json.dumps({"count": len(results), "results": results}, ensure_ascii=False, indent=2))]

    if name == "get_unit_details":
        data = _get(f"units/{arguments['unit_id']}")
        if isinstance(data, dict) and data.get("level") in LEVEL_LABELS:
            data["level_label"] = LEVEL_LABELS[data["level"]]
        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    if name == "get_data":
        var_id = arguments["variable_id"]
        unit_ids: list[str] = arguments.get("unit_ids") or []
        year_from = arguments.get("year_from")
        year_to = arguments.get("year_to")
        limit_units = int(arguments.get("limit_units", 20))

        params: dict[str, Any] = {}
        if unit_ids:
            # BDL API accepts unit-id repeated; requests handles list values.
            params["unit-id"] = unit_ids
        else:
            # Default: all voivodeships (level 2)
            params["unit-level"] = 2
            params["page-size"] = min(limit_units, 100)
        if year_from is not None:
            params["year"] = list(range(int(year_from), int(year_to or year_from) + 1))
        elif year_to is not None:
            params["year"] = int(year_to)

        data = _get(f"data/by-variable/{var_id}", params)
        return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, indent=2))]

    raise ValueError(f"Unknown tool: {name}")


async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
