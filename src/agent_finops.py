import json
import os
from dataclasses import asdict

from dotenv import load_dotenv

from contracts import PipelineRequest
from pipeline import FinOpsPipeline

load_dotenv()


def create_request() -> PipelineRequest:
    """Tạo input contract cho một lần chạy pipeline."""
    return PipelineRequest(
        application_name=os.getenv("FINOPS_APPLICATION", "Taco House"),
        environment=os.getenv("FINOPS_ENVIRONMENT", "staging"),
        protected=os.getenv("FINOPS_PROTECTED", "false").lower() == "true",
        region=os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1"),
        evidence_window_days=int(os.getenv("FINOPS_EVIDENCE_WINDOW_DAYS", "14")),
    )


def run_pipeline(request: PipelineRequest) -> dict:
    """Chạy pipeline và chuyển output contract thành dữ liệu serializable."""
    result = FinOpsPipeline().run(request)
    return asdict(result)


def main() -> None:
    """Composition root của ứng dụng FinOps."""
    request = create_request()
    result = run_pipeline(request)

    print("--- FinOps pipeline output ---")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
