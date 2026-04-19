from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
from src.graph_api.graph_store import GraphStore
from src.graph_api.retriever import GraphRetriever

app = FastAPI(title="Care-Beacon Graph RAG API")

# Initialize Graph Store
graph_store = None

@app.on_event("startup")
async def startup():
    global graph_store
    graph_store = GraphStore()
    graph_store.create_schema()

@app.on_event("shutdown")
async def shutdown():
    if graph_store:
        graph_store.close()

class QuestionRequest(BaseModel):
    question: str
    max_results: int = 5

class Source(BaseModel):
    text: str
    article_title: str
    section: str
    score: Optional[float] = None

class QuestionResponse(BaseModel):
    answer: str
    sources: List[Source]

@app.get("/health")
async def health():
    try:
        graph_store.verify_connection()
        return {"status": "healthy", "service": "graph-rag-api"}
    except Exception:
        raise HTTPException(status_code=503, detail="Service unavailable")

@app.post("/ask", response_model=QuestionResponse)
async def ask(request: QuestionRequest):
    try:
        retriever = GraphRetriever(graph_store)
        results = retriever.retrieve(request.question, limit=request.max_results)
        
        # Format sources
        sources = []
        context_text = ""
        for res in results:
            # Graph context is a list of neighbor texts
            context = "\n".join(res.get("context", []))
            text = f"{res.get('text')}\n\nContext:\n{context}"
            
            sources.append(Source(
                text=text,
                article_title=res.get("article_title", "Unknown"),
                section=res.get("section", "Unknown"),
                score=res.get("score")
            ))
            context_text += f"Source: {res.get('article_title')}\n{text}\n\n"
            
        # Generate Answer (Mock for now, or use LLM)
        # To do this properly, we should inject the AnswerGenerator or LLMClient
        # For this MVP, we will just return the retrieved context as the answer
        # or a simple message.
        
        answer = f"Based on the graph analysis of {len(results)} sources:\n\n{context_text[:500]}..."
        
        return {
            "answer": answer,
            "sources": sources
        }
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in /ask: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
