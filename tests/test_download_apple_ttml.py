"""Tests for Apple Podcasts CDN transcript download."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from podsidian.apple_podcasts import (
    download_apple_ttml,
    _get_apple_bearer_token,
    _try_amp_api_download,
    _try_direct_cdn_download,
    _cache_ttml,
)


SAMPLE_TTML = '<?xml version="1.0"?><tt><body><div><p>Hello world</p></div></body></tt>'


class TestGetAppleBearerToken:
    def test_returns_token_from_env(self):
        with patch.dict("os.environ", {"APPLE_PODCASTS_TOKEN": "test-token-123"}):
            assert _get_apple_bearer_token() == "test-token-123"

    def test_returns_none_when_not_set(self):
        with patch.dict("os.environ", {}, clear=True):
            assert _get_apple_bearer_token() is None

    def test_returns_none_for_empty_string(self):
        with patch.dict("os.environ", {"APPLE_PODCASTS_TOKEN": "  "}):
            assert _get_apple_bearer_token() is None


class TestTryAmpApiDownload:
    def test_successful_download(self):
        api_response = {
            "data": [
                {
                    "attributes": {
                        "ttmlAssetUrls": {
                            "ttml": "https://cdn.example.com/transcript.ttml?accessKey=abc"
                        }
                    }
                }
            ]
        }

        mock_api_resp = MagicMock()
        mock_api_resp.status_code = 200
        mock_api_resp.json.return_value = api_response

        mock_ttml_resp = MagicMock()
        mock_ttml_resp.status_code = 200
        mock_ttml_resp.text = SAMPLE_TTML

        with patch("podsidian.apple_podcasts.requests.get") as mock_get:
            mock_get.side_effect = [mock_api_resp, mock_ttml_resp]
            result = _try_amp_api_download(55555, "test-token")
            assert result == SAMPLE_TTML

    def test_returns_none_on_401(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            assert _try_amp_api_download(55555, "bad-token") is None

    def test_returns_none_on_empty_data(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": []}

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            assert _try_amp_api_download(55555, "token") is None

    def test_returns_none_on_no_ttml_url(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"attributes": {"ttmlAssetUrls": {}}}]}

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            assert _try_amp_api_download(55555, "token") is None

    def test_returns_none_on_network_error(self):
        with patch(
            "podsidian.apple_podcasts.requests.get",
            side_effect=Exception("Connection timeout"),
        ):
            assert _try_amp_api_download(55555, "token") is None


class TestTryDirectCdnDownload:
    def test_successful_download(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = SAMPLE_TTML

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            result = _try_direct_cdn_download("PodcastContent221/v4/transcript.ttml")
            assert result == SAMPLE_TTML

    def test_returns_none_on_404(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            assert _try_direct_cdn_download("nonexistent") is None

    def test_returns_none_on_non_ttml_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html>Not a TTML file</html>"

        with patch("podsidian.apple_podcasts.requests.get", return_value=mock_resp):
            assert _try_direct_cdn_download("test") is None

    def test_returns_none_on_exception(self):
        with patch(
            "podsidian.apple_podcasts.requests.get",
            side_effect=Exception("Network error"),
        ):
            assert _try_direct_cdn_download("test") is None


class TestCacheTtml:
    def test_caches_to_file(self, tmp_path):
        with patch("podsidian.apple_podcasts.TTML_CACHE_DIR", tmp_path):
            _cache_ttml("transcript_123", 55555, SAMPLE_TTML)
            cached = tmp_path / "transcript_123-55555.ttml"
            assert cached.is_file()
            assert cached.read_text(encoding="utf-8") == SAMPLE_TTML

    def test_creates_directory(self, tmp_path):
        cache_dir = tmp_path / "nested" / "dir"
        with patch("podsidian.apple_podcasts.TTML_CACHE_DIR", cache_dir):
            _cache_ttml("transcript_123", 55555, SAMPLE_TTML)
            assert (cache_dir / "transcript_123-55555.ttml").is_file()

    def test_never_raises(self):
        with patch(
            "podsidian.apple_podcasts.TTML_CACHE_DIR",
            Path("/nonexistent/readonly/path"),
        ):
            # Should not raise
            _cache_ttml("test", 123, SAMPLE_TTML)


class TestDownloadAppleTtml:
    def test_returns_cached_content_first(self, tmp_path):
        ttml_file = tmp_path / "tid-55555.ttml"
        ttml_file.write_text(SAMPLE_TTML)

        with patch("podsidian.apple_podcasts.TTML_CACHE_DIR", tmp_path):
            result = download_apple_ttml("tid", 55555)
            assert result == SAMPLE_TTML

    def test_tries_amp_api_when_not_cached(self):
        with (
            patch("podsidian.apple_podcasts.get_cached_ttml", return_value=None),
            patch.dict("os.environ", {"APPLE_PODCASTS_TOKEN": "test-token"}),
            patch(
                "podsidian.apple_podcasts._try_amp_api_download",
                return_value=SAMPLE_TTML,
            ) as mock_amp,
            patch("podsidian.apple_podcasts._cache_ttml") as mock_cache,
        ):
            result = download_apple_ttml("tid", 55555)
            assert result == SAMPLE_TTML
            mock_amp.assert_called_once_with(55555, "test-token")
            mock_cache.assert_called_once_with("tid", 55555, SAMPLE_TTML)

    def test_tries_direct_cdn_after_amp_fails(self):
        with (
            patch("podsidian.apple_podcasts.get_cached_ttml", return_value=None),
            patch.dict("os.environ", {"APPLE_PODCASTS_TOKEN": "test-token"}),
            patch("podsidian.apple_podcasts._try_amp_api_download", return_value=None),
            patch(
                "podsidian.apple_podcasts._try_direct_cdn_download",
                return_value=SAMPLE_TTML,
            ) as mock_cdn,
            patch("podsidian.apple_podcasts._cache_ttml") as mock_cache,
        ):
            result = download_apple_ttml("tid", 55555)
            assert result == SAMPLE_TTML
            mock_cdn.assert_called_once_with("tid")
            mock_cache.assert_called_once()

    def test_skips_amp_without_token(self):
        with (
            patch("podsidian.apple_podcasts.get_cached_ttml", return_value=None),
            patch.dict("os.environ", {}, clear=True),
            patch("podsidian.apple_podcasts._try_amp_api_download") as mock_amp,
            patch(
                "podsidian.apple_podcasts._try_direct_cdn_download",
                return_value=None,
            ),
        ):
            result = download_apple_ttml("tid", 55555)
            assert result is None
            mock_amp.assert_not_called()

    def test_returns_none_when_all_fail(self):
        with (
            patch("podsidian.apple_podcasts.get_cached_ttml", return_value=None),
            patch.dict("os.environ", {"APPLE_PODCASTS_TOKEN": "test-token"}),
            patch("podsidian.apple_podcasts._try_amp_api_download", return_value=None),
            patch(
                "podsidian.apple_podcasts._try_direct_cdn_download",
                return_value=None,
            ),
        ):
            result = download_apple_ttml("tid", 55555)
            assert result is None
