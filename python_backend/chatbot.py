import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
INDEX_DIR = os.getenv("INDEX_DIR", "faiss_index")

LAST_RETRIEVAL_LOGS = []

embeddings = OpenAIEmbeddings()
db = FAISS.load_local(
    INDEX_DIR,
    embeddings,
    allow_dangerous_deserialization=True
)
retriever = db.as_retriever(search_kwargs={"k": 3})

def _basename(source: str) -> str:
    if not source:
        return "unknown_file"
    return os.path.basename(source)

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown_site"
    except Exception:
        return "unknown_site"

@tool("retrieve_local_context")
def retrieve_local_context(query: str) -> str:
    """Retrieve relevant evidence from the local indexed knowledge base."""
    global LAST_RETRIEVAL_LOGS

    docs = retriever.invoke(query)

    if not docs:
        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": "Searched local files: none matched."
        })
        return "No relevant local context found."

    results = []
    seen_files = []

    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "unknown_source")
        filename = _basename(source)
        content = d.page_content.strip()
        short_content = content[:800]
        snippet = content[:180].replace("\n", " ").strip()

        results.append(f"[Local Doc {i}] File: {filename}\n{short_content}")

        if filename not in seen_files:
            seen_files.append(filename)

        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": f"Local hit {i}: file={filename}; snippet={snippet}..."
        })

    LAST_RETRIEVAL_LOGS.append({
        "agent": "Researcher",
        "message": f"Searched local files: {', '.join(seen_files)}"
    })

    return "\n\n".join(results)

@tool("search_web")
def search_web(query: str) -> str:
    """Search the web for public information and return concise evidence."""
    global LAST_RETRIEVAL_LOGS

    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        domains = []

        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=5))

        if not search_results:
            LAST_RETRIEVAL_LOGS.append({
                "agent": "Researcher",
                "message": "Searched websites: none matched."
            })
            return "No relevant web results found."

        for i, item in enumerate(search_results[:5], start=1):
            title = item.get("title", "").strip()
            href = item.get("href", "").strip()
            body = item.get("body", "").strip()
            domain = _domain(href)

            if domain and domain not in domains:
                domains.append(domain)

            results.append(
                f"[Web Result {i}] Title: {title}\n"
                f"Site: {domain}\n"
                f"URL: {href}\n"
                f"Snippet: {body}"
            )

            LAST_RETRIEVAL_LOGS.append({
                "agent": "Researcher",
                "message": f"Web hit {i}: site={domain}; title={title}"
            })

        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": f"Searched websites: {', '.join(domains)}"
        })

        return "\n\n".join(results)

    except Exception as e:
        LAST_RETRIEVAL_LOGS.append({
            "agent": "Researcher",
            "message": f"Web search failed: {str(e)}"
        })
        return f"Web search failed: {str(e)}"

def build_agents():
    llm = LLM(model=MODEL_NAME, temperature=0)

    researcher = Agent(
        role="Researcher",
        goal="Find relevant evidence from local indexed files and the public web.",
        backstory=(
            "You are a research assistant. "
            "You search local documents and the web for evidence relevant to the user's question. "
            "You must not fabricate sources."
        ),
        tools=[retrieve_local_context, search_web],
        llm=llm,
        verbose=False,
        memory=False,
        max_iter=2,
        allow_delegation=False
    )

    analyst = Agent(
        role="Analyst",
        goal="Analyze the research evidence, identify the key facts, compare sources, and form a grounded conclusion.",
        backstory=(
            "You are an analyst. "
            "You read the researcher's evidence, identify what matters most, resolve conflicts if possible, "
            "and produce a concise analytical summary with uncertainty clearly stated when needed."
        ),
        llm=llm,
        verbose=False,
        memory=False,
        max_iter=1,
        allow_delegation=False
    )

    writer = Agent(
        role="Writer",
        goal="Write a clear final answer based only on the analyst's output.",
        backstory=(
            "You are a writer. "
            "You do not do retrieval. "
            "You do not analyze raw evidence directly. "
            "You only transform the analyst's conclusions into a concise, user-facing response."
        ),
        llm=llm,
        verbose=False,
        memory=False,
        max_iter=1,
        allow_delegation=False
    )

    return researcher, analyst, writer

def run_chatbot(user_question: str, use_retrieval: bool = True):
    global LAST_RETRIEVAL_LOGS
    LAST_RETRIEVAL_LOGS = []

    print(f"use_retrieval={use_retrieval}")

    if use_retrieval:
        researcher, analyst, writer = build_agents()

        research_task = Task(
            description=(
                f"User question: {user_question}\n\n"
                "You must do both of the following:\n"
                "1. Search local indexed files for relevant evidence.\n"
                "2. Search the public web for relevant evidence.\n\n"
                "Return a research bundle that includes:\n"
                "- local evidence\n"
                "- web evidence\n"
                "- file names\n"
                "- website domains\n"
                "Do not fabricate sources."
            ),
            expected_output=(
                "A research bundle containing local evidence, web evidence, file names, and website domains."
            ),
            agent=researcher
        )

        analysis_task = Task(
            description=(
                f"User question: {user_question}\n\n"
                "Analyze the research bundle from the Researcher.\n"
                "Your output must include:\n"
                "- key findings\n"
                "- which evidence is most relevant\n"
                "- whether local files and web results agree or conflict\n"
                "- uncertainties or limitations\n"
                "Be concise and structured."
            ),
            expected_output=(
                "A concise analytical summary with key findings, evidence comparison, and uncertainty notes."
            ),
            agent=analyst,
            context=[research_task]
        )

        writing_task = Task(
            description=(
                f"User question: {user_question}\n\n"
                "Write the final answer using only the Analyst's output.\n"
                "Do not introduce new facts.\n"
                "Be clear, concise, and user-facing."
            ),
            expected_output="A grounded final answer.",
            agent=writer,
            context=[analysis_task]
        )

        crew = Crew(
            agents=[researcher, analyst, writer],
            tasks=[research_task, analysis_task, writing_task],
            process=Process.sequential,
            verbose=False,
            memory=False,
            planning=False
        )

        result = crew.kickoff()

        logs = list(LAST_RETRIEVAL_LOGS)
        logs.append({
            "agent": "Analyst",
            "message": "Analyzed the research evidence and produced a structured conclusion."
        })
        logs.append({
            "agent": "Writer",
            "message": "Wrote the final answer from the analyst's output."
        })

        return {
            "reply": str(result),
            "logs": logs
        }

    llm = LLM(model=MODEL_NAME, temperature=0)
    reply = llm.call(f"Answer clearly and concisely:\n{user_question}")

    return {
        "reply": str(reply),
        "logs": [
            {"agent": "Assistant", "message": "Answered directly in chat mode."}
        ]
    }