import os
import re
import subprocess
from pathlib import Path

from bs4 import BeautifulSoup
from curl_cffi import requests

from headers import video_headers


def extract_player_iframe_src(html_content: str) -> str | None:
    """
    Parses HTML and extracts the src URL from the iframe with id='player_iframe'.
    Returns the full https URL if found, otherwise None.
    """
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        iframe = soup.find('iframe', id='player_iframe')
        if not iframe:
            print("Could not find the iframe with id 'player_iframe'")
            return None

        src_url = iframe.get('src')

        if src_url and src_url.startswith('//'):
            src_url = 'https:' + src_url

        return src_url

    except Exception as e:
        print(f"Error parsing HTML: {e}")
        return None


def get_iframe_src(html_content):
    """
    Extracts the 'src' value starting with /prorcp/ from the JavaScript code.
    """
    # Regex pattern explanation:
    # src:\s* -> Matches 'src:' followed by optional whitespace
    # ['"]      -> Matches either a single or double quote opening
    # (/prorcp/.*?) -> Captures the path starting with /prorcp/ until the next quote
    # ['"]      -> Matches the closing quote
    pattern = r"src:\s*['\"](/prorcp/.*?)['\"]"

    match = re.search(pattern, html_content)

    if match:
        return f"https://cloudnestra.com{match.group(1)}" if match.group(1) else''
    return None


def extract_player_urls(html_content):
    # Regex explanation:
    # file:\s* -> Matches the key "file:" followed by optional whitespace
    # "         -> Matches the opening double quote
    # ([^"]+)   -> Capturing group: Matches any character that is NOT a double quote (the content)
    # "         -> Matches the closing double quote
    pattern = r'file:\s*"([^"]+)"'

    match = re.search(pattern, html_content)

    block_pattern = r"var\s+test_doms\s*=\s*\[([\s\S]*?)\];"

    match2 = re.search(block_pattern, html_content)
    video_urls=[]

    if match2:
        raw_array_content = match2.group(1)

        # Step 2: Extract the URLs from within that block
        # This looks for strings inside single or double quotes starting with http
        url_pattern = r'["\'](https?://.*?)["\']'

        video_urls = re.findall(url_pattern, raw_array_content)

    if match:
        # The captured group 1 contains the long string of URLs separated by " or "
        full_string = match.group(1)

        # Split the string into a list using the specific delimiter
        url_list = full_string.split(" or ")
        full_urls=[]
        for vdo_url in url_list:
            full_urls.append(get_mapped_url(vdo_url, video_urls))
        return full_urls
    else:
        return []


def get_mapped_url(template_url, domain_list):
    """
    Parses a template URL containing a {vN} placeholder and returns
    the full URL using the Nth domain from the provided list.

    Args:
        template_url (str): The URL containing {v1}, {v2}, etc.
        domain_list (list): List of replacement domain strings.

    Returns:
        str: The constructed URL, or None if the placeholder is invalid/missing.
    """
    # 1. Find the placeholder (e.g., {v1}, {v2})
    match = re.search(r'\{v(\d+)\}', template_url)

    if match:
        # 2. Extract the number and convert to 0-based index
        # {v1} becomes index 0, {v2} becomes index 1, etc.
        v_index = int(match.group(1)) - 1

        # 3. Check if the index exists in our domain list
        if 0 <= v_index < len(domain_list):
            # 4. Split the template at the placeholder to get the path
            # We discard the left part (old domain) and keep the right part (path)
            placeholder_str = match.group(0)
            path_part = template_url.split(placeholder_str, 1)[1]

            # 5. Combine new domain + path
            return domain_list[v_index] + path_part

    return None

