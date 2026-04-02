"""Observability MCP server for VictoriaLogs and VictoriaTraces."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from pydantic import BaseModel


class LogsSearchParams(BaseModel):
    query: str = "severity:ERROR"
    limit: int = 10
    time_range: str = "10m"


class LogsErrorCountParams(BaseModel):
    time_range: str = "1h"
    service: str | None = None


class TracesListParams(BaseModel):
    service: str = "Learning Management Service"
    limit: int = 5


class TracesGetParams(BaseModel):
    trace_id: str


def _text(data: Any) -> list[TextContent]:
    if isinstance(data, BaseModel):
        payload = data.model_dump()
    else:
        payload = data
    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, indent=2))]


def create_server() -> Server:
    server = Server("observability")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="logs_search",
                description="Search logs in VictoriaLogs by query and time range",
                inputSchema=LogsSearchParams.model_json_schema(),
            ),
            Tool(
                name="logs_error_count",
                description="Count errors per service over a time window",
                inputSchema=LogsErrorCountParams.model_json_schema(),
            ),
            Tool(
                name="traces_list",
                description="List recent traces for a service",
                inputSchema=TracesListParams.model_json_schema(),
            ),
            Tool(
                name="traces_get",
                description="Fetch a specific trace by ID",
                inputSchema=TracesGetParams.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any] | None) -> list[TextContent]:
        try:
            if name == "logs_search":
                params = LogsSearchParams.model_validate(arguments or {})
                result = await search_logs(params.query, params.limit, params.time_range)
            elif name == "logs_error_count":
                params = LogsErrorCountParams.model_validate(arguments or {})
                result = await count_errors(params.time_range, params.service)
            elif name == "traces_list":
                params = TracesListParams.model_validate(arguments or {})
                result = await list_traces(params.service, params.limit)
            elif name == "traces_get":
                params = TracesGetParams.model_validate(arguments or {})
                result = await get_trace(params.trace_id)
            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]
            return _text(result)
        except Exception as exc:
            return [TextContent(type="text", text=f"Error: {type(exc).__name__}: {exc}")]

    _ = list_tools, call_tool
    return server


async def search_logs(query: str, limit: int, time_range: str) -> dict:
    """Search logs in VictoriaLogs."""
    victorialogs_url = "http://localhost:9428"
    full_query = f"_time:{time_range} {query}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{victorialogs_url}/select/logsql/query",
            params={"query": full_query, "limit": limit},
            timeout=30.0,
        )
        response.raise_for_status()
        # VictoriaLogs returns various formats
        try:
            return response.json()
        except json.JSONDecodeError:
            return {"raw": response.text[:5000]}


async def count_errors(time_range: str, service: str | None) -> dict:
    """Count errors per service."""
    victorialogs_url = "http://localhost:9428"
    query = f"_time:{time_range} severity:ERROR"
    if service:
        query += f' service.name:"{service}"'
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{victorialogs_url}/select/logsql/query",
            params={"query": query, "limit": 100},
            timeout=30.0,
        )
        response.raise_for_status()
        try:
            data = response.json()
            # Count by service
            errors_by_service: dict[str, int] = {}
            if isinstance(data, list):
                for entry in data:
                    svc = entry.get("service.name", "unknown") if isinstance(entry, dict) else "unknown"
                    errors_by_service[svc] = errors_by_service.get(svc, 0) + 1
            return {"time_range": time_range, "errors_by_service": errors_by_service}
        except json.JSONDecodeError:
            return {"time_range": time_range, "raw": response.text[:2000]}


async def list_traces(service: str, limit: int) -> dict:
    """List recent traces for a service."""
    victoriatraces_url = "http://localhost:10428"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{victoriatraces_url}/select/jaeger/api/traces",
            params={"service": service, "limit": limit},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        # Return summary
        traces = data.get("data", [])
        summary = []
        for trace in traces[:limit]:
            trace_id = trace.get("traceID", "unknown")
            spans = trace.get("spans", [])
            summary.append({
                "trace_id": trace_id,
                "span_count": len(spans),
                "operations": list(set(s.get("operationName", "unknown") for s in spans[:5])),
            })
        return {"service": service, "traces": summary}


async def get_trace(trace_id: str) -> dict:
    """Fetch a specific trace by ID."""
    victoriatraces_url = "http://localhost:10428"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{victoriatraces_url}/select/jaeger/api/traces/{trace_id}",
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        # Return summary
        trace = data.get("data", [{}])[0] if isinstance(data.get("data"), list) else data.get("data", {})
        spans = trace.get("spans", [])
        span_summary = []
        for span in spans:
            span_summary.append({
                "span_id": span.get("spanID", "unknown"),
                "operation": span.get("operationName", "unknown"),
                "duration_ms": span.get("duration", 0),
                "service": trace.get("processes", {}).get(span.get("processID", ""), {}).get("serviceName", "unknown"),
            })
        return {
            "trace_id": trace.get("traceID", trace_id),
            "span_count": len(spans),
            "spans": span_summary,
        }


async def main() -> None:
    server = create_server()
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
