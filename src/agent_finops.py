import os

from dotenv import load_dotenv
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent, tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

MODEL_NAME = "apu-gpt-5.6-sol"
BASE_URL = "https://luvenia-uncommuted-hypermorally.ngrok-free.dev/v1"

SYSTEM_PROMPT = (
    "Bạn là một chuyên gia FinOps xuất sắc chuyên tối ưu chi phí AWS. "
    "Khi nhận được yêu cầu tối ưu cho một ứng dụng, bạn PHẢI sử dụng công cụ "
    "`get_aws_resources_status` để lấy dữ liệu thực tế trước, tuyệt đối không "
    "được tự bịa ra số liệu. Sau khi có dữ liệu, hãy phân tích và đưa ra lời "
    "khuyên tối ưu chi phí cụ thể (số tiền tiết kiệm được, giải pháp hạ cấp...). "
    "Hãy trả lời bằng tiếng Việt một cách chuyên nghiệp."
)


@tool
def get_aws_resources_status(app_name: str) -> str:
    """Kiểm tra các tài nguyên AWS có nguy cơ gây lãng phí."""
    resources_by_app = {
        "taco house": (
            "[Dữ liệu thực tế từ AWS]\n"
            "- EC2 Instance id 'i-01234abcd' (Size: m5.xlarge, Chi phí: $140/tháng): "
            "CPU Utilization trung bình 7 ngày qua chỉ có 3%.\n"
            "- EBS Volume id 'vol-09876xyz' (Size: 100GB, Chi phí: $10/tháng): "
            "Trạng thái 'available' (đang bị bỏ hoang, không gắn vào server nào)."
        )
    }

    normalized_name = app_name.strip().lower()
    resources = resources_by_app.get(normalized_name)

    if resources:
        return resources

    return f"Không tìm thấy ứng dụng nào có tên là {app_name} trên hệ thống AWS."


def create_prompt() -> ChatPromptTemplate:
    """Tạo prompt dùng chung cho FinOps agent."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )


def create_agent_executor(api_key: str) -> AgentExecutor:
    """Khởi tạo LLM và bộ điều phối agent."""
    llm = ChatOpenAI(
        model=MODEL_NAME,
        base_url=BASE_URL,
        api_key=api_key,
        temperature=0,
    )
    tools = [get_aws_resources_status]
    agent = create_tool_calling_agent(llm, tools, create_prompt())

    return AgentExecutor(agent=agent, tools=tools, verbose=True)


def run_agent(user_message: str, agent_executor: AgentExecutor) -> str:
    """Gửi yêu cầu đến agent và trả về câu trả lời."""
    response = agent_executor.invoke({"input": user_message})
    return response["output"]


def main() -> None:
    """Đọc cấu hình, chạy yêu cầu mặc định và in kết quả."""
    load_dotenv()
    api_key = os.environ.get("OPENAI_API_KEY")
    DEFAULT_REQUEST = "Hãy tối ưu chi phí cho hệ thống aws của app Taco House"

    if not api_key:
        raise RuntimeError("Set OPENAI_API_KEY before running this script.")

    print(f"User: {DEFAULT_REQUEST}\n")
    print("--- Agent bắt đầu suy nghĩ và hành động ---")

    agent_executor = create_agent_executor(api_key)
    output = run_agent(DEFAULT_REQUEST, agent_executor)

    print("\n--- Kết quả đầu ra (Output) ---")
    print(output)


if __name__ == "__main__":
    main()
