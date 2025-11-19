import uvicorn
from app.main import app
from app.database import init_db
if __name__ == "__main__":
    uvicorn.run(
        app="app.main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        workers=1,
        env_file='.env.local'
    )