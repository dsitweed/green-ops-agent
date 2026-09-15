from contracts import (
    ContextAnalysis,
    DiscoveryResult,
    OptimizationCandidate,
    ResourceSnapshot,
)


class ContextAnalyzer:
    def analyze(
        self,
        candidate: OptimizationCandidate,
        discovery: DiscoveryResult,
    ) -> ContextAnalysis:
        """Kiểm tra dependency và constraint trước khi tạo patch."""

        resource = self._find_resource(candidate.resource_id, discovery.resources)

        if resource is None:
            return ContextAnalysis(
                candidate=candidate,
                dependencies_resolved=False,
                architecture_constraints_satisfied=False,
                notes=("Resource not found in discovery data.",),
            )

        notes = [
            f"Evidence window: {discovery.evidence_window_days} days",
            f"Recommendation source: {discovery.recommendation_source}",
        ]
        dependencies_resolved, dependency_notes = self._check_dependencies(
            resource, discovery.resources
        )
        notes.extend(dependency_notes)

        architecture_constraints_satisfied, constraint_notes = (
            self._check_architecture_constraints(candidate, resource, discovery)
        )
        notes.extend(constraint_notes)

        return ContextAnalysis(
            candidate=candidate,
            dependencies_resolved=dependencies_resolved,
            architecture_constraints_satisfied=architecture_constraints_satisfied,
            notes=tuple(notes),
        )

    @staticmethod
    def _find_resource(
        resource_id: str,
        resources: tuple[ResourceSnapshot, ...],
    ) -> ResourceSnapshot | None:
        return next(
            (resource for resource in resources if resource.resource_id == resource_id),
            None,
        )

    @staticmethod
    def _check_dependencies(
        resource: ResourceSnapshot,
        resources: tuple[ResourceSnapshot, ...],
    ) -> tuple[bool, list[str]]:
        dependencies = tuple(dependency.strip() for dependency in resource.dependencies)
        notes: list[str] = []

        if any(not dependency for dependency in dependencies):
            return False, ["Dependency list contains an empty identifier."]

        if len(set(dependencies)) != len(dependencies):
            return False, ["Dependency list contains duplicate identifiers."]

        if resource.resource_id in dependencies:
            return False, ["Resource cannot depend on itself."]

        known_resources = {item.resource_id: item for item in resources}
        unresolved_drift = [
            dependency
            for dependency in dependencies
            if dependency in known_resources
            and known_resources[dependency].has_unresolved_drift
        ]
        if unresolved_drift:
            return False, [
                "Dependencies with unresolved drift: "
                + ", ".join(unresolved_drift)
                + "."
            ]

        if dependencies:
            unknown_dependencies = [
                dependency
                for dependency in dependencies
                if dependency not in known_resources
            ]
            if unknown_dependencies:
                notes.append(
                    "Dependency status could not be verified for: "
                    + ", ".join(unknown_dependencies)
                    + "."
                )
            else:
                notes.append(
                    "All discovered dependencies are free of unresolved drift."
                )
        else:
            notes.append("No dependencies were declared for this resource.")

        return True, notes

    @staticmethod
    def _check_architecture_constraints(
        candidate: OptimizationCandidate,
        resource: ResourceSnapshot,
        discovery: DiscoveryResult,
    ) -> tuple[bool, list[str]]:
        failures: list[str] = []

        if resource.resource_type != "aws_instance":
            failures.append(
                "Only aws_instance resources can be resized by this analyzer."
            )
        if not resource.terraform_managed:
            failures.append("Resource is not marked as Terraform-managed.")
        if resource.has_unresolved_drift:
            failures.append("Resource has unresolved Terraform drift.")
        if candidate.current_size != resource.current_size:
            failures.append("Candidate current size does not match discovery data.")
        if candidate.recommended_size == resource.current_size:
            failures.append("Recommended size is identical to the current size.")
        if candidate.expected_monthly_saving <= 0:
            failures.append("Expected monthly saving must be greater than zero.")
        if candidate.expected_monthly_saving >= resource.monthly_cost:
            failures.append(
                "Expected saving cannot be greater than or equal to monthly cost."
            )
        if candidate.performance_risk != "low":
            failures.append("Performance risk is above the low-risk threshold.")
        if candidate.availability_impact != "none":
            failures.append("Candidate reports an availability impact.")
        if discovery.evidence_window_days <= 0:
            failures.append("Evidence window must be greater than zero days.")

        if failures:
            return False, ["Architecture constraints failed: " + " ".join(failures)]

        return True, [
            "Resource is Terraform-managed and candidate matches the discovered configuration.",
            "Performance, availability, cost, and evidence-window constraints passed.",
        ]
