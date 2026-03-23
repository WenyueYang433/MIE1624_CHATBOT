import os
from dotenv import load_dotenv

load_dotenv()
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
INDEX_DIR = "faiss_index"

LAST_RETRIEVAL_LOGS = []

embeddings = OpenAIEmbeddings()
db = FAISS.load_local(
    INDEX_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)
retriever = db.as_retriever(search_kwargs={"k": 2})

@tool("retrieve_course_context")
def retrieve_course_context(query: str) -> str:
    """Retrieve relevant evidence from the indexed knowledge base."""
    global LAST_RETRIEVAL_LOGS
    LAST_RETRIEVAL_LOGS = []

    docs = retriever.invoke(query)

    if not docs:
        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": "No relevant context found in the knowledge base."
        })
        return "No relevant context found in the knowledge base."

    results = []
    seen_sources = set()

    LAST_RETRIEVAL_LOGS.append({
        "agent": "Researcher",
        "message": f"Retrieved {len(docs)} relevant document chunks."
    })

    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "unknown_source")
        content = d.page_content.strip()
        short_content = content[:800]
        snippet = content[:200].replace("\n", " ").strip()

        results.append(f"[Doc {i}] Source: {source}\n{short_content}")

        if source not in seen_sources:
            LAST_RETRIEVAL_LOGS.append({
                "agent": "Researcher",
                "message": f"Found source: {source}"
            })
            seen_sources.add(source)

        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": f"Doc {i} snippet: {snippet}..."
        })

    return "\n\n".join(results)

def build_agents():
    llm = LLM(model=MODEL_NAME, temperature=0)

    researcher = Agent(
        role="Researcher",
        goal="Find the most relevant evidence in the knowledge base to answer user questions.",
        backstory=(
            "You are a policy and evidence researcher. "
            "Your task is to search the indexed materials and extract the most relevant facts and findings."
        ),
        tools=[retrieve_course_context],
        llm=llm,
        verbose=False,
        memory=False,
        max_iter=1,
        allow_delegation=False
    )

    writer = Agent(
        role="Writer",
        goal="Write a clear, grounded, user-facing answer based only on retrieved evidence.",
        backstory=(
            "You are a professional writer who explains technical and policy ideas clearly and concisely. "
            "You must write grounded answers and avoid unsupported claims."
        ),
        llm=llm,
        verbose=False,
        memory=False,
        max_iter=1,
        allow_delegation=False
    )

    return researcher, writer

def run_chatbot(user_question: str, use_retrieval: bool = True):
    global LAST_RETRIEVAL_LOGS
    LAST_RETRIEVAL_LOGS = []
    print(use_retrieval)
    if use_retrieval:
        researcher, writer = build_agents()

        research_task = Task(
            description=f"Question: {user_question}\nRetrieve relevant facts from the knowledge base with sources only.",
            expected_output="Concise evidence summary.",
            agent=researcher
        )

        writing_task = Task(
            description=f"Question: {user_question}\nAnswer only from the retrieved summary. Be concise and factual.",
            expected_output="Grounded final answer.",
            agent=writer,
            context=[research_task]
        )

        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, writing_task],
            process=Process.sequential,
            verbose=False,
            memory=False,
            planning=False
        )

        result = crew.kickoff()

        logs = list(LAST_RETRIEVAL_LOGS)
        logs.append({
            "agent": "Writer",
            "message": "Generated final answer from retrieved evidence."
        })

        return {
            "reply": str(result),
            "logs": logs
        }

    llm = LLM(model=MODEL_NAME, temperature=0)
    reply = llm.call(f"Answer clearly:\n{user_question}")

    return {
        "reply": str(reply),
        "logs": [
            {"agent": "Assistant", "message": "Answered directly in chat mode."}
        ]
    }