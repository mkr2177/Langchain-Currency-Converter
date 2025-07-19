import streamlit as st
import requests
from langchain_core.tools import tool, InjectedToolArg
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from typing import Annotated
import json

# 🔐 ExchangeRate-API Key
API_KEY = "{EXCHNAGE RATE API KEY}"
CODES_URL = f"https://v6.exchangerate-api.com/v6/{API_KEY}/codes"

# 📌 Caching supported currencies for performance
@st.cache_data(ttl=86400)
def get_supported_currencies():
    try:
        response = requests.get(CODES_URL)
        data = response.json()
        if data['result'] == 'success':
            return [code[0] for code in data['supported_codes']]
    except:
        pass
    return ["USD", "INR", "EUR", "GBP", "JPY"]  # fallback list

# 🛠️ Tool 1: Get live conversion rate
@tool
def get_conversion_factor(base_currency: str, target_currency: str) -> float:
    """Fetches the currency conversion factor between base and target currency."""
    url = f'https://v6.exchangerate-api.com/v6/{API_KEY}/pair/{base_currency}/{target_currency}'
    response = requests.get(url)
    return response.json()

# 🛠️ Tool 2: Convert value using conversion rate
@tool
def convert(base_currency_value: float, conversion_rate: Annotated[float, InjectedToolArg]) -> float:
    """Converts base currency value to target using conversion rate."""
    return base_currency_value * conversion_rate

# 🤖 LLM Setup via OpenRouter + LangChain
llm = ChatOpenAI(
    model="mistralai/mistral-7b-instruct",
    openai_api_key="OPEN ROUTER API KEY",  # Replace with your actual key
    openai_api_base="https://openrouter.ai/api/v1",
    max_tokens=1000
)

llm_with_tools = llm.bind_tools([get_conversion_factor, convert])

# ================= STREAMLIT UI ===================

st.set_page_config(page_title="Currency Converter", page_icon="💱")
st.title("💱 Currency Converter")

# 🌍 Dropdown currency list
currency_options = get_supported_currencies()

# 💵 Input fields
amount = st.number_input("Enter Amount:", min_value=0.0, format="%.2f")
base_currency = st.selectbox("From Currency:", currency_options, index=currency_options.index("USD"))
target_currency = st.selectbox("To Currency:", currency_options, index=currency_options.index("INR"))

if st.button("Convert"):
    with st.spinner("Fetching conversion rate and computing result..."):
        messages = [
            HumanMessage(
                f"What is the conversion factor between {base_currency} and {target_currency}, "
                f"and based on that can you convert {amount} {base_currency} to {target_currency}?"
            )
        ]

        # Step 1: Let LLM decide which tools to call
        ai_message = llm_with_tools.invoke(messages)
        messages.append(ai_message)

        # Step 2: Manually run tool calls
        for tool_call in ai_message.tool_calls:
            if tool_call['name'] == 'get_conversion_factor':
                tool_message1 = get_conversion_factor.invoke(tool_call)
                conversion_rate = json.loads(tool_message1.content)['conversion_rate']
                messages.append(tool_message1)

            if tool_call['name'] == 'convert':
                tool_call['args']['conversion_rate'] = conversion_rate
                tool_message2 = convert.invoke(tool_call)
                messages.append(tool_message2)

        # Step 3: Final LLM response with result
        final_response = llm_with_tools.invoke(messages).content

        # 💡 Optional: Rounded result extraction
        try:
            converted_amount = float(tool_message2.content)
            st.success(f"{amount:.2f} {base_currency} ≈ {converted_amount:.2f} {target_currency}")
        except:
            st.success(final_response)
