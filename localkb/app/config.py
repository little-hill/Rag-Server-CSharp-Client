import psutil
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import os

class UbuntuConfig:
    # FILE PATH
    ROOT_DIR = "/home/user/localkb/"
    DATA_DIR = Path(ROOT_DIR) / "data"
    KNOWLEDGE_DIR = DATA_DIR / "knowledge"
    VECTOR_DIR = DATA_DIR / "vectors"
    VECTOR_STORE_META = "metadata.json"
    FAISS_FILE = "index.faiss"
    FAISS_NPROBE = 5

    # API KEY PATH
    API_KEY_PATH = Path(ROOT_DIR) / "key/api.key"
    
    # LOGGING CONFIGURATION
    SERVICE_USER = "user"
    LOG_DIR = Path(ROOT_DIR) / "logs"
    LOG_FILE = LOG_DIR / "application.log"
    LOG_LEVEL = logging.INFO
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # MODEL CONFIGURATION
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    # LLM_MODEL = "deepseek-llm:7b"
    LLM_MODEL = "llama3.2:latest"
    CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    
    # PERFORMANCE TUNING
    CHUNK_SIZE = 1000  # GOOD FOR BIG LINUX BLOCK
    MAX_MEMORY = psutil.virtual_memory().total * 0.8  # 80% OF MEMORY
    CHUNK_OVERLAP = 200    # CHARACTER NUMBER OVERLAPPED BETWEEN BLOCKS

    # BLOCK OPTIMIZATION PARAMETERS
    MIN_CHUNK_LENGTH = 200  # MERGE IF SIZE IS LESS THAN THE THRESHOLD
    ENABLE_CHUNK_MERGE = True

    # LLM CONFIGURATION
    max_tokens = 512
    temperature = 0.1

    # OLLAMA CONFIGURATION
    ollama_base_url = "http://localhost:11434"
    ollama_timeout = 1800


    @classmethod
    def init_logging(cls):
        """INITIALIZE LOG CONFIGURATION"""
        cls.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # CONFIGURE ROOT LOGGER 
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.LOG_LEVEL)

        # FILE HANDLER
        file_handler = RotatingFileHandler(
            filename=str(cls.LOG_FILE),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8',
            delay=True
        )
        file_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))

        # CLEAN EXISTED LOGGER TO AVOID REDUNDENCY
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        root_logger.addHandler(file_handler)

        # OPTIONAL: CONSOLE OUTPUT
        if os.getenv("DEBUG"):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(logging.Formatter(cls.LOG_FORMAT))
            root_logger.addHandler(console_handler)

        return root_logger

    @property
    def logger(self):
        import logging
        logger = logging.getLogger(__name__)
        handler = logging.handlers.RotatingFileHandler(
            f"{self.LOG_DIR}/debug.log",
            maxBytes=10*1024*1024,
            backupCount=5
        )
        logger.addHandler(handler)
        return logger

