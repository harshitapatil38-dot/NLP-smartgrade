# PCCOE Intelligent College Information Assistant

## Project Purpose
This project is an NLP-based college information chatbot designed to assist students and staff with inquiries about PCCOE. The long-term goal is to deploy this assistant on the official college website.

## Current Technology Stack
- **Backend:** Python, FastAPI
- **Frontend:** React, Vite

## Current Project Structure
The project is divided into the following main directories:
- `backend/`: FastAPI application containing API endpoints, database setup, and future NLP/RAG logic.
- `frontend/`: React/Vite application for the user interface.
- `chatbot-widget/`: Directory for the future embeddable website widget.
- `knowledge_base/`: Storage for documents and sample data for the assistant.
- `docs/`: Architecture, API, and deployment documentation.

## Current Development Stage
This is **Step 1: Project Foundation**. The basic project structure for both the frontend and backend has been created.

### Planned Future Modules
- PostgreSQL and pgvector for database and embeddings
- NLP and semantic search integration
- Retrieval-Augmented Generation (RAG)
- Document processing and ingestion
- Authentication and Admin Dashboard
- Website-embeddable chatbot widget

## Setup Instructions

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://localhost:8000` and the health check at `http://localhost:8000/health`.

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Run the development server:
   ```bash
   npm run dev
   ```
   The frontend will be available at `http://localhost:5173`.