def get_m3u8_stream(url: str, origin: str = "https://cloudnestra.com", referer: str = "https://cloudnestra.com/") -> str | None:

    try:
        # Method 1: Direct download with curl_cffi (bypasses CORS)
        download_file_direct(url, "video.mp4", "vidsrc", video_headers(url, origin, referer))

        # Method 2: Use yt-dlp (if Method 1 doesn't work)
        # download_file(url, "video.mp4", "vidsrc", headers)

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def download_file_direct(url, filename, folder_name, headers=None):
    """
    Alternative download method using curl_cffi (bypasses CORS issues)
    For m3u8 playlists, use ffmpeg instead
    """
    try:
        # Sanitize folder name
        sanitized_folder_name = "".join(c for c in folder_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        sanitized_folder_name = sanitized_folder_name.replace('  ', ' ')

        # Create downloads folder
        downloads_folder = Path.home() / "Downloads" / sanitized_folder_name
        os.makedirs(downloads_folder, exist_ok=True)

        output_path = os.path.join(downloads_folder, filename)

        print(f"Downloading: {filename}")

        # Check if it's an m3u8 playlist
        if '.m3u8' in url.lower():
            print("Detected m3u8 playlist, using ffmpeg...")
            return download_m3u8_with_ffmpeg(url, output_path, headers)

        # Download with curl_cffi (bypasses many restrictions)
        response = requests.get(url, headers=headers, impersonate="chrome120", stream=True)
        response.raise_for_status()

        # Write to file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"[+] Successfully downloaded: {output_path}")
        return output_path

    except Exception as e:
        print(f"[-] Failed to download {filename}: {e}")
        return None

def download_m3u8_with_ffmpeg(url, output_path, headers=None):
    """
    Download m3u8 playlist using ffmpeg (best for CORS issues)
    Install: brew install ffmpeg
    """
    try:
        cmd = [
            'ffmpeg',
            '-loglevel', 'warning',
            '-stats',
        ]

        # Add headers
        if headers:
            header_str = "\\r\\n".join([f"{k}: {v}" for k, v in headers.items()])
            cmd.extend(['-headers', header_str])

        cmd.extend([
            '-i', url,
            '-c', 'copy',  # Copy streams without re-encoding
            '-bsf:a', 'aac_adtstoasc',
            output_path
        ])

        print(f"Command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print(f"[+] Successfully downloaded: {output_path}")
        return output_path

    except FileNotFoundError:
        print("ffmpeg not found. Install with: brew install ffmpeg")
        return None
    except subprocess.CalledProcessError as e:
        print(f"[-] ffmpeg failed: {e}")
        return None

def download_file(url, filename, folder_name, headers=None):
    """Downloads a file from a URL using yt-dlp and saves it in a product-specific folder."""
    try:
        # Sanitize folder name by removing special characters
        sanitized_folder_name = "".join(c for c in folder_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        sanitized_folder_name = sanitized_folder_name.replace('  ', ' ')  # Replace multiple spaces with single space

        # Create downloads folder and product-specific subfolder
        downloads_folder = Path.home() / "Downloads" / sanitized_folder_name
        os.makedirs(downloads_folder, exist_ok=True)

        # Set the output path to product-specific folder
        output_path = os.path.join(downloads_folder, filename)

        # Use yt-dlp to download the file
        cmd = [
            'yt-dlp',
            '--no-check-certificate',  # Bypass SSL verification
            '--user-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
            '--concurrent-fragments', '5',  # Download fragments in parallel
            '--fragment-retries', '10',  # Retry failed fragments
            '--retries', '10',  # Retry failed downloads
            '--hls-prefer-native',  # Use native HLS downloader
            '-o', output_path,  # Output filename with product-specific folder path
        ]

        # Add headers if provided
        if headers:
            for key, value in headers.items():
                cmd.extend(['--add-header', f'{key}: {value}'])

        cmd.append(url)

        print(f"Downloading: {filename}")
        print(f"Command: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"[+] Successfully downloaded: {output_path}")

    except subprocess.CalledProcessError as e:
        print(f"[-] yt-dlp failed to download {filename}: {e.stderr}")
    except Exception as e:
        print(f"[-] Failed to download {filename}: {e}")