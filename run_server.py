import uvicorn

if __name__ == "__main__":
    print("="*70)
    print(" SentiCall — 'The Third Voice: AI Web Prototype Against Voice Fraud'")
    print(" Starting local server on http://127.0.0.1:8000")
    print("="*70)
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)
