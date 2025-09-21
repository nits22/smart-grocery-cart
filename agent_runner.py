# agent_runner.py
import os
import json
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv
load_dotenv()

from langchain.agents import initialize_agent, Tool

# local tools - your repo's utilities
from lc_tools import PriceCheckerTool, OptimizerTool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Google Gemini LLM factory ----------
def build_gemini_llm():
    """Build Google Gemini LLM with no test calls to avoid startup delays"""
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key or google_api_key == "your_google_api_key_here":
        logger.warning("GOOGLE_API_KEY not found in environment")
        return None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info("🔧 Initializing Google Gemini LLM...")

        # Updated model name - Google has changed from gemini-pro to gemini-1.5-flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # Updated model name
            google_api_key=google_api_key,
            temperature=0.2,
            max_output_tokens=300
        )

        # DO NOT test the LLM during initialization - causes startup delays
        logger.info(f"✅ Gemini LLM initialized (no test call)")
        return llm

    except ImportError:
        logger.warning("langchain_google_genai not available. Install with: pip install langchain-google-genai")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini LLM: {e}")
        return None

# --- Alternative LLM factory using OpenAI ----------
def build_openai_llm():
    """Try OpenAI as an alternative with no test calls"""
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key or openai_key == "your_openai_api_key_here":
        logger.warning("OPENAI_API_KEY not found in environment")
        return None

    try:
        from langchain_openai import ChatOpenAI
        logger.info("🔧 Initializing OpenAI LLM as primary...")

        llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            openai_api_key=openai_key,
            temperature=0.2,
            max_tokens=200
        )

        # DO NOT test the LLM during initialization - causes startup delays
        logger.info(f"✅ OpenAI LLM initialized successfully")
        return llm

    except ImportError as e:
        logger.warning(f"langchain_openai not available: {e}")
        logger.info("💡 Install with: pip install langchain-openai")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to initialize OpenAI LLM: {e}")
        return None

# --- Simple fallback LLM for testing ----------
def build_simple_test_llm():
    """Create a simple test LLM that just echoes responses for testing"""
    class TestLLM:
        def invoke(self, prompt):
            class TestResponse:
                def __init__(self, content):
                    self.content = content

            # Simple rule-based responses for grocery optimization
            if "grocery" in prompt.lower() or "shopping" in prompt.lower():
                return TestResponse("Great optimization! You found the best prices across multiple stores. This multi-store approach saves you money compared to shopping at just one location. Consider the delivery fees and travel time when deciding your final shopping strategy.")
            else:
                return TestResponse("4")  # Simple test response

    logger.info("🔧 Using simple test LLM for demonstration")
    return TestLLM()

# --- Enhanced LLM factory with test LLM as primary ----------
def build_hf_llm(repo_id: str = None, temperature: float = 0.2, max_length: int = 150):
    """
    Build LLM with test LLM as primary (since both OpenAI and Gemini have quota issues), then OpenAI, then Gemini
    """

    # Try test LLM first (since both APIs have quota issues)
    logger.info("🔄 Using test LLM as primary due to API quota issues...")
    test_llm = build_simple_test_llm()
    if test_llm:
        logger.info("✅ Using test LLM as primary")
        return test_llm

    # Try OpenAI as fallback
    logger.info("🔄 Trying OpenAI as fallback...")
    openai_llm = build_openai_llm()
    if openai_llm:
        logger.info("✅ Using OpenAI as fallback LLM")
        return openai_llm

    # Fallback to Gemini if OpenAI fails
    try:
        gemini_llm = build_gemini_llm()
        if gemini_llm:
            return gemini_llm
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            logger.warning("🚫 Gemini quota exceeded")
        else:
            logger.warning(f"⚠️ Gemini failed: {e}")

    # Final fallback
    logger.info("🔄 All LLMs unavailable, using basic test LLM...")
    return build_simple_test_llm()

# --- Tools ----------
price_tool = PriceCheckerTool()
opt_tool = OptimizerTool()

TOOLS = [
    Tool(name=price_tool.name, func=price_tool._run, description=price_tool.description),
    Tool(name=opt_tool.name, func=opt_tool._run, description=opt_tool.description),
]

# --- Agent builder ----------
def create_agent(llm=None, tools=TOOLS, verbose: bool = True):
    """
    Build and return an agent (LangChain) wired with given llm and tools.
    If llm is None, build_hf_llm() will be used with default model.
    """
    if llm is None:
        llm = build_hf_llm()
        if llm is None:
            logger.error("No LLM available. Please set HUGGINGFACEHUB_API_TOKEN environment variable.")
            return None

    try:
        # Using zero-shot react description as a default agent style. If your langchain
        # version complains about the "agent" string, consult your version docs and adjust.
        agent = initialize_agent(
            tools, llm, agent="zero-shot-react-description", verbose=verbose
        )
        return agent
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return None

# --- Lazy initialization - only create agent when needed ----------
_cached_agent = None

def get_agent():
    """
    Get the agent using lazy initialization - only creates it when first needed.
    This prevents unnecessary LLM calls during app startup.
    """
    global _cached_agent
    if _cached_agent is None:
        logger.info("🚀 Creating agent on first use (lazy initialization)")
        _cached_agent = create_agent()
    return _cached_agent

def reset_agent():
    """Reset the cached agent to force re-initialization with new LLM priority"""
    global _cached_agent
    _cached_agent = None
    logger.info("🔄 Agent cache cleared - will reinitialize with new LLM priority")
