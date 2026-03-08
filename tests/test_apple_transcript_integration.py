"""Tests for Apple transcript integration in the core processing pipeline."""

from unittest.mock import MagicMock, patch

import pytest


class FakeEpisode:
    """Minimal episode stand-in for testing _get_apple_transcript."""

    def __init__(
        self,
        guid="test-guid",
        title="Test Episode",
        audio_url="https://example.com/ep.mp3",
    ):
        self.guid = guid
        self.title = title
        self.audio_url = audio_url
        self.transcript = None
        self.transcript_source = None
        self.transcript_url = None


def make_processor():
    """Create a PodcastProcessor with a mocked DB session and config."""
    with patch("podsidian.config.config", MagicMock()):
        from podsidian.core import PodcastProcessor

        db = MagicMock()
        processor = PodcastProcessor(db)
        return processor


# Patch targets for the local imports inside _get_apple_transcript
FIND_EP = "podsidian.apple_podcasts.find_episode_in_apple_db"
GET_TTML = "podsidian.apple_podcasts.get_cached_ttml"
PARSE_TTML = "podsidian.ttml_parser.parse_ttml"


class TestGetAppleTranscript:
    def test_returns_text_on_success(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": "transcript_99999.ttml", "store_track_id": 55555}
        ttml_xml = "<tt>dummy</tt>"
        parsed = {
            "text": "This is a valid Apple transcript with enough characters to pass validation."
        }

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value=ttml_xml),
            patch(PARSE_TTML, return_value=parsed),
        ):
            result = processor._get_apple_transcript(episode)
            assert result == parsed["text"]

    def test_returns_none_when_episode_not_found(self):
        processor = make_processor()
        episode = FakeEpisode()

        with patch(FIND_EP, return_value=None):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_returns_none_when_no_transcript_id(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": None, "store_track_id": 55555}

        with patch(FIND_EP, return_value=apple_ep):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_returns_none_when_no_ttml_cached(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": "t.ttml", "store_track_id": 123}

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value=None),
        ):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_returns_none_when_parse_fails(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": "t.ttml", "store_track_id": 123}

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value="<tt>x</tt>"),
            patch(PARSE_TTML, return_value=None),
        ):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_returns_none_when_text_too_short(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": "t.ttml", "store_track_id": 123}
        parsed = {"text": "Too short"}

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value="<tt>x</tt>"),
            patch(PARSE_TTML, return_value=parsed),
        ):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_returns_none_when_text_empty(self):
        processor = make_processor()
        episode = FakeEpisode()

        apple_ep = {"transcript_id": "t.ttml", "store_track_id": 123}
        parsed = {"text": "   "}

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value="<tt>x</tt>"),
            patch(PARSE_TTML, return_value=parsed),
        ):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_never_raises_on_exception(self):
        processor = make_processor()
        episode = FakeEpisode()

        with patch(FIND_EP, side_effect=Exception("boom")):
            result = processor._get_apple_transcript(episode)
            assert result is None

    def test_reports_progress_callback(self):
        processor = make_processor()
        episode = FakeEpisode()
        callback = MagicMock()

        apple_ep = {"transcript_id": "t.ttml", "store_track_id": 123}
        parsed = {"text": "A" * 100}

        with (
            patch(FIND_EP, return_value=apple_ep),
            patch(GET_TTML, return_value="<tt>x</tt>"),
            patch(PARSE_TTML, return_value=parsed),
        ):
            result = processor._get_apple_transcript(episode, progress_callback=callback)
            assert result is not None
            assert callback.call_count >= 2
            stages = [call.args[0]["stage"] for call in callback.call_args_list]
            assert "apple_transcript" in stages

    def test_exception_with_callback_reports_warning(self):
        processor = make_processor()
        episode = FakeEpisode()
        callback = MagicMock()

        with patch(FIND_EP, side_effect=RuntimeError("db locked")):
            result = processor._get_apple_transcript(episode, progress_callback=callback)
            assert result is None
            stages = [call.args[0]["stage"] for call in callback.call_args_list]
            assert "warning" in stages
