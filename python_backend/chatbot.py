import os
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dotenv import load_dotenv

#environment variable
load_dotenv()
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"

from crewai import Agent, Task, Crew, Process, LLM
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INDEX_DIR = BASE_DIR / "faiss_index"
INDEX_DIR = Path(os.getenv("INDEX_DIR", str(DEFAULT_INDEX_DIR))).resolve()

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LOCAL_TOP_K = int(os.getenv("LOCAL_TOP_K", "2"))
WEB_TOP_K = int(os.getenv("WEB_TOP_K", "5"))
RESEARCH_TIMEOUT = int(os.getenv("RESEARCH_TIMEOUT", "15"))

LAST_RETRIEVAL_LOGS = []

index_faiss = INDEX_DIR / "index.faiss"
index_pkl = INDEX_DIR / "index.pkl"
if not index_faiss.exists() or not index_pkl.exists():
    raise FileNotFoundError(
        f"FAISS index files not found. INDEX_DIR={INDEX_DIR}, "
        f"index.faiss exists={index_faiss.exists()}, index.pkl exists={index_pkl.exists()}"
    )

embeddings = OpenAIEmbeddings()
db = FAISS.load_local(str(INDEX_DIR), embeddings, allow_dangerous_deserialization=True)
retriever = db.as_retriever(search_kwargs={"k": LOCAL_TOP_K})

#Extract the file name
def _basename(source: str) -> str:
    if not source:
        return "unknown_file"
    return os.path.basename(source)

def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown_site"
    except Exception:
        return "unknown_site"

#Local Knowledge Base Search
def retrieve_local_context(query: str) -> str:
    global LAST_RETRIEVAL_LOGS
    docs = retriever.invoke(query)
    if not docs:
        LAST_RETRIEVAL_LOGS.append({
            "agent": "LocalResearcher",
            "message": "Searched local files: none matched."
        })
        return "No relevant local context found."

    results = []
    seen_files = []
    for i, d in enumerate(docs, start=1):
        source = d.metadata.get("source", "unknown_source")
        filename = _basename(source)
        content = d.page_content.strip()
        short_content = content[:300]
        snippet = content[:100].replace("\n", " ").strip()
        results.append(f"[Local Doc {i}] File: {filename}\nEvidence: {short_content}")
        if filename not in seen_files:
            seen_files.append(filename)
        LAST_RETRIEVAL_LOGS.append({
            "agent": "LocalResearcher",
            "message": f"Local hit {i}: file={filename}; snippet={snippet}..."
        })

    LAST_RETRIEVAL_LOGS.append({
        "agent": "LocalResearcher",
        "message": f"Searched local files: {', '.join(seen_files)}"
    })
    return "\n\n".join(results)

#web search
def search_web(query: str) -> str:
    global LAST_RETRIEVAL_LOGS
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                LAST_RETRIEVAL_LOGS.append({
                    "agent": "WebResearcher",
                    "message": "Web search dependency is missing. Install ddgs."
                })
                return "Web search is unavailable because the ddgs package is not installed."

        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=WEB_TOP_K))

        if not search_results:
            LAST_RETRIEVAL_LOGS.append({
                "agent": "WebResearcher",
                "message": "Searched websites: none matched."
            })
            return "No relevant web results found."

        results = []
        domains = []
        for i, item in enumerate(search_results[:WEB_TOP_K], start=1):
            title = item.get("title", "").strip()
            href = item.get("href", "").strip()
            body = item.get("body", "").strip()[:160]
            domain = _domain(href)
            if domain not in domains:
                domains.append(domain)
            results.append(
                f"[Web Result {i}] Title: {title}\n"
                f"Site: {domain}\n"
                f"Snippet: {body}"
            )
            LAST_RETRIEVAL_LOGS.append({
                "agent": "WebResearcher",
                "message": f"Web hit {i}: site={domain}; title={title}"
            })

        LAST_RETRIEVAL_LOGS.append({
            "agent": "WebResearcher",
            "message": f"Searched websites: {', '.join(domains)}"
        })
        return "\n\n".join(results)

    except Exception as e:
        LAST_RETRIEVAL_LOGS.append({
            "agent": "WebResearcher",
            "message": f"Web search failed: {str(e)}"
        })
        return f"Web search failed: {str(e)}"

llm = LLM(model=MODEL_NAME, temperature=0)

#Generate the final answer
analyst = Agent(
    role="Analyst",
    goal="Analyze the research evidence and produce the final answer.",
    backstory=(
        "You are an analyst. "
        "Read the local and web evidence, keep only the most important facts, "
        "note uncertainty only when needed, and write a short final answer."
    ),
    llm=llm,
    verbose=False,
    memory=False,
    max_iter=1,
    allow_delegation=False
)

