from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from api.rest import router as api_router
from api.websocket import router as ws_router

app = FastAPI()

# Configure CORS with more specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Include routers
app.include_router(api_router, prefix="/api")
app.include_router(ws_router, prefix="/api")

@app.get("/")
async def root():
    return {"message": "Welcome to GoQuant5 API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 