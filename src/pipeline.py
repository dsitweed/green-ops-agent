from contracts import (
    DiscoveryResult,
    OptimizationCandidate,
    PipelineRequest,
    PipelineResult,
    PipelineStatus,
    PullRequestDraft,
    ResourceSnapshot,
    TerraformChangePlan,
    ValidationResult,
)
import os
from mcp_discovery import McpDiscoverySource
from finops_agent import FinOpsAgent
from context_analyzer import ContextAnalyzer
from policy_engine import PolicyEngine
from terraform_change_generator import TerraformChangeGenerator
from validation_runner import ValidationRunner


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


class PullRequestBuilder:
    """Tạo nội dung PR, chưa gọi GitHub API."""

    def build(
        self,
        candidate: OptimizationCandidate,
        patch: TerraformChangePlan,
        validation: ValidationResult,
        resource: ResourceSnapshot | None,
    ) -> PullRequestDraft:
        body = (
            f"Change: {candidate.current_size} -> {candidate.recommended_size}\n"
            f"Expected saving: ${candidate.expected_saving}/month\n"
            f"Performance risk: {self._performance_risk(resource)}\n"
            f"Terraform plan: {'PASSED' if validation.terraform_plan else 'FAILED'}\n"
            f"Policy: PASSED\n"
            f"Files: {', '.join(change.file_path for change in patch.changes)}\n"
            "Rollback: Restore the Terraform change if needed.\n"
            "Status: WAITING FOR HUMAN APPROVAL"
        )
        return PullRequestDraft(
            title="FinOps Optimization Candidate",
            body=body,
            status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
        )

    @staticmethod
    def _performance_risk(resource: ResourceSnapshot | None) -> str:
        return (resource.performance_risk if resource else "unknown").upper()


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

        if not validation.passed:
            return PipelineResult(
                status=PipelineStatus.BLOCKED,
                candidate=candidate,
                policy=policy,
                patch=patch,
                validation=validation,
                messages=["Validation failed; no pull request will be created."],
            )

        self.patch_generator.apply(patch)

        pull_request = self.pull_request_builder.build(
            candidate,
            patch,
            validation,
            context.resource,
        )
        return PipelineResult(
            status=PipelineStatus.WAITING_FOR_HUMAN_REVIEW,
            candidate=candidate,
            policy=policy,
            patch=patch,
            validation=validation,
            pull_request=pull_request,
            messages=["Candidate is ready for human review."],
        )