def _run_local_research(query: str) -> str:
    return retrieve_local_context(query)

def _run_web_research(query: str) -> str:
    return search_web(query)

#Parallel Execution of Local Search and Network Search
def run_parallel_research(user_question: str, enable_web_search: bool = True):
    local_result = "No local research result."
    web_result = "Web search disabled."

    if not enable_web_search:
        try:
            local_result = _run_local_research(user_question)
        except Exception as e:
            local_result = f"Local research failed: {str(e)}"
            LAST_RETRIEVAL_LOGS.append({
                "agent": "LocalResearcher",
                "message": local_result
            })
        LAST_RETRIEVAL_LOGS.append({
            "agent": "WebResearcher",
            "message": "Web search is disabled by user setting."
        })
        return local_result, web_result

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_local = executor.submit(_run_local_research, user_question)
        future_web = executor.submit(_run_web_research, user_question)

        try:
            local_result = future_local.result(timeout=RESEARCH_TIMEOUT)
        except FuturesTimeoutError:
            local_result = f"Local research timed out after {RESEARCH_TIMEOUT} seconds."
            LAST_RETRIEVAL_LOGS.append({
                "agent": "LocalResearcher",
                "message": local_result
            })
        except Exception as e:
            local_result = f"Local research failed: {str(e)}"
            LAST_RETRIEVAL_LOGS.append({
                "agent": "LocalResearcher",
                "message": local_result
            })

        try:
            web_result = future_web.result(timeout=RESEARCH_TIMEOUT)
        except FuturesTimeoutError:
            web_result = f"Web research timed out after {RESEARCH_TIMEOUT} seconds."
            LAST_RETRIEVAL_LOGS.append({
                "agent": "WebResearcher",
                "message": web_result
            })
        except Exception as e:
            web_result = f"Web research failed: {str(e)}"
            LAST_RETRIEVAL_LOGS.append({
                "agent": "WebResearcher",
                "message": web_result
            })

    return local_result, web_result

#The main logic of the chatbot
def run_chatbot(user_question: str, enable_web_search: bool = True):
    global LAST_RETRIEVAL_LOGS
    LAST_RETRIEVAL_LOGS = []

    local_research_bundle, web_research_bundle = run_parallel_research(
        user_question,
        enable_web_search=enable_web_search
    )

    analysis_task = Task(
    description=(
        f"User question: {user_question}\n\n"
        "You are given two research bundles.\n\n"
        "LOCAL RESEARCH BUNDLE:\n"
        f"{local_research_bundle}\n\n"
        "WEB RESEARCH BUNDLE:\n"
        f"{web_research_bundle}\n\n"
        "Your role is to answer questions specifically related to Canada's AI strategy.\n\n"
        "Instructions:\n"
        "- First determine whether the user question is related to AI strategy.\n"
        "- If the question is unrelated, do not answer it directly. Instead, politely explain that your role is limited to answering questions about Canada's AI strategy.\n"
        "- If the question is related, analyze both research bundles before answering.\n"
        "- Prefer local evidence when it is directly relevant.\n"
        "- Use web evidence only as supplementary support.\n"
        "- Keep only the most important findings.\n"
        "- State uncertainty only when it materially affects the answer.\n"
        "- Do not add unsupported facts.\n"
        "- Use the response format that best fits the question. You may use paragraphs, short lists, or bullet points only when helpful.\n"
        "- Keep the answer concise and clear, with a maximum of 200 words."
    ),
        expected_output="A short, grounded final answer.",
        agent=analyst
    )

    crew = Crew(
        agents=[analyst],
        tasks=[analysis_task],
        process=Process.sequential,
        verbose=False,
        memory=False,
        planning=False
    )

    result = crew.kickoff()

    logs = list(LAST_RETRIEVAL_LOGS)
    logs.append({
        "agent": "Analyst",
        "message": "Analyzed the research bundles and wrote the final answer."
    })

    return {
        "reply": str(result),
        "logs": logs
    }

if __name__ == "__main__":
    while True:
        try:
            user_question = input("\nUser: ").strip()
            if user_question.lower() in {"exit", "quit"}:
                print("Bye.")
                break

            enable_web = input("Enable web search? (y/n): ").strip().lower() == "y"
            result = run_chatbot(user_question, enable_web_search=enable_web)

            print("\nAssistant:\n")
            print(result["reply"])

            print("\nLogs:")
            for log in result["logs"]:
                print(f"- [{log['agent']}] {log['message']}")

        except KeyboardInterrupt:
            print("\nBye.")
            break
        except Exception as e:
            print(f"\nError: {e}")