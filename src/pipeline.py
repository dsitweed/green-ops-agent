from contracts import (
    ContextAnalysis,
    DiscoveryResult,
    OptimizationCandidate,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
    PolicyDecision,
    PullRequestDraft,
    ResourceSnapshot,
    SafetyDecision,
    TerraformPatch,
    ValidationResult,
)
import os
from mcp_discovery import McpDiscoverySource
from finops_agent import FinOpsAgent
from context_analyzer import ContextAnalyzer


class FakeDiscoverySource:
    """Nguồn dữ liệu giả thay cho AWS, Terraform và các dịch vụ metrics."""

    # def discover(instance_id, region):
    #     ec2 = ec2_provider.get_instance(instance_id, region)
    #     metrics = cloudwatch_provider.get_metrics(instance_id, region)
    #     terraform = terraform_provider.find_resource(instance_id)
    #     recommendation = compute_optimizer_provider.get_recommendation(
    #         instance_id, region
    #     )

    #     return {
    #         "resource": ec2,
    #         "metrics": metrics,
    #         "terraform": terraform,
    #         "recommendation": recommendation,
    #         "source": {
    #             "ec2": "aws",
    #             "metrics": "fixture",
    #             "recommendation": "fixture",
    #         },
    #     }

    def discover(self, request: PipelineRequest) -> DiscoveryResult:
        resources = ()
        # TODO: fix hardcode request
        if request.application_name.strip().lower() == "taco house":
            resources = (
                ResourceSnapshot(
                    resource_id="i-01234abcd",
                    resource_type="aws_instance",
                    current_size="m5.xlarge",
                    monthly_cost=140,
                    cpu_average_percent=3,
                    terraform_managed=True,
                    dependencies=("aws_lb.api",),
                ),
                ResourceSnapshot(
                    resource_id="vol-09876xyz",
                    resource_type="aws_ebs_volume",
                    current_size="100GB",
                    monthly_cost=10,
                    cpu_average_percent=0,
                    terraform_managed=True,
                ),
            )

        return DiscoveryResult(
            request=request,
            resources=resources,
            evidence_window_days=30,
            recommendation_source="fake-compute-optimizer",
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


class TerraformChangeGenerator:
    """Tạo candidate patch; adapter thật sau này sẽ sửa file trong sandbox branch."""

    def generate(self, candidate: OptimizationCandidate) -> TerraformPatch:
        return TerraformPatch(
            resource_id=candidate.resource_id,
            file_path="terraform/main.tf",
            old_value=f'instance_type = "{candidate.current_size}"',
            new_value=f'instance_type = "{candidate.recommended_size}"',
            diff=(
                f'- instance_type = "{candidate.current_size}"\n'
                f'+ instance_type = "{candidate.recommended_size}"'
            ),
        )


class ValidationRunner:
    """Mô phỏng terraform fmt/validate/plan và Infracost."""

    def validate(self, patch: TerraformPatch) -> ValidationResult:
        has_change = patch.old_value != patch.new_value
        return ValidationResult(
            terraform_fmt=True,
            terraform_validate=True,
            terraform_plan=has_change,
            infracost=has_change,
        )


class SafetyGate:
    """Chỉ cho phép tạo PR khi cost và risk đều đạt điều kiện."""

    def evaluate(
        self,
        candidate: OptimizationCandidate,
        validation: ValidationResult,
    ) -> SafetyDecision:
        if not validation.passed:
            return SafetyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Validation failed; no pull request will be created.",
                rollback=f"Restore {candidate.current_size}",
            )

        if candidate.expected_monthly_saving <= 0:
            return SafetyDecision(
                status=PipelineStatus.BLOCKED,
                reason="The change does not reduce cost.",
                rollback=f"Restore {candidate.current_size}",
            )

        if (
            candidate.performance_risk != "low"
            or candidate.availability_impact != "none"
        ):
            return SafetyDecision(
                status=PipelineStatus.BLOCKED,
                reason="Performance or availability risk is above the allowed threshold.",
                rollback=f"Restore {candidate.current_size}",
            )

        return SafetyDecision(
            status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
            reason="Safety checks passed; human approval is required.",
            rollback=f"Restore {candidate.current_size}",
        )


class PullRequestBuilder:
    """Tạo nội dung PR, chưa gọi GitHub API."""

    def build(
        self,
        candidate: OptimizationCandidate,
        patch: TerraformPatch,
        validation: ValidationResult,
        safety: SafetyDecision,
    ) -> PullRequestDraft:
        body = (
            f"Change: {candidate.current_size} -> {candidate.recommended_size}\n"
            f"Expected saving: ${candidate.expected_monthly_saving}/month\n"
            f"Performance risk: {candidate.performance_risk.upper()}\n"
            f"Terraform plan: {'PASSED' if validation.terraform_plan else 'FAILED'}\n"
            f"Policy: PASSED\n"
            f"File: {patch.file_path}\n"
            f"Rollback: {safety.rollback}\n"
            "Status: WAITING FOR HUMAN APPROVAL"
        )
        return PullRequestDraft(
            title="FinOps Optimization Candidate",
            body=body,
            status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
        )


class FinOpsPipeline:
    """Orchestrator duy nhất điều phối toàn bộ decision pipeline."""

    def __init__(self) -> None:
        if os.environ.get("PIPELINE_MODE", "simulation") == "production":
            # Use MCP discovery source in production mode
            self.discovery_source = McpDiscoverySource(
                server_path=os.getenv("CFM_MCP_SERVER"),
                terraform_state_path=os.getenv("TERRAFORM_STATE_PATH", "terraform"),
            )
        else:
            self.discovery_source = FakeDiscoverySource()
        self.agent = FinOpsAgent()
        self.context_analyzer = ContextAnalyzer()
        self.policy_engine = PolicyEngine()
        self.patch_generator = TerraformChangeGenerator()
        self.validation_runner = ValidationRunner()
        self.safety_gate = SafetyGate()
        self.pull_request_builder = PullRequestBuilder()

    def run(self, request: PipelineRequest) -> PipelineResult:
        discovery = self.discovery_source.discover(request)
        candidate = self.agent.analyze(discovery)

        if candidate is None:
            return PipelineResult(
                status=PipelineStatus.BLOCKED,
                messages=["No optimization candidate was found."],
            )

        context = self.context_analyzer.analyze(candidate, discovery)
        policy = self.policy_engine.check(request, discovery, context)

        if policy.status != PipelineStatus.CONTINUE:
            return PipelineResult(
                status=policy.status,
                candidate=candidate,
                policy=policy,
                messages=[policy.reason],
            )

        patch = self.patch_generator.generate(candidate)
        validation = self.validation_runner.validate(patch)
        safety = self.safety_gate.evaluate(candidate, validation)

        if safety.status != PipelineStatus.WAITING_FOR_HUMAN_REVIEW:
            return PipelineResult(
                status=safety.status,
                candidate=candidate,
                policy=policy,
                patch=patch,
                validation=validation,
                safety=safety,
                messages=[safety.reason],
            )

        pull_request = self.pull_request_builder.build(
            candidate,
            patch,
            validation,
            safety,
        )
        return PipelineResult(
            status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
            candidate=candidate,
            policy=policy,
            patch=patch,
            validation=validation,
            safety=safety,
            pull_request=pull_request,
            messages=["Candidate is ready for human review."],
        )
