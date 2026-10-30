import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"message":"Working!"}

def main():
    print("Hello from procindex-assignment!")
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

if __name__ == "__main__":
    main()