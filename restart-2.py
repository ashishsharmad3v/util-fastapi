import os
import signal
import threading
import time
import logging
from datetime import datetime
import uvicorn
from fastapi import FastAPI, BackgroundTasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fastapi-app")

# Create FastAPI app
app = FastAPI(title="Auto-Restarting FastAPI App")

# Global variable to store the last restart time
last_restart_time = datetime.now()
restart_interval_hours = 6  # Default restart interval
restart_thread = None
should_restart = True

def scheduled_restart_task():
    """Background thread that handles the scheduled restarts"""
    global last_restart_time, should_restart
    
    while should_restart:
        # Sleep for the configured interval
        time.sleep(restart_interval_hours * 3600)  # Convert hours to seconds
        
        # Get the current process ID
        pid = os.getpid()
        
        # Log restart information
        logger.info(f"Performing scheduled restart of process {pid}")
        last_restart_time = datetime.now()
        
        # Send SIGTERM to the current process
        os.kill(pid, signal.SIGTERM)
        break  # Exit the thread as we're restarting

@app.on_event("startup")
async def startup_event():
    """Start the restart scheduler when the app starts"""
    global restart_thread
    
    # Get the current process ID
    pid = os.getpid()
    logger.info(f"Application started with PID: {pid}")
    logger.info(f"Configured to restart every {restart_interval_hours} hours")
    
    # Start the background restart thread
    restart_thread = threading.Thread(target=scheduled_restart_task)
    restart_thread.daemon = True  # Make thread exit when main thread exits
    restart_thread.start()
    logger.info("Automatic restart scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    """Handle clean shutdown"""
    global should_restart
    should_restart = False
    logger.info("Application shutting down")

@app.get("/")
async def root():
    """Basic root endpoint"""
    return {
        "message": "FastAPI server running with auto-restart feature",
        "process_id": os.getpid(),
        "last_restart": last_restart_time.isoformat(),
        "next_restart": (last_restart_time.timestamp() + restart_interval_hours * 3600)
    }

@app.get("/status")
async def status():
    """Report app status with restart information"""
    current_time = datetime.now()
    next_restart = last_restart_time.timestamp() + (restart_interval_hours * 3600)
    seconds_until_restart = max(0, next_restart - current_time.timestamp())
    
    return {
        "status": "running",
        "process_id": os.getpid(),
        "uptime_seconds": (current_time - last_restart_time).total_seconds(),
        "last_restart": last_restart_time.isoformat(),
        "next_restart_in_seconds": seconds_until_restart,
        "restart_interval_hours": restart_interval_hours
    }

@app.post("/admin/restart")
async def manual_restart(background_tasks: BackgroundTasks):
    """Endpoint to manually trigger a restart"""
    pid = os.getpid()
    logger.info(f"Manual restart triggered for process {pid}")
    
    # Schedule the restart with a small delay to allow the response to be sent
    def delayed_restart():
        time.sleep(1)  # 1-second delay
        os.kill(pid, signal.SIGTERM)
    
    background_tasks.add_task(delayed_restart)
    return {"message": "Application restarting...", "process_id": pid}

@app.post("/admin/configure")
async def configure_restart(interval_hours: int):
    """Configure the restart interval"""
    global restart_interval_hours, restart_thread, should_restart
    
    if interval_hours < 1:
        return {"error": "Interval must be at least 1 hour"}
    
    # Update the configuration
    restart_interval_hours = interval_hours
    
    # Restart the scheduler thread with new interval
    should_restart = False
    if restart_thread and restart_thread.is_alive():
        restart_thread.join(timeout=1.0)
    
    should_restart = True
    restart_thread = threading.Thread(target=scheduled_restart_task)
    restart_thread.daemon = True
    restart_thread.start()
    
    return {
        "message": f"Restart interval configured to {interval_hours} hours",
        "next_restart_in_seconds": restart_interval_hours * 3600
    }

if __name__ == "__main__":
    # When running this file directly, start the Uvicorn server
    logger.info(f"Starting FastAPI application with auto-restart every {restart_interval_hours} hours")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
