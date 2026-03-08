import logging
import os
import sqlite3
import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Local cache directory for Apple Podcasts TTML transcripts
TTML_CACHE_DIR = (
    Path.home()
    / "Library"
    / "Group Containers"
    / "243LU875E5.groups.com.apple.podcasts"
    / "Library"
    / "Cache"
    / "Assets"
    / "TTML"
)

def find_apple_podcast_db() -> Optional[str]:
    """Find the Apple Podcasts SQLite database in the Group Containers directory."""
    group_containers = Path.home() / "Library" / "Group Containers"
    
    if not group_containers.exists():
        return None
    
    for path in group_containers.rglob("MTLibrary.sqlite"):
        if path.is_file():
            return str(path)
    
    return None

def get_subscriptions() -> List[Dict[str, str]]:
    """Get all podcast subscriptions from Apple Podcasts."""
    db_path = find_apple_podcast_db()
    if not db_path:
        raise FileNotFoundError("Apple Podcasts database not found")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get podcast subscriptions
        cursor.execute("""
            SELECT ZTITLE, ZAUTHOR, ZFEEDURL 
            FROM ZMTPODCAST
            WHERE ZFEEDURL IS NOT NULL
        """)
        
        subscriptions = []
        for row in cursor.fetchall():
            subscriptions.append({
                'title': row[0],
                'author': row[1],
                'feed_url': row[2]
            })
        
        return subscriptions
        
    except sqlite3.Error as e:
        raise Exception(f"Error reading Apple Podcasts database: {e}")
    
    finally:
        if 'conn' in locals():
            conn.close()

