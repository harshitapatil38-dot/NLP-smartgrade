from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PCCOE Intelligent College Information Assistant API",
    description="Backend API for the PCCOE College Information Chatbot",
    version="1.0.0"
)

# CORS configuration for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to the PCCOE College AI Assistant API"}

@app.get("/health")
def health_check():
    return {"status": "ok"}
