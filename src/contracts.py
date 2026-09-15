from dataclasses import dataclass, field
from enum import StrEnum


class PipelineStatus(StrEnum):
    CONTINUE = "CONTINUE"
    BLOCKED = "BLOCKED"
    REJECTED = "REJECTED"
    WAITING_FOR_HUMAN_REVIEW = "WAITING_FOR_HUMAN_REVIEW"


@dataclass(frozen=True)
class PipelineRequest:
    application_name: str
    environment: str
    protected: bool = False
    region: str = "ap-northeast-1"
    evidence_window_days: int = 14


@dataclass(frozen=True)
class ResourceSnapshot:
    resource_id: str
    resource_type: str  # Loại tài nguyên, ví dụ: "aws_instance", "aws_ebs_volume"
    current_size: str
    monthly_cost: float
    cpu_average_percent: float
    terraform_managed: bool
    has_unresolved_drift: bool = False
    dependencies: tuple[str, ...] = ()
    recommended_size: str | None = None
    expected_monthly_saving: float = 0
    performance_risk: str | None = None


@dataclass(frozen=True)
class DiscoveryResult:
    request: PipelineRequest
    resources: tuple[ResourceSnapshot, ...]
    evidence_window_days: int
    recommendation_source: str


@dataclass(frozen=True)
class OptimizationCandidate:
    resource_id: str
    current_size: str
    recommended_size: str
    expected_monthly_saving: float
    performance_risk: str
    availability_impact: str


@dataclass(frozen=True)
class ContextAnalysis:
    candidate: OptimizationCandidate
    dependencies_resolved: bool
    architecture_constraints_satisfied: bool
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PolicyDecision:
    status: PipelineStatus
    reason: str


@dataclass(frozen=True)
class TerraformPatch:
    resource_id: str
    file_path: str
    old_value: str
    new_value: str
    diff: str


@dataclass(frozen=True)
class ValidationResult:
    terraform_fmt: bool
    terraform_validate: bool
    terraform_plan: bool
    infracost: bool
    unexpected_replacement: bool = False

    @property
    def passed(self) -> bool:
        return (
            all(
                (
                    self.terraform_fmt,
                    self.terraform_validate,
                    self.terraform_plan,
                    self.infracost,
                )
            )
            and not self.unexpected_replacement
        )


@dataclass(frozen=True)
class SafetyDecision:
    status: PipelineStatus
    reason: str
    rollback: str


@dataclass(frozen=True)
class PullRequestDraft:
    title: str
    body: str
    status: PipelineStatus


@dataclass(frozen=True)
class PipelineResult:
    status: PipelineStatus
    candidate: OptimizationCandidate | None = None
    policy: PolicyDecision | None = None
    patch: TerraformPatch | None = None
    validation: ValidationResult | None = None
    safety: SafetyDecision | None = None
    pull_request: PullRequestDraft | None = None
    messages: list[str] = field(default_factory=list)