def get_podcast_app_url(audio_url: str, guid: str = None, title: str = None) -> str:
    """Get the podcast:// URL for opening in Apple Podcasts app.
    
    This function tries to extract podcast ID and episode ID from the URL or find the
    corresponding podcast in the Apple Podcasts database using either the audio URL, GUID, or title.
    If found, it returns a podcast:// URL that will open the episode in the Apple Podcasts app.
    
    Args:
        audio_url: The audio URL from the episode
        guid: Optional episode GUID to use for lookup in Apple Podcasts database
        title: Optional episode title to use for lookup in Apple Podcasts database
        
    Returns:
        A podcast:// URL if found, or a generic podcast:// URL if not found
    """
    # Check if this is already an Apple Podcasts URL
    # Format: https://podcasts.apple.com/*/podcast/*/id<PODCAST_ID>?i=<EPISODE_ID>
    apple_pattern = r'podcasts\.apple\.com/[^/]+/podcast/[^/]+/id(\d+)\?i=(\d+)'
    match = re.search(apple_pattern, audio_url)
    if match:
        podcast_id, episode_id = match.groups()
        return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
    
    # Alternative format: https://podcasts.apple.com/*/podcast/*/id<PODCAST_ID>
    alt_pattern = r'podcasts\.apple\.com/[^/]+/podcast/[^/]+/id(\d+)'
    match = re.search(alt_pattern, audio_url)
    if match:
        podcast_id = match.group(1)
        return f"https://podcasts.apple.com/podcast/id{podcast_id}"
    
    # If not an Apple Podcasts URL, try to query the database
    try:
        db_path = find_apple_podcast_db()
        if not db_path:
            return "https://podcasts.apple.com"
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # If we have a GUID, use it for the query (preferred method)
        if guid:
            cursor.execute("""
                SELECT p.ZSTORECOLLECTIONID, e.ZSTORETRACKID 
                FROM ZMTEPISODE e
                JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
                WHERE e.ZGUID = ?
            """, (guid,))
            
            results = cursor.fetchall()
            if results and results[0][0] and results[0][1]:
                podcast_id, episode_id = results[0]
                return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
        
        # If no GUID or no results from GUID, try with the audio URL
        # Try matching on a significant portion of the URL path
        if audio_url:
            # Extract filename from URL for more specific matching
            filename_match = re.search(r'/([^/]+\.mp3)', audio_url)
            if filename_match:
                filename = filename_match.group(1)
                cursor.execute("""
                    SELECT p.ZSTORECOLLECTIONID, e.ZSTORETRACKID 
                    FROM ZMTEPISODE e
                    JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
                    WHERE e.ZASSETURL LIKE ?
                """, (f'%{filename}%',))
                
                results = cursor.fetchall()
                if results and results[0][0] and results[0][1]:
                    podcast_id, episode_id = results[0]
                    return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
            
            # If still no match, try with domain
            domain_match = re.search(r'https?://(?:www\.)?([^/]+)', audio_url)
            if domain_match:
                domain = domain_match.group(1)
                cursor.execute("""
                    SELECT p.ZSTORECOLLECTIONID, e.ZSTORETRACKID 
                    FROM ZMTEPISODE e
                    JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
                    WHERE e.ZASSETURL LIKE ?
                """, (f'%{domain}%',))
                
                results = cursor.fetchall()
                if results and results[0][0] and results[0][1]:
                    podcast_id, episode_id = results[0]
                    return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
        
        # If still no match and we have a title, try matching by title
        if title:
            # Clean the title and extract key words for matching
            # Remove common prefixes like "BONUS:" and clean up special characters
            clean_title = re.sub(r'^(BONUS|EPISODE|PREVIEW|TRAILER|TEASER):\s*', '', title, flags=re.IGNORECASE)
            clean_title = re.sub(r'[^\w\s]', '', clean_title).strip()
            
            # Extract significant words (longer than 3 chars, not common words)
            common_words = {'the', 'and', 'for', 'with', 'that', 'this', 'from', 'have', 'what', 'your', 'are', 'how'}
            words = [word for word in clean_title.split() if len(word) > 3 and word.lower() not in common_words]
            
            # Use the first 3 significant words for matching (or fewer if not enough words)
            significant_words = words[:min(3, len(words))]
            
            if significant_words:
                # Build a query that checks for each significant word
                query = """
                    SELECT p.ZSTORECOLLECTIONID, e.ZSTORETRACKID, e.ZTITLE
                    FROM ZMTEPISODE e
                    JOIN ZMTPODCAST p ON e.ZPODCAST = p.Z_PK
                    WHERE 
                """
                
                conditions = []
                params = []
                
                for word in significant_words:
                    conditions.append("e.ZTITLE LIKE ?")
                    params.append(f"%{word}%")
                
                query += " AND ".join(conditions)
                
                cursor.execute(query, params)
                results = cursor.fetchall()
                
                # If we get exactly one result, use it
                if len(results) == 1 and results[0][0] and results[0][1]:
                    podcast_id, episode_id = results[0][0], results[0][1]
                    return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
                
                # If we get multiple results, try to find the best match
                elif len(results) > 1:
                    best_match = None
                    best_match_score = 0
                    
                    for result in results:
                        if result[0] and result[1] and result[2]:  # Ensure we have podcast_id, episode_id, and title
                            # Simple scoring: count how many words from our significant words appear in the title
                            result_title = result[2].lower()
                            score = sum(1 for word in significant_words if word.lower() in result_title)
                            
                            # If this is a better match than what we've seen so far, update
                            if score > best_match_score:
                                best_match = result
                                best_match_score = score
                    
                    # If we found a good match (more than half the words match), use it
                    if best_match and best_match_score >= len(significant_words) / 2:
                        podcast_id, episode_id = best_match[0], best_match[1]
                        return f"https://podcasts.apple.com/podcast/id{podcast_id}?i={episode_id}"
        
        return "https://podcasts.apple.com"
        
    except sqlite3.Error as e:
        print(f"Error querying Apple Podcasts database: {e}")
        return "https://podcasts.apple.com"

    finally:
        if 'conn' in locals():
            conn.close()


