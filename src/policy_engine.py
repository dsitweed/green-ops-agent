import math

from contracts import (
    ContextAnalysis,
    PipelineRequest,
    DiscoveryResult,
    PolicyDecision,
    PipelineStatus,
)


class PolicyEngine:
    """Deterministic guardrails; LLM không được phép vượt qua lớp này."""

    MIN_MONTHLY_SAVING = 5.0
    MIN_SAVING_PERCENT = 0.10
    MIN_CONFIDENCE = 0.80
    MIN_OBSERVATION_DAYS = 7
    MAX_PAYBACK_MONTHS = 12.0
    MAX_CAPACITY_REDUCTION_PERCENT = 30.0
    MIN_DEPENDENCY_CONFIDENCE = 0.80

    def check(
        self,
        request: PipelineRequest,
        discovery: DiscoveryResult,
        context: ContextAnalysis,
    ) -> PolicyDecision:
        if request.environment == "production" and request.protected:
            return PolicyDecision(
                status=PipelineStatus.REJECTED,
                reason="Protected production resources cannot be changed automatically.",
            )

        if request.environment.strip().lower() not in {
            "production",
            "staging",
            "test",
            "development",
            "dev",
        }:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Environment is unknown; human review is required.",
            )

        saving_failure = self._validate_saving(context)
        if saving_failure:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason=saving_failure,
            )

        risk_decision = self._validate_risk(request, context)
        if risk_decision:
            return risk_decision

        if any(resource.has_unresolved_drift for resource in discovery.resources):
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Unresolved Terraform drift requires human review.",
            )

        if not context.dependencies_resolved:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Architecture dependencies are unresolved.",
            )

        if (
            context.circular_dependency
            or context.dependency_confidence < self.MIN_DEPENDENCY_CONFIDENCE
        ):
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Dependency graph is circular or below the confidence threshold.",
            )

        if not context.architecture_constraints_satisfied:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Architecture constraints are not satisfied.",
            )

        return PolicyDecision(
            status=PipelineStatus.CONTINUE,
            reason="Policy checks passed.",
        )

    def _validate_saving(self, context: ContextAnalysis) -> str | None:
        candidate = context.candidate
        resource = context.resource
        if resource is None:
            return "Candidate resource is missing from discovery data."
        values = (
            candidate.estimated_cost_after,
            candidate.expected_saving,
            candidate.confidence,
        )
        if any(value is None or not math.isfinite(value) for value in values):
            return "Saving estimate is missing current cost, cost-after, saving, or confidence."

        assert candidate.estimated_cost_after is not None
        assert candidate.expected_saving is not None
        assert candidate.confidence is not None
        calculated_saving = resource.monthly_cost - candidate.estimated_cost_after
        if not math.isclose(
            candidate.expected_saving, calculated_saving, rel_tol=0.01, abs_tol=0.01
        ):
            return "Expected saving does not match current cost minus estimated cost after."
        if resource.monthly_cost <= 0 or candidate.estimated_cost_after < 0:
            return "Cost values must be non-negative and current cost must be positive."
        if candidate.expected_saving <= 0:
            return "Expected saving must be positive."
        if candidate.expected_saving < self.MIN_MONTHLY_SAVING:
            return f"Expected monthly saving is below ${self.MIN_MONTHLY_SAVING:.2f}."
        if candidate.expected_saving / resource.monthly_cost < self.MIN_SAVING_PERCENT:
            return "Expected saving is below the minimum saving percentage."
        if candidate.confidence < self.MIN_CONFIDENCE:
            return "Saving estimate confidence is below the required threshold."
        if not candidate.evidence_sources:
            return "Saving estimate has no supporting evidence."
        if candidate.observation_period_days < self.MIN_OBSERVATION_DAYS:
            return "Observation period is shorter than the minimum evidence window."
        if candidate.monthly_recurring_saving is None:
            return "Monthly recurring saving must be provided separately from one-time saving."
        if candidate.monthly_recurring_saving <= 0:
            return "Monthly recurring saving must be positive."
        if candidate.one_time_saving < 0 or candidate.implementation_cost < 0:
            return "One-time saving and implementation cost cannot be negative."
        net_monthly_saving = (
            candidate.monthly_recurring_saving - candidate.implementation_cost
        )
        if net_monthly_saving <= 0:
            return "Implementation cost removes the recurring saving benefit."
        if candidate.implementation_cost > 0:
            if candidate.payback_period_months is None:
                return "Payback period is required when implementation cost exists."
            if candidate.payback_period_months > self.MAX_PAYBACK_MONTHS:
                return "Payback period exceeds the configured limit."
        return None

    def _validate_risk(
        self,
        request: PipelineRequest,
        context: ContextAnalysis,
    ) -> PolicyDecision | None:
        candidate = context.candidate
        resource = context.resource
        if resource is None:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Candidate resource is missing from discovery data.",
            )
        if resource.business_criticality in {"critical", "high"}:
            return PolicyDecision(
                status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
                reason="High-criticality resources require human approval.",
            )
        if resource.single_point_of_failure or not resource.has_redundancy:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Candidate affects a single point of failure or lacks redundancy.",
            )
        if resource.autoscaling_managed:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Autoscaling-managed resources cannot be manually resized.",
            )
        if resource.shared_resource:
            return PolicyDecision(
                status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
                reason="Shared resources require blast-radius review.",
            )
        if candidate.capacity_reduction_percent > self.MAX_CAPACITY_REDUCTION_PERCENT:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Capacity reduction exceeds the configured 30% limit.",
            )
        if resource.memory_utilization_percent is None and candidate.action == "resize":
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Memory utilization evidence is required before rightsizing.",
            )
        if (
            resource.network_utilization_percent is None
            and candidate.action == "resize"
        ):
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Network utilization evidence is required before rightsizing.",
            )
        if (
            resource.storage_utilization_percent is None
            and candidate.action == "resize"
        ):
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Storage utilization evidence is required before rightsizing.",
            )
        if resource.latency_sla_breached:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="SLA preservation has not been demonstrated.",
            )
        if candidate.action in {
            "terminate",
            "delete",
            "destroy",
            "release",
            "purge",
        }:
            if not resource.backup_strategy_verified:
                return PolicyDecision(
                    status=PipelineStatus.BLOCKED,
                    reason="Destructive action lacks a verified backup or recovery strategy.",
                )
            return PolicyDecision(
                status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
                reason="Destructive actions require explicit human approval.",
            )
        if request.environment.strip().lower() == "production":
            return PolicyDecision(
                status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
                reason="Production changes require human approval.",
            )
        return None
