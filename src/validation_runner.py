import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from contracts import TerraformChangePlan, ValidationResult


class ValidationRunner:
    """Validate a Terraform change plan without modifying the real repository.
    A sandboxed environment is used for testing changes.

    The runner checks plan consistency, applies proposed changes only to a
    temporary Terraform copy, and runs Terraform formatting, initialization,
    validation, planning, and Infracost checks in production mode. Simulation
    mode returns successful validation results without invoking external tools.
    """

    def validate(self, plan: TerraformChangePlan) -> ValidationResult:
        if not self._plan_is_consistent(plan):
            return ValidationResult(
                terraform_fmt=False,
                terraform_validate=False,
                terraform_plan=False,
                infracost=False,
            )

        if os.getenv("PIPELINE_MODE", "simulation").strip().lower() != "production":
            return ValidationResult(
                terraform_fmt=True,
                terraform_validate=True,
                terraform_plan=True,
                infracost=True,
            )

        root = Path(os.getenv("TERRAFORM_ROOT", "terraform")).expanduser()
        if not root.is_dir():
            return ValidationResult(
                terraform_fmt=False,
                terraform_validate=False,
                terraform_plan=False,
                infracost=False,
            )

        with TemporaryDirectory(prefix="green-ops-terraform-") as directory:
            sandbox = Path(directory) / root.name
            shutil.copytree(root, sandbox)
            self._overlay_changes(sandbox, plan)
            fmt = self._run_terraform(sandbox, "fmt", "-check", "-recursive")
            initialized = self._run_terraform(
                sandbox, "init", "-backend=false", "-input=false"
            )
            terraform_validate = initialized and self._run_terraform(
                sandbox, "validate", "-no-color"
            )
            terraform_plan = terraform_validate and self._run_terraform(
                sandbox,
                "plan",
                "-input=false",
                "-refresh=false",
                "-lock=false",
                "-no-color",
            )
            infracost = self._run_infracost(sandbox)

        return ValidationResult(
            terraform_fmt=fmt,
            terraform_validate=terraform_validate,
            terraform_plan=terraform_plan,
            infracost=infracost,
        )

    @staticmethod
    def _plan_is_consistent(plan: TerraformChangePlan) -> bool:
        if not plan.summary or not plan.related_files or not plan.resources_to_change:
            return False
        related_files = set(plan.related_files)
        protected_files = set(plan.protected_files)
        changed_files = [change.file_path for change in plan.changes]
        if protected_files & set(changed_files):
            return False
        if any(file_path not in related_files for file_path in changed_files):
            return False
        if len(changed_files) != len(set(changed_files)):
            return False
        return all(
            change.reason and change.content is not None for change in plan.changes
        )

    @staticmethod
    def _overlay_changes(root: Path, plan: TerraformChangePlan) -> None:
        for change in plan.changes:
            relative_file = Path(change.file_path)
            destination = (root / relative_file).resolve()
            if (
                relative_file.is_absolute()
                or ".." in relative_file.parts
                or root.resolve() not in destination.parents
                or not destination.is_file()
            ):
                raise ValueError(f"Invalid Terraform change path: {change.file_path}")
            destination.write_text(change.content.rstrip("\n") + "\n", encoding="utf-8")

    @staticmethod
    def _run_terraform(root: Path, *arguments: str) -> bool:
        if shutil.which("terraform") is None:
            return False
        result = subprocess.run(
            ["terraform", "-chdir=" + str(root), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    @staticmethod
    def _run_infracost(root: Path) -> bool:
        if shutil.which("infracost") is None:
            return False
        result = subprocess.run(
            ["infracost", "breakdown", "--path", str(root), "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
