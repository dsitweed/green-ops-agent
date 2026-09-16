import json
import os
from dataclasses import asdict
from difflib import unified_diff
from pathlib import Path

from langchain_classic.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from contracts import (
    OptimizationCandidate,
    TerraformChangePlan,
    TerraformFileChange,
)


class TerraformChangeGenerator:
    """Generate Terraform proposals and apply them through an LLM in production."""

    _UPDATE_PROMPT = """
        You are a Terraform change agent operating in a production repository.
        Understand the complete change request before editing any file.

        Change request:
        {request}

        Repository Terraform files are provided as a JSON object keyed by paths
        relative to the Terraform root. Inspect references, variables, modules,
        dependencies, and related resources before deciding which files change.
        Preserve unrelated content and formatting. Never invent resources or
        values. Include every file required for a consistent Terraform change.

        Return JSON only with this schema:
        {{
            "related_files": ["relative/path.tf"],
            "resources_to_change": ["aws_instance.example"],
            "protected_files": ["relative/path.tf"],
            "summary": "why this change is required",
            "files": [{{"path": "relative/path.tf", "content": "complete updated file content", "reason": "why this file changes"}}]
        }}
        Include only changed files in files. Paths must refer to files in the input.
    """

    def __init__(self) -> None:
        self._agent = None
        if os.getenv("PIPELINE_MODE", "simulation").strip().lower() == "production":
            self._agent = self._create_agent()

    def generate(
        self,
        candidate: OptimizationCandidate,
    ) -> TerraformChangePlan:
        if self._agent is None:
            return TerraformChangePlan(
                related_files=("terraform/main.tf",),
                resources_to_change=(candidate.resource_id,),
                changes=(
                    TerraformFileChange(
                        file_path="terraform/main.tf",
                        content="",
                        reason="Simulation placeholder; no file is written.",
                    ),
                ),
                protected_files=(),
                summary=f"Resize {candidate.resource_id} from {candidate.current_size} to {candidate.recommended_size}.",
                diff=f"- {candidate.current_size}\n+ {candidate.recommended_size}",
            )

        terraform_root = self._terraform_root()
        sources = self._read_terraform_files(terraform_root)
        response = self._request_changes(candidate, sources)
        return self._build_plan(terraform_root, sources, response)

    def apply(self, plan: TerraformChangePlan) -> None:
        """Apply an already validated plan to the configured Terraform root."""
        if self._agent is None:
            return
        root = self._terraform_root()
        for change in plan.changes:
            relative_file = Path(change.file_path)
            file_path = (root / relative_file).resolve()
            if relative_file.is_absolute() or ".." in relative_file.parts:
                raise ValueError(f"Invalid Terraform change path: {change.file_path}")
            if root.resolve() not in file_path.parents or not file_path.is_file():
                raise FileNotFoundError(
                    f"Terraform file does not exist: {change.file_path}"
                )
            file_path.write_text(change.content.rstrip("\n") + "\n", encoding="utf-8")

    @staticmethod
    def _terraform_root() -> Path:
        configured_root = os.getenv("TERRAFORM_ROOT", "terraform")
        root = Path(configured_root).expanduser()
        if not root.is_dir():
            raise FileNotFoundError(f"Terraform root does not exist: {root}")
        return root

    @staticmethod
    def _read_terraform_files(root: Path) -> dict[str, str]:
        files = {
            str(path.relative_to(root)): path.read_text(encoding="utf-8")
            for path in sorted(root.rglob("*.tf"))
            if path.is_file()
        }
        if not files:
            raise FileNotFoundError(f"No Terraform files found under: {root}")
        return files

    def _request_changes(
        self,
        candidate: OptimizationCandidate,
        sources: dict[str, str],
    ) -> dict[str, object]:
        request = {
            "candidate": asdict(candidate),
        }
        response = self._agent.invoke(
            {
                "request": json.dumps(request, indent=2),
                "files": json.dumps(sources, indent=2),
            }
        )
        return self._parse_agent_response(response)

    @staticmethod
    def _build_plan(
        root: Path,
        sources: dict[str, str],
        response: dict[str, object],
    ) -> TerraformChangePlan:
        related_files = tuple(str(path) for path in response.get("related_files", ()))
        resources = tuple(
            str(resource) for resource in response.get("resources_to_change", ())
        )
        protected_files = tuple(
            str(path) for path in response.get("protected_files", ())
        )
        summary = str(response.get("summary", ""))
        raw_changes = response.get("files", ())
        if (
            not isinstance(raw_changes, list)
            or not summary
            or not related_files
            or not resources
        ):
            raise ValueError(
                "Terraform change agent returned an incomplete change plan."
            )
        known_files = set(sources)
        if not set(related_files).issubset(known_files):
            raise ValueError(
                "Terraform change plan references an unknown related file."
            )
        if not set(protected_files).issubset(known_files):
            raise ValueError(
                "Terraform change plan references an unknown protected file."
            )

        validated_changes: list[tuple[Path, str, str]] = []
        file_changes: list[TerraformFileChange] = []
        for item in raw_changes:
            if not isinstance(item, dict):
                raise ValueError(
                    "Terraform change agent returned an invalid file change."
                )
            relative_path = str(item.get("path", ""))
            updated_source = str(item.get("content", ""))
            reason = str(item.get("reason", ""))
            relative_file = Path(relative_path)
            file_path = (root / relative_file).resolve()
            if (
                relative_file.is_absolute()
                or ".." in relative_file.parts
                or root.resolve() not in file_path.parents
                or relative_path not in sources
                or relative_path in protected_files
                or not reason
            ):
                raise ValueError(
                    f"Terraform agent returned an unknown file: {relative_path}"
                )
            source = sources[relative_path]
            if updated_source != source:
                validated_changes.append((file_path, source, updated_source))
                file_changes.append(
                    TerraformFileChange(relative_path, updated_source, reason)
                )

        if not validated_changes:
            raise ValueError("Terraform change agent did not produce a file change.")

        diffs: list[str] = []
        for file_path, source, updated_source in validated_changes:
            normalized_source = updated_source.rstrip("\n") + "\n"
            diffs.append(
                "".join(
                    unified_diff(
                        source.splitlines(keepends=True),
                        normalized_source.splitlines(keepends=True),
                        fromfile=str(file_path),
                        tofile=str(file_path),
                    )
                ).rstrip("\n")
            )
        return TerraformChangePlan(
            related_files=related_files,
            resources_to_change=resources,
            changes=tuple(file_changes),
            protected_files=protected_files,
            summary=summary,
            diff="\n".join(diffs),
        )

    @staticmethod
    def _parse_agent_response(response: str) -> dict[str, object]:
        try:
            payload = json.loads(response)
            if not isinstance(payload, dict):
                raise ValueError("Response must be an object.")
            return payload
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError("Terraform change agent returned invalid JSON.") from error

    def _create_agent(self):
        api_key = os.getenv("OPENAI_API_KEY")
        model_name = os.getenv("OPENAI_API_MODEL_NAME")
        base_url = os.getenv("OPENAI_API_BASE_URL")
        if not api_key or not model_name or not base_url:
            raise ValueError(
                "OPENAI_API_KEY, OPENAI_API_MODEL_NAME, and OPENAI_API_BASE_URL "
                "are required in production mode."
            )
        prompt = ChatPromptTemplate.from_template(self._UPDATE_PROMPT)
        return (
            prompt
            | ChatOpenAI(
                model=model_name,
                base_url=base_url,
                api_key=api_key,
                temperature=0,
            )
            | StrOutputParser()
        )
