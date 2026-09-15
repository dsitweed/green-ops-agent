from dataclasses import asdict
import json
import os

from langchain_classic.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from contracts import DiscoveryResult, OptimizationCandidate, ResourceSnapshot

LLM_SYSTEM_PROMPT = """
Bạn là FinOps Analyst. Phân tích discovery data và đề xuất đúng một candidate
tối ưu chi phí nếu có đủ bằng chứng. Không được tự bịa resource hoặc số liệu.
Chỉ đề xuất giảm kích thước EC2 khi CPU trung bình thấp và không có dấu hiệu
ảnh hưởng availability. Nếu không đủ bằng chứng, không tạo candidate. Output
phải tuân thủ schema đã cung cấp.
"""


class FinOpsAgent:
    def __init__(self):
        self.analysis_chain = None
        if os.getenv("PIPELINE_MODE", "simulation") == "production":
            self.api_key = os.getenv("OPENAI_API_KEY")
            self.model_name = os.getenv("OPENAI_API_MODEL_NAME")
            self.base_url = os.getenv("OPENAI_API_BASE_URL")

            if not self.api_key:
                raise ValueError("OPENAI_API_KEY is not set")
            if not self.model_name:
                raise ValueError("OPENAI_API_MODEL_NAME is not set")
            if not self.base_url:
                raise ValueError("OPENAI_API_BASE_URL is not set")

            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", LLM_SYSTEM_PROMPT),
                    ("human", "Discovery data:\n{discovery_data}"),
                ]
            )
            self.analysis_chain = prompt | self._create_llm().with_structured_output(
                OptimizationCandidate
            )

    def analyze(self, discovery: DiscoveryResult) -> OptimizationCandidate | None:
        """Phân tích discovery data và tạo optimization candidate, nếu có đủ bằng chứng."""

        pipeline_mode = os.getenv("PIPELINE_MODE", "simulation")
        if pipeline_mode == "simulation":
            return self._generate_simulation_optimization_candidate(discovery)

        optimization_candidate = self.analysis_chain.invoke(
            {"discovery_data": json.dumps(asdict(discovery), ensure_ascii=False)}
        )

        if not optimization_candidate:
            return None

        resource = next(
            (
                resource
                for resource in discovery.resources
                if resource.resource_id == optimization_candidate.resource_id
            ),
            None,
        )

        if resource is None:
            return None

        if not self.is_valid_candidate(optimization_candidate, resource):
            return None

        return optimization_candidate

    def _create_llm(self) -> ChatOpenAI:
        """Tạo LLM adapter dùng riêng cho bước phân tích candidate."""

        return ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0,
        )

    def _generate_simulation_optimization_candidate(
        self, discovery: DiscoveryResult
    ) -> OptimizationCandidate | None:
        for resource in discovery.resources:
            if (
                resource.resource_type == "aws_instance"
                # TODO: Make this threshold configurable
                and resource.cpu_average_percent < 20
            ):
                if (
                    not resource.recommended_size
                    or resource.expected_monthly_saving <= 0
                ):
                    continue

                return OptimizationCandidate(
                    resource_id=resource.resource_id,
                    current_size=resource.current_size,
                    recommended_size=resource.recommended_size,
                    expected_monthly_saving=resource.expected_monthly_saving,
                    performance_risk=resource.performance_risk or "unknown",
                    availability_impact="none",
                )

        return None

    @staticmethod
    def is_valid_candidate(
        recommendation: OptimizationCandidate,
        resource: ResourceSnapshot,
    ) -> bool:
        return (
            recommendation.resource_id == resource.resource_id
            and resource.resource_type == "aws_instance"
            # TODO: Make this threshold configurable
            and resource.cpu_average_percent < 20
            and recommendation.current_size == resource.current_size
            and recommendation.recommended_size != resource.current_size
            and bool(recommendation.recommended_size)
            and recommendation.expected_monthly_saving > 0
            and recommendation.performance_risk == "low"
            and recommendation.availability_impact == "none"
        )
