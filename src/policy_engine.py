from contracts import (
    ContextAnalysis,
    PipelineRequest,
    DiscoveryResult,
    PolicyDecision,
    PipelineStatus,
)


class PolicyEngine:
    """Deterministic guardrails; LLM không được phép vượt qua lớp này."""

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

        if not context.architecture_constraints_satisfied:
            return PolicyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Architecture constraints are not satisfied.",
            )

        return PolicyDecision(
            status=PipelineStatus.CONTINUE,
            reason="Policy checks passed.",
        )
