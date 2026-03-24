import os
import base64
import mimetypes
import shutil
import docx2txt
from dotenv import load_dotenv
from openai import OpenAI
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS

load_dotenv()

DATA_DIR = "data"
INDEX_DIR = "faiss_index"
TMP_IMAGE_DIR = "_extracted_docx_images"
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4.1-mini")

client = OpenAI()

def image_to_data_url(image_path: str) -> str:
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"

def describe_image(image_path: str) -> str:
    data_url = image_to_data_url(image_path)
    response = client.responses.create(
        model=VISION_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Describe this image for document retrieval. "
                            "If the image contains text, tables, labels, headings, or diagram annotations, "
                            "transcribe the important text faithfully. "
                            "If it is a chart/diagram, summarize what it shows. "
                            "Keep the output concise but information-dense."
                        )
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url
                    }
                ]
            }
        ]
    )
    return (response.output_text or "").strip()

def load_md_or_txt(path: str, name: str):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    return [Document(page_content=text, metadata={"source": name, "type": "text"})]

def load_docx_with_images(path: str, name: str):
    image_dir = os.path.join(TMP_IMAGE_DIR, os.path.splitext(name)[0])
    os.makedirs(image_dir, exist_ok=True)

    text = docx2txt.process(path, image_dir)
    docs = [
        Document(
            page_content=text,
            metadata={"source": name, "type": "docx_text"}
        )
    ]

    image_files = sorted(
        [
            os.path.join(image_dir, fn)
            for fn in os.listdir(image_dir)
            if fn.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp"))
        ]
    )

    for idx, image_path in enumerate(image_files, start=1):
        try:
            image_summary = describe_image(image_path)
            if image_summary:
                docs.append(
                    Document(
                        page_content=(
                            f"[Image {idx} from {name}]\n"
                            f"{image_summary}"
                        ),
                        metadata={
                            "source": name,
                            "type": "docx_image",
                            "image_file": os.path.basename(image_path),
                            "image_index": idx
                        }
                    )
                )
                print(f"Processed image {idx}: {os.path.basename(image_path)}")
        except Exception as e:
            print(f"Failed to analyze image {image_path}: {e}")

    return docs

def load_docs():
    docs = []
    os.makedirs(TMP_IMAGE_DIR, exist_ok=True)

    for name in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, name)

        if name.lower().endswith((".md", ".txt")):
            docs.extend(load_md_or_txt(path, name))
        elif name.lower().endswith(".docx"):
            docs.extend(load_docx_with_images(path, name))

    return docs

def main():
    docs = load_docs()
    if not docs:
        raise ValueError("No documents found in ./data.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150
    )
    chunks = splitter.split_documents(docs)

    embeddings = OpenAIEmbeddings()
    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(INDEX_DIR)

    print(f"Loaded {len(docs)} documents/fragments")
    print(f"Built {len(chunks)} chunks")
    print(f"Index built and saved to ./{INDEX_DIR}")

if __name__ == "__main__":
    try:
        main()
    finally:
        if os.path.exists(TMP_IMAGE_DIR):
            shutil.rmtree(TMP_IMAGE_DIR, ignore_errors=True)