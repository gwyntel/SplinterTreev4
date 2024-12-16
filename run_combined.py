import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# Ensure logs directory exists
logs_dir = os.path.join('/app', 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Configure logging with error handling
try:
    # Create a rotating file handler
    log_file = os.path.join(logs_dir, 'combined.log')
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            file_handler,
            logging.StreamHandler(sys.stdout)  # Also log to console
        ]
    )

    logging.info("Logging initialized successfully")

except Exception as e:
    print(f"Error initializing logging: {e}")
    logging.basicConfig(level=logging.INFO)  # Fallback to basic logging

# Rest of your existing run_combined.py script continues here
# ... (your original script content)
