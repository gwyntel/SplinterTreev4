import os
import sys
import time
import signal
import subprocess
import threading
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import requests
from requests.exceptions import RequestException

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

# Create logger for this module
logger = logging.getLogger(__name__)

def check_web_server(url="http://localhost:5000", timeout=1):
    """Check if web server is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200 or response.status_code == 401  # 401 is ok as it means auth is working
    except RequestException:
        return False

def stream_output(process, name):
    """Stream process output to logger"""
    for line in iter(process.stdout.readline, ''):
        logger.info(f"{name} output: {line.strip()}")
    for line in iter(process.stderr.readline, ''):
        logger.error(f"{name} error: {line.strip()}")

def run_processes():
    """Run both web server and discord bot processes with proper handling."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Set unbuffered output
    os.environ['PYTHONUNBUFFERED'] = '1'
    
    # Initialize database if needed
    logger.info("Initializing database...")
    try:
        subprocess.run([sys.executable, 'initialize_interaction_logs_db.py'], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to initialize database: {e}")
        return
    
    processes = []
    output_threads = []
    try:
        # Start web server first
        logger.info("Starting web server...")
        web_process = subprocess.Popen(
            [sys.executable, 'web.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        processes.append(('web', web_process))
        
        # Start output streaming thread for web server
        web_thread = threading.Thread(target=stream_output, args=(web_process, 'web'))
        web_thread.daemon = True
        web_thread.start()
        output_threads.append(web_thread)
        
        # Wait for web server to be ready
        logger.info("Waiting for web server to be ready...")
        retries = 30
        while retries > 0:
            if check_web_server():
                logger.info("Web server is ready")
                break
            time.sleep(1)
            retries -= 1
            if web_process.poll() is not None:
                stdout, stderr = web_process.communicate()
                logger.error(f"Web server failed to start\nStdout: {stdout}\nStderr: {stderr}")
                return
        else:
            logger.error("Web server failed to respond in time")
            return
        
        # Start Discord bot
        logger.info("Starting Discord bot...")
        bot_process = subprocess.Popen(
            [sys.executable, 'bot.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1  # Line buffered
        )
        processes.append(('bot', bot_process))
        
        # Start output streaming thread for bot
        bot_thread = threading.Thread(target=stream_output, args=(bot_process, 'bot'))
        bot_thread.daemon = True
        bot_thread.start()
        output_threads.append(bot_thread)
        
        # Monitor processes
        while True:
            for name, process in processes:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    logger.error(f"{name} process died\nStdout: {stdout}\nStderr: {stderr}")
                    raise Exception(f"{name} process died unexpectedly")
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("\nReceived shutdown signal...")
    except Exception as e:
        logger.error(f"Error occurred: {e}")
    finally:
        # Graceful shutdown
        logger.info("Shutting down processes...")
        for name, process in processes:
            if process.poll() is None:  # If process is still running
                logger.info(f"Terminating {name} process...")
                if sys.platform == 'win32':
                    process.terminate()  # Use SIGTERM on Windows
                else:
                    process.send_signal(signal.SIGTERM)  # Use SIGTERM on Unix
                try:
                    process.wait(timeout=5)  # Wait up to 5 seconds for graceful shutdown
                except subprocess.TimeoutExpired:
                    logger.warning(f"{name} process didn't terminate gracefully, forcing...")
                    process.kill()  # Force kill if process doesn't terminate
                    process.wait()
        logger.info("All processes terminated.")

if __name__ == '__main__':
    run_processes()