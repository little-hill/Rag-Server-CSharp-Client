import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
if not logging.getLogger().hasHandlers():
    from app.config import UbuntuConfig
    UbuntuConfig.init_logging()
logger = logging.getLogger(__name__)  

class KnowledgeHandler(FileSystemEventHandler):
    def __init__(self, callback, cooldown=30):
        self.callback = callback
        self.cooldown = cooldown
        self.last_trigger = 0
    
    def on_any_event(self, event):
        if event.is_directory:
            return
            
        # IGNOE TEMPORAY FILES
        if event.src_path.endswith('~') or event.src_path.startswith('.'):
            return
            
        current_time = time.time()
        if current_time - self.last_trigger > self.cooldown:
            self.last_trigger = current_time
            logger.info(f"\nFile change detected: {event.event_type} {event.src_path}")
            self.callback()

class FileMonitor:
    def __init__(self, path, callback, cooldown=30):
        self.path = path
        self.event_handler = KnowledgeHandler(callback, cooldown)
        self.observer = Observer()
        self.is_running = False
    
    def start(self):
        if not self.is_running:
            self.observer.schedule(
            self.event_handler, 
            self.path, 
            recursive=True        
            )
            self.observer.start()
            self.is_running = True
            logger.info(f"Monitoring started on {self.path}")
    
    def stop(self):
        if self.is_running:
            self.observer.stop()
            self.observer.join(timeout=5.0)
            self.is_running = False
            logger.info(f"Monitoring stopped on {self.path}")

    def __enter__(self):
        logger.info("Entering FileMonitor context")
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logger.info("Exiting FileMonitor context")
        self.stop()
    
    def __del__(self):
        logger.info("FileMonitor is being deleted")
        self.stop()  # MAKE SURE TO STOP DURING DECONSTRUCTION