
# GroundCheck

GroundCheck is a Retrieval-Augmented Generation (RAG) system that enables users to ask questions about any YouTube video and receive answers strictly grounded in the video’s transcript. The system enforces source-based answering and includes a secondary evaluation layer to detect hallucinations in model responses.

---

# Overview

GroundCheck takes a YouTube video link, extracts its transcript, and converts the content into a searchable knowledge base using vector embeddings. When a user asks a question, the system retrieves the most relevant segments of the transcript and generates an answer using a large language model constrained to the provided context.

A second LLM call evaluates the generated answer for faithfulness, completeness, and hallucination risk, producing a final reliability verdict.

---

# Key Features

* Context-grounded question answering from YouTube transcripts
* Retrieval-Augmented Generation (RAG) pipeline
* Semantic search using vector embeddings
* Strict prompt design to prevent use of external knowledge
* Hallucination detection using LLM-based evaluation
* Admin panel for session logging and analytics
* Local caching and transcript handling
* End-to-end system built with Streamlit interface

---

# Architecture

The system follows a standard RAG pipeline with an additional evaluation layer:

1. Input: User provides a YouTube video URL
2. Transcript Extraction: Transcript is fetched using YouTube Transcript API 
3. Chunking: Transcript is split into overlapping text chunks
4. Embedding: Each chunk is converted into vector embeddings using Sentence Transformers 
5. Storage: Embeddings are stored in ChromaDB vector database 
6. Retrieval: Relevant chunks are retrieved based on semantic similarity
7. Generation: LLaMA 3.3 70B (via Groq API) generates answers constrained to retrieved context 
8. Evaluation: A second LLM call evaluates the answer for hallucination and reliability
9. Logging: Session data is stored for analysis

---

# Tech Stack

* Python
* Streamlit
* Groq API (LLaMA 3.3 70B)
* Sentence Transformers
* ChromaDB
* YouTube Transcript API
* dotenv

Dependencies are defined in requirements.txt 

---

# Project Structure

* app.py – Main Streamlit application containing the full pipeline
* Groundcheck_notebook.ipynb – Experimental notebook for development and testing
* requirements.txt – List of dependencies

---

# How It Works

1. User enters a YouTube link
2. System extracts and processes the transcript
3. Transcript is converted into embeddings and stored
4. User asks a question
5. System retrieves relevant context
6. LLM generates a grounded answer
7. Evaluation layer checks for hallucination
8. Final answer and reliability status are displayed

---

# Hallucination Detection

The system includes a second-stage evaluation using the same LLM to assess:

* Faithfulness (alignment with source content)
* Completeness of the answer
* Presence of hallucination
* Final verdict (Trusted or Flagged)

This adds an additional layer of reliability beyond standard RAG systems.

---

# Admin Panel

A password-protected admin panel provides:

* Session logs (user, video, question)
* Token usage estimates
* Number of retrieved chunks
* Final verdict (Trusted or Flagged)
* Downloadable logs in JSON format

---

# Limitations

* YouTube transcript extraction may fail in cloud environments due to IP blocking
* System depends on availability of subtitles in the video
* Large model inference latency depends on API performance
* Requires external API key for Groq

---

# Setup Instructions

1. Clone the repository

2. Install dependencies:

   pip install -r requirements.txt

3. Create a .env file and add:

   GROQ_API_KEY=your_api_key

4. Run the application:

   streamlit run app.py

---

# Future Improvements

* Robust transcript ingestion using alternative APIs
* Improved retrieval using hybrid search (BM25 + embeddings)
* Caching and persistence for large-scale usage
* Deployment optimization for cloud environments
* UI enhancements and multi-video support

---

# Author

Joe Sharwin C

---

* convert this into **top-tier GitHub README with badges + sections hierarchy**
* or align it exactly with **ATS + recruiter expectations for your resume**
