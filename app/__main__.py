"""Levanta la app solo en la interfaz local (RF-24):  python -m app"""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PUERTO", "8000")), reload=False)
