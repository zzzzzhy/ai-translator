import uvicorn
from app.main import app

if __name__ == "__main__":
    uvicorn.run(
        app="app.main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        workers=1
    )