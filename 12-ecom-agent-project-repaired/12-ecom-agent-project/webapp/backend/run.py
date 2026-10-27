"""Run the backend locally: uvicorn on http://localhost:8000.

    cd webapp/backend
    python run.py

webapp/backend/.env is read by app/settings.py when the app is imported — so
`uvicorn app.main:app` and a PyCharm run configuration read it too. Nothing
needs loading here.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
