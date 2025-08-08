# RAG System with Ubuntu Service (Python) and C# Client

This project implements a local Retrieval-Augmented Generation (RAG) service running on Ubuntu (Python-based), with a Windows client written in C#.

## Project Structure

- `localkb/`: Python RAG service using LangChain/Ollama/etc.
- `KnowledgeClient/`: C# WinForms app for interacting with the RAG service
- `docs/`: Architecture diagrams, usage instructions, etc.

## Features

- Local-only operation over LAN
- semantic search with rerank and LLM response using FAISS/vector DB
- C# client communicates with the Python API over HTTP
- automatic vector update to match the changes to the document folder

## Requirements

- Ubuntu 20.04+ with Python 3.9+
- Windows with .NET SDK for building the client
- Local network connectivity

## Setup Instructions

### RAG Service (Ubuntu)
```bash
cd localkb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
