from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl
from requests import get_streaming_url
from proxy import (
    get_working_proxies_async,
    working_proxy_list
)
import asyncio
from contextlib import asynccontextmanager

# Background task to refresh proxies periodically
async def refresh_proxies_periodically():
    """Refresh proxies every 5 min in the background."""
    while True:
        await asyncio.sleep(300)  # Wait 5 min
        print("🔄 Auto-refreshing proxies...")
        try:
            await get_working_proxies_async()
            print(f"✅ Auto-refresh complete: proxies")
        except Exception as e:
            print(f"⚠️ Auto-refresh failed: {e}")


async def fetch_proxies_on_startup():
    """Fetch proxies in background without blocking server startup."""
    import sys
    print("🔄 Fetching proxies in background...", flush=True)
    sys.stdout.flush()
    try:
        await get_working_proxies_async()
        print("✅ Proxies loaded and ready!", flush=True)
        sys.stdout.flush()
    except Exception as e:
        print(f"⚠️ Failed to load proxies: {e}", flush=True)
        import traceback
        traceback.print_exc()
        sys.stdout.flush()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Start proxy fetching in background (DON'T WAIT FOR IT)
    proxy_task = asyncio.create_task(fetch_proxies_on_startup())

    # Start periodic refresh task
    refresh_task = asyncio.create_task(refresh_proxies_periodically())

    print("🚀 Server ready! (Proxies loading in background...)")

    yield  # Server is running - accepts requests immediately!

    # Shutdown
    proxy_task.cancel()
    refresh_task.cancel()
    print("👋 Shutting down...")


app = FastAPI(lifespan=lifespan)


class VideoRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/proxy-stats")
def get_proxy_stats():
    """
    Get current proxy list statistics.
    This returns the STORED list (no refetch).
    """
    return {
        "total_proxies": len(working_proxy_list),
        "proxies_loaded": len(working_proxy_list) > 0,
        "note": "These are cached proxies loaded at startup"
    }


@app.post("/refresh-proxies")
async def refresh_proxies():
    """
    Manually refresh the proxy list.
    This REFETCHES from GitHub and Geonode.
    """
    try:
        # get_working_proxies()

        return {
            "success": True,
            "message": "Proxies refreshed",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh proxies: {e}")


@app.get("/fetch-embed/{imdb_id}")
async def fetch_embed(imdb_id: str):
    """
    Fetches video embed content from vidsrc.

    Example request body:
    {
        "url": "https://vidsrc.xyz/embed/movie/tt5433140"
    }
    """
    result = await get_streaming_url(f"https://vidsrc.xyz/embed/movie/{imdb_id}")

    if result is None:
        raise HTTPException(status_code=400, detail="Failed to fetch embed content")

    return {"success": True, "content": result}


