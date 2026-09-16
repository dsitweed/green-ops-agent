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
    estimated_cost_after: float | None = None
    saving_confidence: float | None = None
    evidence_sources: tuple[str, ...] = ()
    observation_period_days: int = 0
    business_criticality: str = "unknown"
    single_point_of_failure: bool = False
    has_redundancy: bool = True
    peak_cpu_percent: float | None = None
    memory_utilization_percent: float | None = None
    network_utilization_percent: float | None = None
    storage_utilization_percent: float | None = None
    latency_sla_breached: bool = False
    availability_impact: str = "unknown"
    autoscaling_managed: bool = False
    shared_resource: bool = False
    backup_strategy_verified: bool = False
    dependency_confidence: float = 1.0
    circular_dependency: bool = False
    cross_account_dependency: bool = False
    cross_region_dependency: bool = False


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
    estimated_cost_after: float | None = None
    expected_saving: float | None = None
    confidence: float | None = None
    evidence_sources: tuple[str, ...] = ()
    observation_period_days: int = 0
    monthly_recurring_saving: float | None = None
    one_time_saving: float = 0
    implementation_cost: float = 0
    payback_period_months: float | None = None
    action: str = "resize"
    capacity_reduction_percent: float = 0


@dataclass(frozen=True)
class ContextAnalysis:
    candidate: OptimizationCandidate
    resource: ResourceSnapshot | None
    dependencies_resolved: bool
    architecture_constraints_satisfied: bool
    notes: tuple[str, ...] = ()
    dependency_confidence: float = 1.0
    circular_dependency: bool = False
    environment_known: bool = True


@dataclass(frozen=True)
class PolicyDecision:
    status: PipelineStatus
    reason: str


@dataclass(frozen=True)
class TerraformFileChange:
    file_path: str
    content: str
    reason: str


@dataclass(frozen=True)
class TerraformChangePlan:
    related_files: tuple[str, ...]
    resources_to_change: tuple[str, ...]
    changes: tuple[TerraformFileChange, ...]
    protected_files: tuple[str, ...]
    summary: str
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
    patch: TerraformChangePlan | None = None
    validation: ValidationResult | None = None
    safety: SafetyDecision | None = None
    pull_request: PullRequestDraft | None = None
    messages: list[str] = field(default_factory=list)
