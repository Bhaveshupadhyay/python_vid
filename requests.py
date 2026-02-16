import time
import random
from typing import List, Dict

from extract import extract_player_iframe_src, extract_player_urls, get_iframe_src, get_m3u8_stream
from proxy import working_proxy_list
from headers import video_headers, cloud_nestra_headers, cloud_nestra_prorcp_headers
from curl_cffi import requests
from pydantic import BaseModel

last_working_proxy = None

def get_random_proxy(is_latest:bool=False) -> dict | None:
    """
    Get a random proxy from the working proxy list.
    Returns a dict formatted for curl_cffi requests.
    Returns None if no working proxies available (will use direct connection).
    """
    if last_working_proxy:
        return {"http": last_working_proxy, "https": last_working_proxy}
    if not working_proxy_list:
        # No proxies available - will fallback to direct connection
        return None

    if is_latest:
        proxy = working_proxy_list[-1]
    else:
        proxy = random.choice(working_proxy_list)
    # Format: {"http": "socks5://ip:port", "https": "socks5://ip:port"}
    return {"http": proxy, "https": proxy}


def fetch_vidsrc_embed(url: str, max_retries: int = 3, use_proxy: bool = True) -> str | None:
    """
    Fetches vidsrc embed page with retry logic.
    Retries up to max_retries times with exponential backoff.
    """
    headers = {
        "Referer": "https://vidsrc.xyz/",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    for attempt in range(max_retries):
        # First attempt: use random proxy
        # Retry attempts: use last proxy from list
        proxy_dict = get_random_proxy(is_latest=attempt!=0) if use_proxy else None
        try:
            if proxy_dict:
                print(f"Attempt {attempt + 1}/{max_retries}: Fetching {url} via proxy {proxy_dict['http']}")
            else:
                print(f"Attempt {attempt + 1}/{max_retries}: Fetching {url} (no proxy)")

            # 'impersonate' makes the server think this is real Chrome
            response = requests.get(
                url,
                headers=headers,
                proxies=proxy_dict,  # Add proxy here
                impersonate="chrome120",
                timeout=10
            )

            # Check for success
            if response.status_code == 200:
                print(f"✓ Success! Status Code: {response.status_code}")
                global last_working_proxy
                last_working_proxy = proxy_dict['http'] if proxy_dict else None
                return response.text

            print(f"✗ Failed with status: {response.status_code}")

            # Don't retry on client errors (4xx), only server errors (5xx) and timeouts
            if 400 <= response.status_code < 500:
                return None

        except TimeoutError:
            print(f"✗ Request timed out on attempt {attempt + 1}")
        except Exception as e:
            print(f"✗ Error on attempt {attempt + 1}: {type(e).__name__}: {e}")

        if proxy_dict and proxy_dict['http'] in working_proxy_list:
            working_proxy_list.remove(proxy_dict['http'])
            last_working_proxy = None
        # Exponential backoff: wait 1s, 2s, 4s between retries
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            print(f"⏳ Waiting {wait_time}s before retry...")
            time.sleep(wait_time)

    print(f"✗ All {max_retries} attempts failed")
    return None

# cloudnestra_url = "https://cloudnestra.com/rcp/..."
# referer = "https://vidsrc.xyz/embed/movie/tt5433140"

def get_cloudnestra(url: str, referer: str, max_retries: int = 3, use_proxy: bool = True) -> str | None:
    """Fetches cloudnestra page with retry logic."""

    for attempt in range(max_retries):
        # First attempt: random proxy, retries: last proxy
        proxy_dict = get_random_proxy(is_latest=attempt!=0) if use_proxy else None

        try:
            response = requests.get(
                url,
                headers=cloud_nestra_headers(referer=referer),
                proxies=proxy_dict,
                impersonate="chrome120",
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ Cloudnestra fetch success")
                global last_working_proxy
                last_working_proxy = proxy_dict['http'] if proxy_dict else None
                return response.text

            print(f"✗ Cloudnestra failed with status: {response.status_code}")
            if 400 <= response.status_code < 500:
                return None

        except TimeoutError:
            print(f"✗ Cloudnestra request timed out on attempt {attempt + 1}")
        except Exception as e:
            print(f"✗ Cloudnestra error on attempt {attempt + 1}: {type(e).__name__}: {e}")

        if proxy_dict and proxy_dict['http'] in working_proxy_list:
            working_proxy_list.remove(proxy_dict['http'])
            last_working_proxy = None

        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            print(f"⏳ Retrying cloudnestra in {wait_time}s...")
            time.sleep(wait_time)

    return None


def get_cloudnestra_prorcp(url: str, referer: str, max_retries: int = 3, use_proxy: bool = True) -> str | None:
    """Fetches cloudnestra prorcp page with retry logic."""

    for attempt in range(max_retries):
        # First attempt: random proxy, retries: last proxy
        proxy_dict = get_random_proxy(is_latest=attempt!=0) if use_proxy else None

        try:
            response = requests.get(
                url,
                headers=cloud_nestra_prorcp_headers(referer=referer),
                proxies=proxy_dict,
                impersonate="chrome120",
                timeout=10
            )

            if response.status_code == 200:
                print(f"✓ Prorcp fetch success")
                global last_working_proxy
                last_working_proxy = proxy_dict['http'] if proxy_dict else None
                return response.text

            print(f"✗ Prorcp failed with status: {response.status_code}")
            if 400 <= response.status_code < 500:
                return None

        except TimeoutError:
            print(f"✗ Prorcp request timed out on attempt {attempt + 1}")
        except Exception as e:
            print(f"✗ Prorcp error on attempt {attempt + 1}: {type(e).__name__}: {e}")

        if proxy_dict and proxy_dict['http'] in working_proxy_list:
            working_proxy_list.remove(proxy_dict['http'])
            last_working_proxy = None

        if attempt < max_retries - 1:
            wait_time = 2 ** attempt
            print(f"⏳ Retrying prorcp in {wait_time}s...")
            time.sleep(wait_time)

    return None


async def get_streaming_url(vidsrc_url: str):
    # Step 1: Fetch initial embed page
    print(f"Fetching vidsrc embed page: {vidsrc_url}")
    html_content = fetch_vidsrc_embed(vidsrc_url)
    if not html_content:
        print("Error: Failed to fetch vidsrc embed")
        return None

    # Step 2: Extract cloudnestra URL from iframe
    cloudnestra_url_1 = extract_player_iframe_src(html_content)
    if not cloudnestra_url_1:
        print("Error: Failed to extract player iframe src")
        return None
    print(f"Cloudnestra URL 1: {cloudnestra_url_1}")

    # Step 3: Fetch cloudnestra page
    cloudnestra_content = get_cloudnestra(cloudnestra_url_1, vidsrc_url)
    if not cloudnestra_content:
        print("Error: Failed to fetch cloudnestra content")
        return None

    # Step 4: Extract prorcp URL
    cloudnestra_url_2 = get_iframe_src(cloudnestra_content)
    if not cloudnestra_url_2:
        print("Error: Failed to extract iframe src from cloudnestra")
        return None
    print(f"Cloudnestra URL 2: {cloudnestra_url_2}")

    # Step 5: Fetch player data
    player_data = get_cloudnestra_prorcp(cloudnestra_url_2, cloudnestra_url_1)
    if not player_data:
        print("Error: Failed to fetch player data")
        return None

    # Step 6: Extract streaming URLs
    urls = extract_player_urls(player_data)
    if not urls or len(urls) == 0:
        print("Error: No streaming URLs found")
        return None
    video_models = []
    for url in urls:
        if not url: continue
        origin = "https://cloudnestra.com"
        referer = "https://cloudnestra.com/"
        video_models.append(VideoModelResponse(url=url, headers=video_headers(url, origin, referer)))

    return video_models

class VideoModelResponse(BaseModel):
    url: str
    headers: Dict[str, str]

if __name__ == "__main__":
    url = "https://vidsrc.xyz/embed/movie/tt5433140"
    referer = "https://vidsrc.xyz/embed/movie/tt5433140"
    html_content = fetch_vidsrc_embed(url)
    cloudnestra_url_1 = extract_player_iframe_src(html_content)
    cloudnestra_url_2 = get_iframe_src(get_cloudnestra(cloudnestra_url_1, referer))
    player_data= get_cloudnestra_prorcp(cloudnestra_url_2, cloudnestra_url_1)
    link= extract_player_urls(player_data)[0]
    print(link)
    get_m3u8_stream(link)

    # Example: Using a Session with impersonate
    # session = Session()
    # headers = {"Referer": "https://vidsrc.xyz/"}
    # response = session.get(url, headers=headers, impersonate="chrome120")
    # print(response.text)