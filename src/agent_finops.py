import json
from dataclasses import asdict

from contracts import PipelineRequest
from pipeline import FinOpsPipeline


def create_request() -> PipelineRequest:
    """Tạo input contract cho một lần chạy pipeline."""
    return PipelineRequest(
        application_name="Taco House",
        environment="staging",
        protected=False,
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
