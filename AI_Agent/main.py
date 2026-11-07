"""
AquaSentry research agent (command line).

Asks a research question, lets the model search the web / Wikipedia and save notes,
then prints a structured answer (topic, summary, sources, tools used).

Provider is chosen from the keys in AI_Agent/.env:
    ANTHROPIC_API_KEY=...   -> Claude (default model below, override with AGENT_MODEL)
    OPENAI_API_KEY=...      -> OpenAI (default model below, override with AGENT_MODEL)
If both are set, AGENT_PROVIDER=anthropic|openai picks one.

Run:  pip install -r AI_Agent/requirements.txt
      python AI_Agent/main.py
"""

import os
import sys

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.agents import create_tool_calling_agent, AgentExecutor

from tools import search_tool, wiki_tool, save_tool

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o"}


class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]


def make_llm():
    has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
    has_openai = bool(os.getenv("OPENAI_API_KEY"))
    provider = (os.getenv("AGENT_PROVIDER") or ("anthropic" if has_anthropic else "openai" if has_openai else "")).lower()
    model = os.getenv("AGENT_MODEL") or DEFAULT_MODELS.get(provider, "")
    if provider == "anthropic" and has_anthropic:
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model), provider, model
    if provider == "openai" and has_openai:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=model), provider, model
    sys.exit("No API key found. Put ANTHROPIC_API_KEY=... or OPENAI_API_KEY=... in AI_Agent/.env and try again.")


def output_text(raw_response) -> str:
    """Claude returns a list of content blocks; OpenAI returns a plain string."""
    out = raw_response.get("output")
    if isinstance(out, list):
        return "".join(block.get("text", "") if isinstance(block, dict) else str(block) for block in out)
    return str(out or "")


def main():
    llm, provider, model = make_llm()
    print(f"[agent] Using {provider} model {model}")
    parser = PydanticOutputParser(pydantic_object=ResearchResponse)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
                You are a research assistant that helps write a research paper about water quality.
                Answer the user's question and use the tools when needed.
                Wrap the output in this format and provide no other text\n{format_instructions}
                """,
            ),
            ("placeholder", "{chat_history}"),
            ("human", "{query}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    ).partial(format_instructions=parser.get_format_instructions())

    tools = [search_tool, wiki_tool, save_tool]
    agent = create_tool_calling_agent(llm=llm, prompt=prompt, tools=tools)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    query = input("What can I help you research? ")
    raw_response = agent_executor.invoke({"query": query})
    text = output_text(raw_response)
    try:
        print(parser.parse(text))
    except Exception as e:
        print("Could not parse the answer into the structured format:", e)
        print("Raw answer:\n", text)


if __name__ == "__main__":
    main()
