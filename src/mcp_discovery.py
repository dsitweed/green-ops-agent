import asyncio
import json
import os
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from contracts import DiscoveryResult, PipelineRequest, ResourceSnapshot


class McpDiscoverySource:
    """Lấy EC2 recommendation qua CFM Tips MCP server."""

    def __init__(
        self, server_path: str, terraform_state_path: str = "terraform"
    ) -> None:
        # CFM_MCP_SERVER must point to mcp_server_with_runbooks.py
        self.server_path = Path(server_path).expanduser()
        if not self.server_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            configured_path = (project_root / self.server_path).resolve()
            legacy_path = self.server_path
            if not configured_path.is_file() and legacy_path.parts[:1] == ("..",):
                configured_path = (
                    project_root / Path(*legacy_path.parts[1:])
                ).resolve()
            self.server_path = configured_path
        if not self.server_path.is_file():
            raise FileNotFoundError(
                f"CFM_MCP_SERVER does not point to a file: {self.server_path}"
            )
        self.terraform_state_path = Path(terraform_state_path)

    def discover(self, request: PipelineRequest) -> DiscoveryResult:
        report = asyncio.run(
            self._call_mcp(
                # TODO: Fix hardcoded tool name; consider making it configurable
                "ec2_rightsizing",
                {
                    "region": request.region,
                    "lookback_period_days": request.evidence_window_days,
                    "output_format": "json",
                },
            )
        )
        resources = self._to_snapshots(report)
        return DiscoveryResult(
            request=request,
            resources=tuple(resources),
            evidence_window_days=request.evidence_window_days,
            recommendation_source="cfm-tips-mcp",
        )

    # TODO: Refactor call_mcp method
    async def _call_mcp(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        default_python = self.server_path.parent / ".venv" / "bin" / "python"
        configured_python = os.environ.get("CFM_MCP_PYTHON", str(default_python))
        server_python = Path(configured_python).expanduser()
        if not server_python.is_absolute():
            server_python = (
                Path(__file__).resolve().parent.parent / server_python
            ).resolve()
        command = os.environ.get("CFM_MCP_COMMAND", str(server_python))
        if command == "uv":
            server_args = [
                "run",
                "--directory",
                str(self.server_path.parent),
                "--with",
                "mcp>=0.9.1,<1",
            ]
            requirements_path = self.server_path.parent / "requirements.txt"
            if requirements_path.is_file():
                server_args.extend(["--with-requirements", str(requirements_path)])
            server_args.extend(["python", self.server_path.name])
        else:
            if not Path(command).is_file():
                raise FileNotFoundError(
                    f"CFM_MCP_PYTHON does not point to a file: {command}"
                )
            server_args = [str(self.server_path)]

        launch_command = shlex.join([command, *server_args])
        server = StdioServerParameters(
            command="/bin/sh",
            args=[
                "-c",
                f"cd {shlex.quote(str(self.server_path.parent))} && exec {launch_command}",
            ],
            env=os.environ.copy(),
        )
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

        for item in result.content:
            text = getattr(item, "text", None)
            if text:
                return json.loads(text)
        raise RuntimeError(f"MCP tool {tool_name!r} returned no JSON text content")

    def _to_snapshots(self, report: Any) -> Iterator[ResourceSnapshot]:
        for item in self._find_recommendations(report):
            resource_id = item.get("instance_id") or item.get("resource_id")
            if not resource_id:
                continue

            recommendation = item.get("recommendation") or {}
            if not isinstance(recommendation, dict):
                recommendation = {}
            recommendation = {
                **recommendation,
                "instance_type": recommendation.get(
                    "instance_type",
                    item.get("recommended_instance_type"),
                ),
                "estimated_monthly_savings": recommendation.get(
                    "estimated_monthly_savings",
                    item.get("estimated_monthly_savings", 0),
                ),
                "performance_risk": recommendation.get(
                    "performance_risk",
                    item.get("performance_risk", "unknown"),
                ),
            }
            yield ResourceSnapshot(
                resource_id=resource_id,
                resource_type="aws_instance",
                current_size=item.get("instance_type")
                or item.get("current_instance_type", "unknown"),
                monthly_cost=float(item.get("monthly_cost", 0)),
                cpu_average_percent=float(
                    item.get("avg_cpu_utilization", item.get("average_cpu", 0))
                ),
                terraform_managed=False,
                dependencies=(),
                recommended_size=recommendation.get("instance_type"),
                expected_monthly_saving=float(
                    recommendation.get("estimated_monthly_savings", 0)
                ),
                performance_risk=recommendation.get("performance_risk"),
                estimated_cost_after=self._optional_float(
                    item.get("estimated_cost_after")
                    or recommendation.get("estimated_cost_after")
                ),
                saving_confidence=self._optional_float(
                    item.get("saving_confidence") or recommendation.get("confidence")
                ),
                evidence_sources=tuple(
                    item.get("evidence_sources")
                    or recommendation.get("evidence_sources")
                    or ()
                ),
                observation_period_days=int(
                    item.get("observation_period_days")
                    or recommendation.get("observation_period_days")
                    or 0
                ),
                business_criticality=item.get("business_criticality", "unknown"),
                single_point_of_failure=bool(
                    item.get("single_point_of_failure", False)
                ),
                has_redundancy=bool(item.get("has_redundancy", True)),
                autoscaling_managed=bool(item.get("autoscaling_managed", False)),
                shared_resource=bool(item.get("shared_resource", False)),
                backup_strategy_verified=bool(
                    item.get("backup_strategy_verified", False)
                ),
            )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        return float(value) if value is not None else None

    def _find_recommendations(self, value: Any) -> Iterator[dict[str, Any]]:
        if isinstance(value, dict):
            if "instanceArn" in value:
                value = {
                    **value,
                    "instance_id": value["instanceArn"].rsplit("/", 1)[-1],
                    "current_instance_type": value.get("currentInstanceType"),
                    "recommended_instance_type": self._recommended_type(value),
                }
            if "instance_id" in value or "resource_id" in value:
                yield value
            for child in value.values():
                yield from self._find_recommendations(child)
        elif isinstance(value, list):
            for child in value:
                yield from self._find_recommendations(child)

    @staticmethod
    def _recommended_type(value: dict[str, Any]) -> str | None:
        options = value.get("recommendationOptions") or []
        if not options:
            return None
        return options[0].get("instanceType")
