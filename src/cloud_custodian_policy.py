"""Deterministic governance checks mirrored by the Cloud Custodian policies."""

from dataclasses import dataclass
from pathlib import Path

from contracts import ContextAnalysis, DiscoveryResult, PipelineRequest, PipelineStatus, PolicyDecision


@dataclass(frozen=True)
class GovernanceConfig:
    allowed_accounts: frozenset[str] = frozenset({"111111111111"})
    blocked_accounts: frozenset[str] = frozenset({"production", "management", "security"})
    allowed_regions: frozenset[str] = frozenset({"ap-northeast-1"})
    allowed_resource_types: frozenset[str] = frozenset(
        {"aws_instance", "aws_ebs_volume", "aws_db_instance", "aws_s3_bucket", "aws_lambda_function"}
    )
    required_tags: frozenset[str] = frozenset({"Environment", "Owner", "Application", "CostCenter"})
    allowed_actions: frozenset[str] = frozenset({"stop", "start", "resize", "modify", "snapshot"})
    high_risk_actions: frozenset[str] = frozenset({"terminate", "delete", "destroy"})
    max_resources_per_run: int = 10
    max_accounts: int = 1
    max_regions: int = 1
    minimum_age_days: int = 7

    @classmethod
    def from_environment(cls) -> "GovernanceConfig":
        import os

        def values(name: str, default: frozenset[str]) -> frozenset[str]:
            raw = os.getenv(name)
            return frozenset(item.strip() for item in raw.split(",") if item.strip()) if raw else default

        return cls(
            allowed_accounts=values("CUSTODIAN_ALLOWED_ACCOUNTS", cls.allowed_accounts),
            blocked_accounts=values("CUSTODIAN_BLOCKED_ACCOUNTS", cls.blocked_accounts),
            allowed_regions=values("CUSTODIAN_ALLOWED_REGIONS", cls.allowed_regions),
        )


class CloudCustodianPolicy:
    """Runs local preflight checks before a Custodian execution is scheduled."""

    policy_path = Path(__file__).resolve().parent.parent / "policies" / "governance.yml"

    def __init__(self, config: GovernanceConfig | None = None) -> None:
        self.config = config or GovernanceConfig.from_environment()

    def check(self, request: PipelineRequest, discovery: DiscoveryResult, context: ContextAnalysis) -> PolicyDecision:
        if not self.policy_path.is_file():
            raise FileNotFoundError(f"Cloud Custodian policy file is missing: {self.policy_path}")
        resources = discovery.resources
        if request.environment.lower() == "production":
            return self._blocked("Production resources are never auto-modified.")
        if request.account_id in self.config.blocked_accounts or request.account_id not in self.config.allowed_accounts:
            return self._blocked("Account is not in the Cloud Custodian modification allowlist.")
        if request.region not in self.config.allowed_regions:
            return self._blocked("Region is not approved for modification.")
        if len(resources) > self.config.max_resources_per_run:
            return self._blocked("Execution exceeds the maximum resource limit.")
        if request.action in self.config.high_risk_actions and not request.approval_granted:
            return PolicyDecision(PipelineStatus.WAITING_FOR_HUMAN_REVIEW, "High-risk action requires manual approval.")
        if request.action not in self.config.allowed_actions and request.action not in self.config.high_risk_actions:
            return self._blocked("Action is not in the Cloud Custodian action allowlist.")

        for resource in resources:
            tags = dict(resource.tags)
            missing = self.config.required_tags - tags.keys()
            if missing:
                return self._blocked(f"Resource {resource.resource_id} is missing required tags: {', '.join(sorted(missing))}.")
            if tags.get("FinOpsOptOut", "").lower() == "true":
                return self._blocked(f"Resource {resource.resource_id} opted out of FinOps changes.")
            if any(tags.get(tag, "").lower() == "true" for tag in ("Critical", "Protected", "DoNotStop")):
                return self._blocked(f"Resource {resource.resource_id} has a protected tag.")
            if resource.resource_type not in self.config.allowed_resource_types:
                return self._blocked(f"Resource type {resource.resource_type} is not allowed.")
            if resource.age_days < self.config.minimum_age_days:
                return self._blocked(f"Resource {resource.resource_id} is younger than the minimum age.")
            if request.action in self.config.high_risk_actions and not resource.backup_exists:
                return self._blocked(f"Resource {resource.resource_id} has no mandatory backup.")
            if not tags.get("Owner", "").strip():
                return self._blocked(f"Owner is not identifiable for resource {resource.resource_id}.")
        return PolicyDecision(PipelineStatus.CONTINUE, "Cloud Custodian governance checks passed.")

    @staticmethod
    def _blocked(reason: str) -> PolicyDecision:
        return PolicyDecision(PipelineStatus.BLOCKED, reason)
