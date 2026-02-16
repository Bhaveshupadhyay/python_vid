import asyncio
from curl_cffi import requests

# List of proxies to test
# Format: protocol://IP:PORT
socks4_proxy_list = []

socks5_proxy_list = []
http_proxy_list = []
working_proxy_list = []

# URL to test IP (shows your IP)
TEST_URL = "https://api.ipify.org"

# Timeout for each request in seconds
TIMEOUT = 10

def get_github_proxies(protocol: str):
    url = f"https://raw.githubusercontent.com/TheSpeedX/PROXY-List/refs/heads/master/{protocol}.txt"
    response = requests.get(url)
    response.raise_for_status()
    lines = response.text.splitlines()
    proxies = [f"{protocol}://{line.strip()}" for line in lines if line.strip()]
    if protocol == "socks4":
        socks4_proxy_list.extend(proxies)
    elif protocol == "socks5":
        socks5_proxy_list.extend(proxies)
    elif protocol == "http":
        http_proxy_list.extend(proxies)

def get_geonode_proxies():
    url = "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    response = requests.get(url)
    response.raise_for_status()
    for data in response.json()["data"]:
        if "socks4" in data["protocols"]:
            socks4_proxy_list.append(f"socks4://{data['ip']}:{data['port']}")
        elif "socks5" in data["protocols"]:
            socks5_proxy_list.append(f"socks5://{data['ip']}:{data['port']}")
        elif "http" in data["protocols"]:
            http_proxy_list.append(f"http://{data['ip']}:{data['port']}")



# Function to test a single proxy
def test_proxy(proxy: str):
    try:
        response = requests.get(
            TEST_URL,
            proxies={"http": proxy, "https": proxy},
            impersonate="chrome120",
            timeout=5,  # Shorter timeout for testing (5s instead of 10s)
        )
        if response.status_code == 200:
            print(f"[✅ WORKING] {proxy}")
            working_proxy_list.append(proxy)
            return proxy
    except Exception:
        # Silently fail - most proxies are dead
        pass
    return None

# Async wrapper to test all proxies concurrently with limits
async def test_all_proxies(proxy_list, max_concurrent=50):
    """Test proxies with concurrency limit to avoid overwhelming free-tier hosts."""
    semaphore = asyncio.Semaphore(max_concurrent)

    async def test_with_limit(proxy):
        async with semaphore:
            return await asyncio.to_thread(test_proxy, proxy)

    tasks = [test_with_limit(proxy) for proxy in proxy_list]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    working_proxies = [p for p in results if p and not isinstance(p, Exception)]
    return working_proxies

async def get_working_proxies_async(max_proxies_to_test=200):
    """
    Fetches and tests proxies asynchronously.
    Can be called directly from async context (FastAPI lifespan).

    Args:
        max_proxies_to_test: Limit testing to this many proxies (useful for free-tier hosting)
    """
    print("📋 Clearing old proxy lists...", flush=True)
    working_proxy_list.clear()
    socks4_proxy_list.clear()
    socks5_proxy_list.clear()
    http_proxy_list.clear()

    print("📥 Fetching proxy lists from sources...", flush=True)
    try:
        await asyncio.to_thread(get_github_proxies, "socks4")
        await asyncio.to_thread(get_github_proxies, "socks5")
        await asyncio.to_thread(get_github_proxies, "http")
        await asyncio.to_thread(get_geonode_proxies)
    except Exception as e:
        print(f"⚠️ Error fetching proxies: {e}", flush=True)

    all_proxies = socks4_proxy_list + socks5_proxy_list + http_proxy_list
    total_fetched = len(all_proxies)

    # Limit proxies on free tier to avoid timeouts/memory issues
    if max_proxies_to_test and total_fetched > max_proxies_to_test:
        print(f"📊 Limiting to first {max_proxies_to_test} proxies (fetched {total_fetched})", flush=True)
        all_proxies = all_proxies[:max_proxies_to_test]
        total_fetched = len(all_proxies)

    print(f"📊 Testing {total_fetched} proxies...", flush=True)

    if total_fetched == 0:
        print("⚠️ No proxies fetched!", flush=True)
        return working_proxy_list

    # Test all proxies (directly await, no asyncio.run)
    await test_all_proxies(all_proxies)

    working_count = len(working_proxy_list)
    success_rate = (working_count / total_fetched * 100) if total_fetched > 0 else 0

    print(f"\n{'='*50}")
    print(f"✅ Testing complete!")
    print(f"📊 Total fetched: {total_fetched}")
    print(f"✅ Working proxies: {working_count}")
    print(f"❌ Failed proxies: {total_fetched - working_count}")
    print(f"📈 Success rate: {success_rate:.1f}%")
    print(f"{'='*50}\n")

    return working_proxy_list

def get_working_proxies():
    """
    Synchronous wrapper for get_working_proxies_async().
    Use this for standalone scripts. For FastAPI, use get_working_proxies_async() directly.
    """
    return asyncio.run(get_working_proxies_async())
