# Group 7 Chatbot
An AI web chatbot system built with a Node.js frontend server and a Python backend.  
The project supports local document retrieval, optional web search, multi-agent assistance and text-to-speech output.

## Project Overview

This project is a web-based chatbot designed to answer user questions by combining:

- Local document retrieval with FAISS
- LLM-based response generation
- Optional web search
- Optional text-to-speech (TTS)
- A simple browser-based frontend

The system uses a **Node.js server** to serve the frontend and forward chat requests, while a **Flask backend** handles retrieval and response generation.

## Features

- Chat interface in browser
- Retrieval-augmented generation from local files
- FAISS vector index for efficient document search
- Optional web information retrieval
- Optional text-to-speech output using OpenAI audio API
- Deployable on Google Cloud Run

## Project Structure

```text
.
├── frontend/                 # Frontend static files
├── python_backend/           # Python backend
│   ├── app.py                # Flask API
│   ├── chatbot.py            # Main chatbot logic
│   ├── build_index.py        # Build FAISS index from local documents
│   ├── data/                 # Local source documents
│   └── faiss_index/          # Saved FAISS index
├── server/                   # Node.js web server
│   ├── server.js
│   └── package.json
├── requirements.txt
├── Dockerfile
└── .dockerignore

## Development Environment

This project was developed and tested with the following local environment:

- **Operating System:** Windows
- **Node.js:** v24.14.0
- **npm:** 11.9.0
- **Python:** 3.11.9
- **pip:** 26.0.1
- **Git:** 2.51.1

## Prerequisites

Before running the project, make sure the following software is installed:

- **Node.js**
- **npm**
- **Python 3.11+**
- **pip**
- **Git**

An **OpenAI API key** is also required for chatbot generation and optional text-to-speech features.


