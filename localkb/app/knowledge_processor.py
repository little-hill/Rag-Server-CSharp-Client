import os
from pathlib import Path
import torch 
from typing import List, Optional
from langchain.vectorstores import FAISS
from langchain_ollama import OllamaLLM
from langchain_huggingface import HuggingFaceEmbeddings  
from typing import List
from langchain.schema import Document
from langchain.chains import RetrievalQA
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from langchain.prompts import PromptTemplate
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import numpy as np
import logging

if not logging.getLogger().hasHandlers():
    from app.config import UbuntuConfig
    UbuntuConfig.init_logging()
 
logger = logging.getLogger(__name__)   

class KnowledgeProcessor:
    def __init__(self, config):
        self.config = config
        self.vector_store: Optional[FAISS] = None
        self.embeddings = None
        self.qa_chain = None

    def retrieve_context_rerank(self, question: str, top_k: int = 5) -> str:
        logger.info(f"calling context rerank function with similarity search setting [{top_k}]")
        """RETRIEVE CONTEXT FROM VECTOR STORE"""
        if self.vector_store is None:
            logger.info("vector store is not loaded, returing empty string")
            return ""  # NEED TO MAKRE SURE VECTOR STORE IS LOADED
        
        # SIMILARITY SEARCH
        docs = self.vector_store.similarity_search(question, k=top_k)
        if len(docs) < 1:
            return ""
        logger.info(f"info: find [{len(docs)}] initial docs and rerank...")
        # RERANKING
        tokenizer = AutoTokenizer.from_pretrained(self.config.CROSS_ENCODER_MODEL)
        model_token = AutoModelForSequenceClassification.from_pretrained(self.config.CROSS_ENCODER_MODEL)
        pairs = [(question, doc.page_content) for doc in docs]
        features = tokenizer(pairs, padding=True, truncation=True, return_tensors="pt", max_length=512)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu") # utilize GPU
        model_token = model_token.to(device)
        features = {k: v.to(device) for k, v in features.items()}
        with torch.no_grad():
            scores = model_token(**features).logits
            rerank_scores = torch.sigmoid(scores).cpu().numpy().flatten()
        refined_docs = [(docs[i], rerank_scores[i]) for i in range(len(docs))]
        refined_docs.sort(key=lambda x: x[1], reverse=True)
        top_N = 2
        refined_docs = [doc for doc, _ in refined_docs[:top_N]]
        logger.info(f"info: find [{len(refined_docs)}] filterred docs")
        context = "\n\n".join([doc.page_content for doc in refined_docs])    
        return context

    def update_vector_store(self, vector_store):
        self.vector_store = vector_store
        logger.info(f"vector store updated with {len(vector_store.index.reconstruct_n(0, vector_store.index.ntotal))} vectors.")
        
    def update_embeddings(self, embeddings):
        self.embeddings = embeddings
        logger.info(f"embeddings is updated")

    # NON-STREAMING RETRIEVAL
    def retrieveQA(self, question: str):
        try:
            if self.vector_store is None:
                logger.info("vector store is not loaded, returing empty string")
                return ""  # NEED TO MAKRE SURE VECTOR STORE IS LOADED

            if not self.qa_chain:
                logger.info("initilaize QA chain...")
                self._init_qa_chain()
            
            results = self.qa_chain.invoke({"query" : question})
            response = results['result']
            logger.info(f"quesion ({question}) has response ({response})")
            return response
        except Exception as e:
            return f"request fails - {str(e)}"
    
    def _init_qa_chain(self):
        llm = OllamaLLM(model=self.config.LLM_MODEL)
        retriever = self.vector_store.as_retriever()
        qa_prompt = PromptTemplate(
            input_variables=["context","question"],
            template="""
            You are a helpful assistant. Use the context provided below to answer the user's question.
            
            Your answer must:
            - Identify and describe only relevant scenarios related to the issue described the question.
            - Provide a clear workaround or resolution for each scenario.
            
            Only use the information from the context. If the answer cannot be found in the context, respond with "I don't know."
            
            Context:
            {context}
            
            Question: {question}
            Answer: 
            """
        )
        self.qa_chain = RetrievalQA.from_chain_type(llm=llm, retriever=retriever, chain_type="stuff", chain_type_kwargs={"prompt": qa_prompt}, return_source_documents=False)