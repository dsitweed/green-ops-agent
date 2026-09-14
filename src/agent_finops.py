import os
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent, tool

load_dotenv()

if not os.environ.get("OPENAI_API_KEY"):
    raise RuntimeError("Set OPENAI_API_KEY before running this script.")

# ==========================================
# 1. ĐỊNH NGHĨA CÔNG CỤ (TOOLS)
# ==========================================

@tool
def get_aws_resources_status(app_name: str) -> str:
    """
    Hãy gọi hàm này khi người dùng muốn kiểm tra trạng thái lãng phí tài nguyên AWS của một ứng dụng cụ thể.
    Hàm này trả về danh sách các server EC2 có CPU quá thấp hoặc ổ đĩa EBS không dùng.
    """
    # Trong thực tế (MVP nâng cao), chỗ này bạn sẽ dùng thư viện `boto3` để gọi AWS API thực tế.
    if app_name.lower() == "taco house":
        return """
        [Dữ liệu thực tế từ AWS]
        - EC2 Instance id 'i-01234abcd' (Size: m5.xlarge, Chi phí: $140/tháng): CPU Utilization trung bình 7 ngày qua chỉ có 3%.
        - EBS Volume id 'vol-09876xyz' (Size: 100GB, Chi phí: $10/tháng): Trạng thái 'available' (đang bị bỏ hoang, không gắn vào server nào).
        """
    else:
        return f"Không tìm thấy ứng dụng nào có tên là {app_name} trên hệ thống AWS."


tools = [get_aws_resources_status]

# ==========================================
# 2. CẤU HÌNH BỘ NÃO (LLM) & HƯỚNG DẪN (PROMPT)
# ==========================================
llm = ChatOpenAI(
    model="apu-gpt-5.6-sol",
    base_url="https://luvenia-uncommuted-hypermorally.ngrok-free.dev/v1",
    api_key= os.environ.get("OPENAI_API_KEY"),
)

# Viết System Prompt để định hình "tính cách" và "nhiệm vụ" cho Agent
prompt = ChatPromptTemplate.from_messages([
    ("system", ""
        "Bạn là một chuyên gia FinOps xuất sắc chuyên tối ưu chi phí AWS. "
        "Khi nhận được yêu cầu tối ưu cho một ứng dụng, bạn PHẢI sử dụng công cụ `get_aws_resources_status` "
        "để lấy dữ liệu thực tế trước, tuyệt đối không được tự bịa ra số liệu. "
        "Sau khi có dữ liệu, hãy phân tích và đưa ra lời khuyên tối ưu chi phí cụ thể (số tiền tiết kiệm được, giải pháp hạ cấp...). "
        "Hãy trả lời bằng tiếng Việt một cách chuyên nghiệp."
    ""),
    ("human", "{input}"),
    # Vị trí để LangChain lưu lịch sử suy nghĩ và kết quả gọi Tool của Agent
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# ==========================================
# 3. KHỞI TẠO VÀ CHẠY AGENT
# ==========================================
agent = create_tool_calling_agent(llm, tools, prompt)

# AgentExecutor là bộ điều khiển vòng lặp: Nhận lệnh -> Suy nghĩ -> Gọi Tool -> Nhận kết quả Tool -> Trả lời khách hàng
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

user_message = "Hãy tối ưu chi phí cho hệ thống aws của app Taco House"

print(f"User: {user_message}\n")
print("--- Agent bắt đầu suy nghĩ và hành động ---")

response = agent_executor.invoke({"input": user_message})

print("\n--- Kết quả đầu ra (Output) ---")
print(response["output"])
