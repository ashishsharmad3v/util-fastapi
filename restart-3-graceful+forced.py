import os
import signal
import subprocess
import time
import schedule
import logging
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fastapi-restarter")

def find_fastapi_pid():
    """Find the PID of the FastAPI/Uvicorn process"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Look for uvicorn process running FastAPI
            if proc.info['cmdline'] and 'uvicorn' in ' '.join(proc.info['cmdline']):
                # You can make this more specific by checking for your app name
                # e.g., if 'main:app' in ' '.join(proc.info['cmdline']):
                logger.info(f"Found FastAPI/Uvicorn process: {proc.info['pid']}")
                return proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    logger.warning("No FastAPI/Uvicorn process found")
    return None

def restart_fastapi():
    """Restart the FastAPI application by sending SIGTERM"""
    pid = find_fastapi_pid()
    if pid:
        logger.info(f"Restarting FastAPI application with PID {pid}")
        try:
            # Send SIGTERM signal to gracefully terminate the process
            os.kill(pid, signal.SIGTERM)
            logger.info("SIGTERM signal sent successfully")
            
            # Wait for the process to terminate
            time.sleep(5)
            
            # Check if process is still running
            if psutil.pid_exists(pid):
                logger.warning(f"Process {pid} still running after SIGTERM, sending SIGKILL")
                os.kill(pid, signal.SIGKILL)
            
            # Start the FastAPI app again
            start_fastapi()
        except ProcessLookupError:
            logger.error(f"Process with PID {pid} not found")
        except Exception as e:
            logger.error(f"Error during restart: {str(e)}")
    else:
        logger.warning("No FastAPI process found to restart, starting a new instance")
        start_fastapi()

def start_fastapi():
    """Start the FastAPI application"""
    try:
        logger.info("Starting FastAPI application")
        # Adjust the command based on your specific app configuration
        # This example assumes you're running 'uvicorn main:app --host 0.0.0.0 --port 8000'
        subprocess.Popen(
            ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True  # Detach the process
        )
        logger.info("FastAPI application started")
    except Exception as e:
        logger.error(f"Error starting FastAPI application: {str(e)}")

def schedule_restarts(interval_hours=6):
    """Schedule periodic restarts at specified interval"""
    schedule.every(interval_hours).hours.do(restart_fastapi)
    logger.info(f"Scheduled FastAPI restarts every {interval_hours} hours")
    
    # Check if FastAPI is running, start if not
    if not find_fastapi_pid():
        start_fastapi()
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute for scheduled tasks

if __name__ == "__main__":
    # Schedule restarts every 6 hours
    schedule_restarts(6)
