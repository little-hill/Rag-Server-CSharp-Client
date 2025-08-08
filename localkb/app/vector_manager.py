import os
import subprocess
from pathlib import Path
import torch
import json
import hashlib
import shutil
import faiss
from langchain_ollama import OllamaEmbeddings
from langchain_ollama import OllamaLLM
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import UnstructuredWordDocumentLoader
from langchain.document_loaders import (
    DirectoryLoader,
    UnstructuredFileLoader,
    UnstructuredPDFLoader#,
    #UnstructuredWordDocumentLoader
)
from app.custom_json import JSONLoader
import logging

if not logging.getLogger().hasHandlers():
    from app.config import UbuntuConfig
    UbuntuConfig.init_logging()
logger = logging.getLogger(__name__)  

class VectorManager:
    def __init__(self, config, processor):
        self.config = config
        self.processor = processor
        self.knowledge_dir = Path(config.KNOWLEDGE_DIR)
        self.vector_dir = Path(config.VECTOR_DIR)
        self.vector_store: Optional[FAISS] = None
        self.meta_file = os.path.join(self.vector_dir, self.config.VECTOR_STORE_META)
        self.embeddings = OllamaEmbeddings(model=self.config.LLM_MODEL)
        self.processor.update_embeddings(self.embeddings)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=self.config.CHUNK_SIZE, chunk_overlap=self.config.CHUNK_OVERLAP)
        self.LOADER_MAPPING = {
            ".txt": (UnstructuredFileLoader, {"encoding": "utf-8"}),
            ".pdf": (UnstructuredPDFLoader, {}),
            ".docx": (UnstructuredWordDocumentLoader, {"mode":"single"}),
            ".json": (JSONLoader, {})  # JSON LOADER
        }
        os.makedirs(self.knowledge_dir, exist_ok=True)
        os.makedirs(self.vector_dir, exist_ok=True)
        
    def _doc_hash(self, file_path):
        """CALCULATE DOCUMENT HASH"""
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _load_metadata(self):
        """LOAD MEDA"""
        if os.path.exists(self.meta_file):
            with open(self.meta_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_metadata(self, metadata):
        """SAVE META"""
        with open(self.meta_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def build_vector_store(self):
        from langchain_community.document_loaders import DirectoryLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        
        logger.info("Building full vector store...")
        loader = DirectoryLoader(self.knowledge_dir, show_progress=True)
        docs = loader.load()
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        splits = text_splitter.split_documents(docs)
        
        vector_store = FAISS.from_documents(splits, self.embeddings, ids=[f"doc_{i}" for i in range(len(splits))])
        vector_store.save_local(self.vector_dir)
        
        # GENERATE META
        metadata = {}
        for doc in docs:
            rel_path = os.path.relpath(doc.metadata['source'], self.knowledge_dir)
            metadata[rel_path] = self._doc_hash(doc.metadata['source'])
        self._save_metadata(metadata)
        
        logger.info(f"Vector store built with {len(splits)} chunks")
        return vector_store
    
    def incremental_update(self):
        """INCREMENTAL UPDATES TO VECTOR STORE"""
        current_meta = self._load_metadata()
        new_meta = {}
        changes = {"added": [], "updated": [], "deleted": []}
        
        # DETECT CHANGE
        for root, _, files in os.walk(self.knowledge_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.knowledge_dir)
                
                current_hash = current_meta.get(rel_path)
                new_hash = self._doc_hash(file_path)
                new_meta[rel_path] = new_hash
                
                if current_hash is None:
                    changes["added"].append(rel_path)
                elif current_hash != new_hash:
                    changes["updated"].append(rel_path)
        
        # DETECT DELETION
        for rel_path in current_meta:
            if rel_path not in new_meta:
                changes["deleted"].append(rel_path)
        
        if not any(changes.values()):
            logger.info("No changes detected")
            return True
        
        logger.info(f"Changes detected: {changes}")
        return self._apply_changes(changes, current_meta)
    
    def _apply_changes(self, changes, old_meta):
        """APPLY CHANGES TO VECTOR STORE"""
        temp_dir = os.path.join(self.config.DATA_DIR, "temp_update")
        backup_dir = os.path.join(self.config.DATA_DIR, "backup")
        try:
            # HANDLE DELETION
            if changes["deleted"] or changes["updated"]:
                # FAISS DOES NOT SUPPORT DELETION AND NEED REBUILD VECTOR STORE
                logger.info("Deletes require full rebuild")
                return False

            # CREATE TEMP DIRECTORY
            os.makedirs(temp_dir, exist_ok=True)
            
            # DUPLICATE EXISTING INDICE
            for f in os.listdir(self.vector_dir):
                src = os.path.join(self.vector_dir, f)
                dst = os.path.join(temp_dir, f)
                if os.path.isfile(src):
                    shutil.copy(src, dst)
            
            # LOAD EXISTING VECTOR STORE
            vector_store = FAISS.load_local(
                self.vector_dir, 
                self.embeddings, 
                allow_dangerous_deserialization=True
            )
            
            new_docs = []
            for change_type, files in changes.items():
                if change_type == "deleted" or change_type == "updated":
                    continue
                    
                for rel_path in files:
                    file_path = os.path.join(self.knowledge_dir, rel_path)
                    ext = os.path.splitext(file_path)[1].lower()
                    
                    loader_class = self.LOADER_MAPPING.get(ext, UnstructuredFileLoader)
                    loader = loader_class(file_path)
                    docs = loader.load()
                    new_docs.extend(docs)
            
            if new_docs:
                splits = self.text_splitter.split_documents(new_docs)
                vector_store.add_documents(splits)
                logger.info(f"Added {len(splits)} new chunks")
            
            # SAVE TO TEMP DIRECTORY
            vector_store.save_local(temp_dir)
            
            # EXCHANGE DIRECTORIES
            shutil.rmtree(backup_dir, ignore_errors=True)
            shutil.move(self.vector_dir, backup_dir)
            shutil.move(temp_dir, self.vector_dir)
            
            # UPDATE META
            new_meta = self._load_metadata()
            for rel_path in changes["added"] + changes["updated"]:
                file_path = os.path.join(self.knowledge_dir, rel_path)
                new_meta[rel_path] = self._doc_hash(file_path)
            for rel_path in changes["deleted"]:
                new_meta.pop(rel_path, None)
            self._save_metadata(new_meta)
            
            # CLEARN UP
            shutil.rmtree(temp_dir, ignore_errors=True)
            shutil.rmtree(backup_dir, ignore_errors=True)
            
            logger.info("Vector store updated successfully")
            self.vector_store = vector_store
            self.processor.update_vector_store(vector_store)
            return True
        except Exception as e:
            logger.info(f"Update failed: {str(e)}")
            # RESTORE BACKUP
            if os.path.exists(backup_dir):
                shutil.move(backup_dir, self.vector_dir)
            return False
    
    # THE FOLLOWING FUNCTIONS ARE MIGRATED FROM app/knowledge_manager.py ====================================
    def vector_store_exists(self) -> bool:
        return (self.vector_dir / self.config.FAISS_FILE).exists()

    def process_knowledge_base(self):
        try:
            docs = self._load_documents()
            documents = self.text_splitter.split_documents(docs)
            self.vector_store = FAISS.from_documents(documents, self.embeddings, ids=[f"doc_{i}" for i in range(len(documents))])
            subprocess.run([
                "chown", "-R", 
                f"{self.config.SERVICE_USER}:{self.config.SERVICE_USER}",
                self.config.VECTOR_DIR
            ])
            self.vector_store.save_local(str(self.vector_dir))
            self.processor.update_vector_store(self.vector_store)
            # CREATE META
            metadata = {}
            for doc in docs:
                rel_path = os.path.relpath(doc.metadata['source'], self.knowledge_dir)
                metadata[rel_path] = self._doc_hash(doc.metadata['source'])
            self._save_metadata(metadata)
            
            logger.info(f"Vector store built with {len(documents)} chunks")
            return self.vector_store
        except Exception as e:
            self._generate_coredump()
            raise
    
    def _load_documents(self):
        # CREATE LOAD DYNAMICALLY
        def dispatch_loader(file_path: str):
            ext = Path(file_path).suffix.lower()
            logger.info(F"file ({file_path}) with extension {ext}")
            if ext in self.LOADER_MAPPING:
                loader_class, loader_args = self.LOADER_MAPPING[ext]
                return loader_class(file_path, **loader_args)
            return None  # INGORE UNSUPPORTED FORMAT

        # INITIALIZE DirectoryLoader (new API)
        try:
            loader = DirectoryLoader(
                    self.config.KNOWLEDGE_DIR,
                    loader_cls=dispatch_loader,
                    use_multithreading=True,
                    show_progress=True,
                    silent_errors=True  # SKIP ERROR FILE SLIENTLY
                    )
            docs = loader.load()            
            logger.info(f"successfully load {len(docs)} documents")
            if len(docs) == 0:
                logger.error("load returns empty document list, possible reasons are:")
                logger.error("1. file format is not supported")
                logger.error("2. file has empty content")
                logger.error("3. file encoding error文件编码错误")
            return docs if docs else []
        except Exception as e:
            logger.error(f"document load failure:{str(e)}")
            return []

    def _generate_coredump(self):
        """CREATE CORE DUMP FILE (Linux ONLY)"""
        dump_dir = Path("/var/crash/knowledge_service")
        try:
            # CHECK DIRECTORY EXISTENCE
            dump_dir.mkdir(parents=True, exist_ok=True)

            # GET PROCESS ID
            pid = os.getpid()

            # USE gcore TO CREATE CORE DUMP
            subprocess.run(
                ["gcore", "-o", str(dump_dir/"core"), str(pid)],
                check=True,
                stderr=subprocess.PIPE
            )

            # CONFIGRUE FILE ACCESS
            subprocess.run(["chmod", "644", str(dump_dir/"core.*")])

            logger.error(f"core dump is created at {dump_dir}")
        except Exception as e:
            logger.critical(f"core dump creation failure: {str(e)}")

    def load_vector_store(self):
        try:
            self.vector_store = FAISS.load_local(
                str(self.vector_dir),
                self.embeddings,
                allow_dangerous_deserialization=True  # OLD FORMAT IS ALLOWED
            )
            self.processor.update_vector_store(self.vector_store)
        except Exception as e:
            raise