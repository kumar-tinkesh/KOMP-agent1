import sys
import os
from dotenv import load_dotenv

# Resolve root directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load environment variables (API key)
load_dotenv()

# pyrefly: ignore [missing-import]
from llm.geminiClient import GeminiClient

llm = GeminiClient()
# Later:
# llm = OpenAIClient()
# llm = ClaudeClient()

context_data = "Abhishek's favorite color is blue. He owns 3 cats."

print("--- Test 1: Query in Context ---")
response_1 = llm.generate(
    query="What is Abhishek's favorite color?",
    context=context_data
)
print("Query: What is Abhishek's favorite color?")
print("Response:", response_1.strip())
print()

print("--- Test 2: Query NOT in Context ---")
response_2 = llm.generate(
    query="What is Abhishek's age?",
    context=context_data
)
print("Query: What is Abhishek's age?")
print("Response:", response_2.strip())
print()

print("--- Test 3: Unstructured Multimodal Context -> Structured Response ---")
unstructured_context = """
hey, just wanted to let you know that we got the invoices.
Bill: John Doe - $150.00 for cleaning services on 2026-07-20.
Invoice #23891 from Acme Corp for consulting - $1200.00 dated 2026-07-22.
Also got a receipt for Jane Smith, developer fee, $500, paid on 2026-07-25.
"""

response_3 = llm.generate_structured(
    context=unstructured_context,
    prompt="Extract all billing items and format them into a clean Markdown table with headers: Date, Customer/Vendor, Description, Price."
)
print(response_3.strip())