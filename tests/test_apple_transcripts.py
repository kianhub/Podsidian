"""Tests for Apple Podcasts transcript lookup functions."""

import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from podsidian.apple_podcasts import (
    TTML_CACHE_DIR,
    find_episode_in_apple_db,
    get_cached_ttml,
    get_episode_transcript_info,
)


@pytest.fixture
def mock_apple_db(tmp_path):
    """Create a temporary Apple Podcasts-style SQLite database."""
    db_path = str(tmp_path / "MTLibrary.sqlite")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE ZMTEPISODE (
            Z_PK INTEGER PRIMARY KEY,
            ZTITLE TEXT,
            ZGUID TEXT,
            ZTRANSCRIPTIDENTIFIER TEXT,
            ZSTORETRACKID INTEGER,
            ZFREETRANSCRIPTPROVIDER TEXT,
            ZASSETURL TEXT,
            ZPODCAST INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE ZMTPODCAST (
            Z_PK INTEGER PRIMARY KEY,
            ZSTORECOLLECTIONID INTEGER,
            ZTITLE TEXT,
            ZAUTHOR TEXT,
            ZFEEDURL TEXT
        )
    """)
    # Insert test data
    cursor.execute("""
        INSERT INTO ZMTPODCAST (Z_PK, ZSTORECOLLECTIONID, ZTITLE, ZAUTHOR, ZFEEDURL)
        VALUES (1, 12345, 'Test Podcast', 'Test Author', 'https://example.com/feed')
    """)
    cursor.execute("""
        INSERT INTO ZMTEPISODE
        (Z_PK, ZTITLE, ZGUID, ZTRANSCRIPTIDENTIFIER, ZSTORETRACKID,
         ZFREETRANSCRIPTPROVIDER, ZASSETURL, ZPODCAST)
        VALUES (1, 'Test Episode', 'test-guid-123',
                'PodcastContent221/v4/transcript_99999.ttml', 55555,
                'apple', 'https://example.com/audio/ep1.mp3', 1)
    """)
    cursor.execute("""
        INSERT INTO ZMTEPISODE
        (Z_PK, ZTITLE, ZGUID, ZTRANSCRIPTIDENTIFIER, ZSTORETRACKID,
         ZFREETRANSCRIPTPROVIDER, ZASSETURL, ZPODCAST)
        VALUES (2, 'Another Episode Title', 'guid-456', NULL, 66666,
                NULL, 'https://example.com/audio/ep2.mp3', 1)
    """)
    conn.commit()
    conn.close()
    return db_path


class TestGetEpisodeTranscriptInfo:
    def test_found_by_guid(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = get_episode_transcript_info("test-guid-123")
            assert result is not None
            assert result["transcript_id"] == "PodcastContent221/v4/transcript_99999.ttml"
            assert result["store_track_id"] == 55555
            assert result["provider"] == "apple"

    def test_not_found(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = get_episode_transcript_info("nonexistent-guid")
            assert result is None

    def test_no_transcript_id(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            # guid-456 has no transcript identifier
            result = get_episode_transcript_info("guid-456")
            assert result is None

    def test_no_db(self):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=None,
        ):
            result = get_episode_transcript_info("any-guid")
            assert result is None

    def test_never_raises(self):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            side_effect=Exception("boom"),
        ):
            result = get_episode_transcript_info("any-guid")
            assert result is None


class TestGetCachedTtml:
    def test_found(self, tmp_path):
        ttml_content = "<tt>test</tt>"
        ttml_file = tmp_path / "transcript_99999.ttml-55555.ttml"
        ttml_file.write_text(ttml_content)

        with patch(
            "podsidian.apple_podcasts.TTML_CACHE_DIR",
            tmp_path,
        ):
            result = get_cached_ttml("transcript_99999.ttml", 55555)
            assert result == ttml_content

    def test_not_found(self, tmp_path):
        with patch(
            "podsidian.apple_podcasts.TTML_CACHE_DIR",
            tmp_path,
        ):
            result = get_cached_ttml("nonexistent", 99999)
            assert result is None

    def test_never_raises(self):
        with patch(
            "podsidian.apple_podcasts.TTML_CACHE_DIR",
            Path("/nonexistent/path/that/does/not/exist"),
        ):
            result = get_cached_ttml("test", 123)
            assert result is None


class TestFindEpisodeInAppleDb:
    def test_find_by_guid(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = find_episode_in_apple_db(guid="test-guid-123")
            assert result is not None
            assert result["z_pk"] == 1
            assert result["title"] == "Test Episode"
            assert result["guid"] == "test-guid-123"
            assert result["transcript_id"] == "PodcastContent221/v4/transcript_99999.ttml"
            assert result["store_track_id"] == 55555

    def test_find_by_title(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = find_episode_in_apple_db(title="Another Episode Title")
            assert result is not None
            assert result["z_pk"] == 2

    def test_find_by_audio_url(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = find_episode_in_apple_db(
                audio_url="https://example.com/audio/ep1.mp3"
            )
            assert result is not None
            assert result["z_pk"] == 1

    def test_not_found(self, mock_apple_db):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=mock_apple_db,
        ):
            result = find_episode_in_apple_db(guid="nope")
            assert result is None

    def test_no_db(self):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            return_value=None,
        ):
            result = find_episode_in_apple_db(guid="any")
            assert result is None

    def test_never_raises(self):
        with patch(
            "podsidian.apple_podcasts.find_apple_podcast_db",
            side_effect=Exception("boom"),
        ):
            result = find_episode_in_apple_db(guid="any")
            assert result is None


class TestTtmlCacheDir:
    def test_constant_exists(self):
        assert TTML_CACHE_DIR is not None
        assert "TTML" in str(TTML_CACHE_DIR)
        assert "243LU875E5.groups.com.apple.podcasts" in str(TTML_CACHE_DIR)