def get_episode_transcript_info(guid: str) -> Optional[dict]:
    """Query Apple Podcasts DB for transcript info by episode GUID.

    Returns {"transcript_id": str, "store_track_id": int, "provider": str}
    if a transcript identifier exists, else None.
    """
    try:
        db_path = find_apple_podcast_db()
        if not db_path:
            return None

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT ZTRANSCRIPTIDENTIFIER, ZSTORETRACKID, ZFREETRANSCRIPTPROVIDER
                FROM ZMTEPISODE
                WHERE ZGUID = ? AND ZTRANSCRIPTIDENTIFIER IS NOT NULL
                """,
                (guid,),
            )
            row = cursor.fetchone()

            if not row:
                return None

            return {
                "transcript_id": row[0],
                "store_track_id": int(row[1]) if row[1] else None,
                "provider": row[2] or "apple",
            }
        finally:
            conn.close()

    except Exception as e:
        logger.warning("Error getting transcript info for GUID %s: %s", guid, e)
        return None


def get_cached_ttml(transcript_id: str, store_track_id: int) -> Optional[str]:
    """Check local TTML cache for a transcript file and return its contents.

    The file is expected at:
    {TTML_CACHE_DIR}/{transcript_id}-{store_track_id}.ttml

    Returns the file contents as a string, or None if not found.
    """
    try:
        filename = f"{transcript_id}-{store_track_id}.ttml"
        filepath = TTML_CACHE_DIR / filename
        if filepath.is_file():
            return filepath.read_text(encoding="utf-8")
        return None
    except Exception as e:
        logger.warning("Error reading cached TTML %s-%s: %s", transcript_id, store_track_id, e)
        return None


def find_episode_in_apple_db(
    guid: str = None, title: str = None, audio_url: str = None
) -> Optional[dict]:
    """Flexible lookup in ZMTEPISODE returning transcript-relevant data.

    Tries GUID first, then title fuzzy match, then audio URL match.

    Returns {"z_pk": int, "title": str, "guid": str,
             "transcript_id": str, "store_track_id": int} or None.
    """
    try:
        db_path = find_apple_podcast_db()
        if not db_path:
            return None

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        try:
            select_cols = (
                "Z_PK, ZTITLE, ZGUID, ZTRANSCRIPTIDENTIFIER, ZSTORETRACKID"
            )

            # 1. Try GUID
            if guid:
                cursor.execute(
                    f"SELECT {select_cols} FROM ZMTEPISODE WHERE ZGUID = ?",
                    (guid,),
                )
                row = cursor.fetchone()
                if row:
                    return _row_to_episode_dict(row)

            # 2. Try title fuzzy match
            if title:
                clean_title = re.sub(
                    r"^(BONUS|EPISODE|PREVIEW|TRAILER|TEASER):\s*",
                    "",
                    title,
                    flags=re.IGNORECASE,
                )
                clean_title = re.sub(r"[^\w\s]", "", clean_title).strip()

                common_words = {
                    "the", "and", "for", "with", "that", "this",
                    "from", "have", "what", "your", "are", "how",
                }
                words = [
                    w for w in clean_title.split()
                    if len(w) > 3 and w.lower() not in common_words
                ]
                significant_words = words[:3]

                if significant_words:
                    conditions = ["ZTITLE LIKE ?" for _ in significant_words]
                    params = [f"%{w}%" for w in significant_words]

                    cursor.execute(
                        f"SELECT {select_cols} FROM ZMTEPISODE WHERE "
                        + " AND ".join(conditions),
                        params,
                    )
                    rows = cursor.fetchall()

                    if len(rows) == 1:
                        return _row_to_episode_dict(rows[0])
                    elif len(rows) > 1:
                        best = None
                        best_score = 0
                        for row in rows:
                            row_title = (row[1] or "").lower()
                            score = sum(
                                1 for w in significant_words if w.lower() in row_title
                            )
                            if score > best_score:
                                best = row
                                best_score = score
                        if best and best_score >= len(significant_words) / 2:
                            return _row_to_episode_dict(best)

            # 3. Try audio URL
            if audio_url:
                filename_match = re.search(r"/([^/]+\.mp3)", audio_url)
                if filename_match:
                    cursor.execute(
                        f"SELECT {select_cols} FROM ZMTEPISODE WHERE ZASSETURL LIKE ?",
                        (f"%{filename_match.group(1)}%",),
                    )
                    row = cursor.fetchone()
                    if row:
                        return _row_to_episode_dict(row)

            return None
        finally:
            conn.close()

    except Exception as e:
        logger.warning("Error finding episode in Apple DB: %s", e)
        return None


def _row_to_episode_dict(row: tuple) -> dict:
    """Convert a ZMTEPISODE row to a transcript info dict."""
    return {
        "z_pk": row[0],
        "title": row[1],
        "guid": row[2],
        "transcript_id": row[3],
        "store_track_id": int(row[4]) if row[4] else None,
    }


# HTTP timeout for all CDN requests (seconds)
_CDN_TIMEOUT = 10


def _get_apple_bearer_token() -> Optional[str]:
    """Get Apple Podcasts API bearer token from environment or token service.

    The amp-api.podcasts.apple.com endpoint requires a bearer token.
    Apple's token service (sf-api-token-service.itunes.apple.com) requires
    an X-Apple-ActionSignature generated by Apple's private AMSMescal framework,
    which cannot be reproduced programmatically.

    Users can provide a pre-captured token via the APPLE_PODCASTS_TOKEN env var.
    To capture a token: use a network proxy (e.g. mitmproxy) to intercept a
    request from Apple Podcasts.app to amp-api.podcasts.apple.com, then copy
    the Authorization header value (without the "Bearer " prefix).

    See: https://blog.alexbeals.com/posts/downloading-arbitrary-apple-podcast-episode-transcripts
    """
    token = os.environ.get("APPLE_PODCASTS_TOKEN", "").strip()
    return token if token else None


def _try_amp_api_download(store_track_id: int, token: str) -> Optional[str]:
    """Attempt to download TTML via Apple's AMP API (Approach A).

    Fetches transcript metadata from the catalog API, which returns a signed
    CDN URL with an accessKey. Then downloads the TTML from that URL.
    """
    try:
        resp = requests.get(
            f"https://amp-api.podcasts.apple.com/v1/catalog/us/"
            f"podcast-episodes/{store_track_id}/transcripts",
            params={
                "fields": "ttmlToken,ttmlAssetUrls",
                "l": "en-US",
                "with": "entitlements",
            },
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": "https://podcasts.apple.com",
            },
            timeout=_CDN_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.debug(
                "AMP API returned %d for track %s", resp.status_code, store_track_id
            )
            return None

        data = resp.json().get("data", [])
        if not data:
            return None

        ttml_url = (
            data[0].get("attributes", {}).get("ttmlAssetUrls", {}).get("ttml")
        )
        if not ttml_url:
            logger.debug("No ttmlAssetUrls in AMP API response for track %s", store_track_id)
            return None

        ttml_resp = requests.get(ttml_url, timeout=_CDN_TIMEOUT)
        if ttml_resp.status_code == 200 and ttml_resp.text.strip():
            return ttml_resp.text
        return None

    except Exception as e:
        logger.debug("AMP API download failed for track %s: %s", store_track_id, e)
        return None


def _try_direct_cdn_download(transcript_id: str) -> Optional[str]:
    """Attempt direct CDN URL patterns (Approach B).

    These URLs occasionally work without authentication for public content.
    """
    cdn_patterns = [
        f"https://podcasts.apple.com/library/content/{transcript_id}",
        f"https://pc-aod.apple.com/{transcript_id}",
    ]
    for url in cdn_patterns:
        try:
            resp = requests.get(url, timeout=_CDN_TIMEOUT)
            if resp.status_code == 200 and "<tt" in resp.text:
                return resp.text
        except Exception as e:
            logger.debug("Direct CDN download failed for %s: %s", url, e)
    return None


def _cache_ttml(transcript_id: str, store_track_id: int, content: str) -> None:
    """Cache downloaded TTML content locally for future use."""
    try:
        TTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{transcript_id}-{store_track_id}.ttml"
        filepath = TTML_CACHE_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        logger.debug("Cached TTML to %s", filepath)
    except Exception as e:
        logger.debug("Failed to cache TTML: %s", e)


def download_apple_ttml(
    transcript_id: str, store_track_id: int
) -> Optional[str]:
    """Download or retrieve an Apple Podcasts TTML transcript.

    Checks the local cache first (fast, reliable), then attempts CDN download
    as a best-effort bonus. Returns the TTML content string or None.

    CDN download requires an APPLE_PODCASTS_TOKEN environment variable
    containing a valid Apple Podcasts API bearer token. Without it, only
    the local cache is checked.

    Args:
        transcript_id: The ZTRANSCRIPTIDENTIFIER from the Apple Podcasts DB.
        store_track_id: The ZSTORETRACKID (episode ID in Apple's catalog).

    Returns:
        TTML file contents as a string, or None if unavailable.
    """
    try:
        # Step 1: Always check local cache first (fast, no network)
        cached = get_cached_ttml(transcript_id, store_track_id)
        if cached:
            return cached

        # Step 2: Try CDN download (best-effort)
        # Approach A: AMP API with bearer token (most reliable if token available)
        token = _get_apple_bearer_token()
        if token and store_track_id:
            logger.debug("Attempting AMP API download for track %s", store_track_id)
            content = _try_amp_api_download(store_track_id, token)
            if content:
                _cache_ttml(transcript_id, store_track_id, content)
                return content

        # Approach B: Direct CDN URL patterns (no auth, rarely works)
        if transcript_id:
            logger.debug("Attempting direct CDN download for %s", transcript_id)
            content = _try_direct_cdn_download(transcript_id)
            if content:
                _cache_ttml(transcript_id, store_track_id, content)
                return content

        # Approach C: Return None, fall back to Whisper
        logger.debug(
            "No TTML available for transcript_id=%s, store_track_id=%s",
            transcript_id,
            store_track_id,
        )
        return None
    except Exception as e:
        logger.warning("Unexpected error in download_apple_ttml: %s", e)
        return None
