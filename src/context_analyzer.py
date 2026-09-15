from contracts import ContextAnalysis, OptimizationCandidate, DiscoveryResult


class ContextAnalyzer:

    def analyze(
        self,
        candidate: OptimizationCandidate,
        discovery: DiscoveryResult,
    ) -> ContextAnalysis:
        """Kiểm tra dependency và constraint trước khi tạo patch."""

        resource = next(
            (
                resource
                for resource in discovery.resources
                if resource.resource_id == candidate.resource_id
            ),
            None,
        )

        if resource is None:
            return ContextAnalysis(
                candidate=candidate,
                dependencies_resolved=False,
                architecture_constraints_satisfied=False,
                notes=("Resource not found in discovery data.",),
            )

        # TODO: Add more sophisticated dependency checks
        # Does a dependency exist?
        # Is it active?
        # Is it drifting?
        # Does changing the instance affect the Load Balancer?
        # Are there any critical auto-scaling, database, queue, or service issues involved?
        dependencies_resolved = all(
            dependency.strip() for dependency in resource.dependencies
        )

        # TODO: Add more sophisticated architecture constraint checks
        # Check if the recommended size meets availability and performance requirements (availability >= required)
        # Check if the recommended size meets performance requirements (performance risk <= acceptable)
        # Check if the recommended size meets cost optimization requirements (expected monthly saving >= threshold)
        # Check if the reliability requirements > required threshold
        architecture_constraints_satisfied = candidate.availability_impact == "none"

        return ContextAnalysis(
            candidate=candidate,
            dependencies_resolved=dependencies_resolved,
            architecture_constraints_satisfied=architecture_constraints_satisfied,
            notes=(
                f"Evidence window: {discovery.evidence_window_days} days",
                f"Recommendation source: {discovery.recommendation_source}",
            ),
        )
