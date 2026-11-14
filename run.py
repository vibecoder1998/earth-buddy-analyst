"""Local server: python run.py -> http://127.0.0.1:8000 (EB_HOST / EB_PORT override)."""
import os

import uvicorn

if __name__ == "__main__":
    from earthbuddy import net

    net.refuse_offline_on_vercel()
    uvicorn.run("earthbuddy.server:app", host=os.environ.get("EB_HOST", "127.0.0.1"),
                port=int(os.environ.get("EB_PORT", "8000")), reload=True)
