import os
import signal
import logging
from datetime import datetime, timedelta, time as dtime
from pytz import timezone
import uvicorn
from fastapi import FastAPI, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fastapi-app")

# Create FastAPI app
app = FastAPI(title="Auto-Restarting FastAPI App")

# Global variables
last_restart_time = datetime.now(timezone('Europe/London'))
default_restart_time = dtime(23, 30)  # Default restart time at 11:30 PM BST
should_restart = True
restart_in_progress = False

scheduler = BackgroundScheduler(timezone='Europe/London')

def perform_restart():
    """Function to perform the restart"""
    global last_restart_time, restart_in_progress

    # Get the current process ID
    pid = os.getpid()
    
    # Log restart information
    logger.info(f"Performing scheduled restart of process {pid}")
    last_restart_time = datetime.now(timezone('Europe/London'))
    
    # Indicate that restart is in progress
    restart_in_progress = True
    
    # Send SIGTERM to the current process
    os.kill(pid, signal.SIGTERM)
    
    # Sleep for 30 seconds and then forcefully kill the process if it's still running
    time.sleep(30)
    os.kill(pid, signal.SIGKILL)

def schedule_restart():
    """Schedule the restart at the default time (11:30 PM BST)"""
    now = datetime.now(timezone('Europe/London'))
    next_restart = now.replace(hour=default_restart_time.hour, minute=default_restart_time.minute, second=0, microsecond=0)
    if now >= next_restart:
        next_restart += timedelta(days=1)
    scheduler.add_job(perform_restart, 'date', run_date=next_restart)
    logger.info(f"Next restart scheduled at {next_restart.isoformat()}")

@app.middleware("http")
async def check_restart_status(request: Request, call_next):
    """Middleware to handle requests during restart"""
    if restart_in_progress:
        return JSONResponse(
            status_code=503,
            content={"message": "Server unavailable due to scheduled activity. Please try again later."}
        )
    response = await call_next(request)
    return response

@app.on_event("startup")
async def startup_event():
    """Start the restart scheduler when the app starts"""
    global last_restart_time
    
    # Get the current process ID
    pid = os.getpid()
    logger.info(f"Application started with PID: {pid}")
    logger.info(f"Configured to restart at 11:30 PM BST daily")
    
    # Start the APScheduler
    scheduler.start()
    schedule_restart()
    logger.info("Automatic restart scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    """Handle clean shutdown"""
    global should_restart
    should_restart = False
    scheduler.shutdown()
    logger.info("Application shutting down")

@app.get("/")
async def root():
    """Basic root endpoint"""
    next_restart = scheduler.get_jobs()[0].next_run_time if scheduler.get_jobs() else None
    return {
        "message": "FastAPI server running with auto-restart feature",
        "process_id": os.getpid(),
        "last_restart": last_restart_time.isoformat(),
        "next_restart": next_restart.isoformat() if next_restart else None
    }

@app.get("/status")
async def status():
    """Report app status with restart information"""
    current_time = datetime.now(timezone('Europe/London'))
    next_restart = scheduler.get_jobs()[0].next_run_time if scheduler.get_jobs() else None
    
    return {
        "status": "running",
        "process_id": os.getpid(),
        "uptime_seconds": (current_time - last_restart_time).total_seconds(),
        "last_restart": last_restart_time.isoformat(),
        "next_restart": next_restart.isoformat() if next_restart else None,
        "restart_interval_hours": (next_restart - current_time).total_seconds() / 3600 if next_restart else None
    }

@app.post("/admin/restart")
async def manual_restart(background_tasks: BackgroundTasks):
    """Endpoint to manually trigger a restart"""
    global restart_in_progress
    pid = os.getpid()
    logger.info(f"Manual restart triggered for process {pid}")
    
    # Indicate that restart is in progress
    restart_in_progress = True
    
    # Schedule the restart with a small delay to allow the response to be sent
    def delayed_restart():
        time.sleep(1)  # 1-second delay
        os.kill(pid, signal.SIGTERM)
        time.sleep(30)
        os.kill(pid, signal.SIGKILL)
    
    background_tasks.add_task(delayed_restart)
    return {"message": "Application restarting...", "process_id": pid}

@app.post("/admin/configure")
async def configure_restart(interval_hours: int):
    """Configure the restart interval"""
    global restart_interval_hours
    
    if interval_hours < 1:
        return {"error": "Interval must be at least 1 hour"}
    
    # Update the configuration
    restart_interval_hours = interval_hours
    
    # Reschedule the restart job with new interval
    for job in scheduler.get_jobs():
        job.reschedule('interval', hours=restart_interval_hours)
    
    return {
        "message": f"Restart interval configured to {interval_hours} hours",
        "next_restart_in_seconds": restart_interval_hours * 3600
    }

if __name__ == "__main__":
    # When running this file directly, start the Uvicorn server
    logger.info(f"Starting FastAPI application with auto-restart configured to restart at 11:30 PM BST daily")
    uvicorn.run("restart-1:app", host="0.0.0.0", port=8000, reload=False)
