import os
import logging
from fastapi import FastAPI, Depends, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.security import APIKeyHeader
from app.config import UbuntuConfig
config = UbuntuConfig()
config.init_logging()
from app.knowledge_processor import KnowledgeProcessor
from app.ollama_client import OllamaClient
from app.prompt_builder import PrompBuilder
from app.vector_manager import VectorManager
from app.file_monitor import FileMonitor
from typing import Annotated
from pydantic import BaseModel
import logging
import asyncio
import traceback
import threading


class QuestionRequest(BaseModel):
    question: str

# DEFINE API KEY HEADER
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

# INITIALIZE THE WEB SERVICE
app = FastAPI(title="Knowledge Service")

# INITIALIZE KEY COMPONENTS
prompt_builder = PrompBuilder()
processor = KnowledgeProcessor(config)
vecManager = VectorManager(config, processor)
monitor = None
shutdown_event = threading.Event()

# INITIALIZE Ollama CLIENT
ollama = OllamaClient(
    base_url=config.ollama_base_url,
    model=config.LLM_MODEL,
    timeout=config.ollama_timeout,
    max_tokens=config.max_tokens,
    temperature=config.temperature
)
logger = logging.getLogger(__name__)

async def validate_api_key(api_key: str = Depends(api_key_header)):
    from .utils.security import secure_compare, get_stored_key
    if not api_key:
        raise HTTPException(status_code=403, detail="Authentication is not provided")
    if not secure_compare(api_key, get_stored_key()):
        raise HTTPException(status_code=403, detail="Authentication fails")
    return api_key

@app.on_event("startup")
async def startup_event():
    """STARTUP INITIALIZATION"""
    global monitor
    logger.info("========== Application Startup ==========")
    if not vecManager.vector_store_exists():
        logger.info("vector store does not exists and creating...")
        vecManager.process_knowledge_base()
    else:
        logger.info("vector store exists, loading...")
        vecManager.load_vector_store()
    ollama.health_check()

    # FILE MONITORING CALLBACK FUNCTION
    def update_callback():
        logger.info("Triggering vector store update...")
        if not vecManager.incremental_update():
            logger.info("Falling back to full rebuild")
            vecManager.process_knowledge_base()
    
    # START FILE MONITORING
    monitor = FileMonitor(
        path=config.KNOWLEDGE_DIR,
        callback=update_callback,
        cooldown=60  # 60 SECONDS TO AVOID FREQUENT CHANGES
    )
    monitor.start()

@app.post("/api/ask")
async def ask_question(
        request: QuestionRequest,
        api_key: Annotated[str, Depends(validate_api_key)]
        ):
    question = request.question
    logger.info(f"received question: [{question}]")
    try:
        response = processor.retrieveQA(question)
        return {"answer": response}
    except Exception as e:
        logger.error(f"request fails: {str(e)}")
        return {"answer", f"Service is not available ({str(e)}), Please try again later"}


@app.post("/api/ask_stream")
async def ask_question_stream(
    request: QuestionRequest,
    api_key: Annotated[str, Depends(validate_api_key)]
    ):
    """STREAM RESPONSE POINT"""
    async def generate_stream():
        try:
            # EXTRACT QUESTION
            question = request.question

            # CHECK IF QUESTION IS A QUERY
            yield f"info: [Analyzing queires \"{question}\"]\n\n"
            response = ollama.generate(
            prompt=prompt_builder.build_prompt_retrieval(question),
            max_tokens=config.max_tokens,
            temperature=config.temperature
            )
            if response.strip().lower() != "yes":
                yield f"data: Hello! How can I help you today?"
                return
            
            # RESTRUCTE THE QUERY
            refined_query = ollama.generate(
            prompt=prompt_builder.build_prompt_stepback(question),
            max_tokens=config.max_tokens,
            temperature=config.temperature
            )
            yield f"info: refined queries are [{refined_query}]\n\n"

            # RETRIEVE CONTEXT (NOT STREAMING)
            yield f"info: [searching context...]\n\n"
            context = processor.retrieve_context_rerank(question=refined_query) # FURTHER FILTERING - RERANK
            if not context:
                yield "info: cannot find related document"
                return
            prompt = prompt_builder.build_prompt_stream(refined_query, context)
            
            # GENERATE STREAM RESPONSE
            yield f"info: [generating response...]\n\n"
            async for chunk in ollama.generate_stream(prompt):
                yield f"data: {chunk}\n\n"
                await asyncio.sleep(0.01)  # CONTROL STREAM PACE
            
            # END OF STREAM
            yield "info: [DONE]\n\n"
        except Exception as e:
            logger.error("stream call error", exc_info=True)
            yield f"error: [ERROR: {str(e)}]\n\n"

    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"  # DO NOT USE Nginx BUFFER
        }
    )


@app.on_event("shutdown")
async def shutdown_event():
    """CLEANUP ON SHUTDOWN"""
    global monitor
    logger.info("========== Application Shutdown ==========")
    if monitor:
        monitor.stop()
        monitor = None
    shutdown_event.set()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
