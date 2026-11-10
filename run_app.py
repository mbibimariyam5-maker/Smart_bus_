"""
SmartBus Application Launcher
Starts the FastAPI application on http://localhost:8000
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting SmartBus - Karnataka Intelligent Bus Transport Analytics")
    print("Dashboard available at: http://localhost:8000")
    print("API Documentation at:  http://localhost:8000/docs")
    print("=" * 60)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)

