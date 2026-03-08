"""Tests for Apple transcript configuration, speaker label toggle, and priority logic."""

from unittest.mock import patch, MagicMock
import pytest

from podsidian.config import Config, DEFAULT_CONFIG
from podsidian.ttml_parser import parse_ttml


# --- Sample TTML for speaker label tests ---

SAMPLE_TTML = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <body>
    <div>
      <p ttm:agent="SPEAKER_0">
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="0.500" end="0.900">Hello</span>
          <span podcasts:unit="word" begin="1.000" end="1.500">world.</span>
        </span>
      </p>
      <p ttm:agent="SPEAKER_1">
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="2.000" end="2.300">Hi</span>
          <span podcasts:unit="word" begin="2.400" end="2.800">there.</span>
        </span>
      </p>
    </div>
  </body>
</tt>
"""


class TestAppleTranscriptsConfig:
    """Test that apple_transcripts config defaults and properties work correctly."""

    def test_defaults_in_default_config(self):
        assert "apple_transcripts" in DEFAULT_CONFIG
        assert DEFAULT_CONFIG["apple_transcripts"]["enabled"] is True
        assert DEFAULT_CONFIG["apple_transcripts"]["prefer_over_rss"] is False
        assert DEFAULT_CONFIG["apple_transcripts"]["include_speaker_labels"] is True

    def test_config_properties_with_defaults(self):
        with patch("os.path.exists", return_value=False):
            cfg = Config()
        assert cfg.apple_transcripts_enabled is True
        assert cfg.apple_transcripts_prefer_over_rss is False
        assert cfg.apple_transcripts_include_speaker_labels is True

    def test_config_missing_section_uses_defaults(self):
        """If [apple_transcripts] section is entirely missing, defaults apply."""
        with patch("os.path.exists", return_value=False):
            cfg = Config()
        # Simulate missing section by removing it from loaded config
        del cfg.config["apple_transcripts"]
        assert cfg.apple_transcripts_enabled is True
        assert cfg.apple_transcripts_prefer_over_rss is False
        assert cfg.apple_transcripts_include_speaker_labels is True

    def test_config_override_enabled_false(self):
        with patch("os.path.exists", return_value=False):
            cfg = Config()
        cfg.config["apple_transcripts"]["enabled"] = False
        assert cfg.apple_transcripts_enabled is False

    def test_config_override_prefer_over_rss_true(self):
        with patch("os.path.exists", return_value=False):
            cfg = Config()
        cfg.config["apple_transcripts"]["prefer_over_rss"] = True
        assert cfg.apple_transcripts_prefer_over_rss is True

    def test_config_override_include_speaker_labels_false(self):
        with patch("os.path.exists", return_value=False):
            cfg = Config()
        cfg.config["apple_transcripts"]["include_speaker_labels"] = False
        assert cfg.apple_transcripts_include_speaker_labels is False


class TestParseTtmlSpeakerLabels:
    """Test parse_ttml include_speaker_labels parameter."""

    def test_speaker_labels_included_by_default(self):
        result = parse_ttml(SAMPLE_TTML)
        assert result is not None
        assert "[Speaker 1]:" in result["text"]
        assert "[Speaker 2]:" in result["text"]

    def test_speaker_labels_included_explicitly(self):
        result = parse_ttml(SAMPLE_TTML, include_speaker_labels=True)
        assert result is not None
        assert "[Speaker 1]:" in result["text"]
        assert "[Speaker 2]:" in result["text"]

    def test_speaker_labels_excluded(self):
        result = parse_ttml(SAMPLE_TTML, include_speaker_labels=False)
        assert result is not None
        assert "[Speaker 1]:" not in result["text"]
        assert "[Speaker 2]:" not in result["text"]
        # But the actual text content should still be there
        assert "Hello world." in result["text"]
        assert "Hi there." in result["text"]

    def test_segments_still_have_speaker_when_labels_excluded(self):
        """Segments should always contain speaker info regardless of label setting."""
        result = parse_ttml(SAMPLE_TTML, include_speaker_labels=False)
        assert result is not None
        assert result["segments"][0]["speaker"] == "Speaker 1"
        assert result["segments"][1]["speaker"] == "Speaker 2"


class TestGetAppleTranscriptEnabledFlag:
    """Test that _get_apple_transcript respects the enabled config flag."""

    def test_returns_none_when_disabled(self):
        """When apple_transcripts.enabled is False, should return None immediately."""
        from podsidian.core import PodcastProcessor

        mock_session = MagicMock()
        processor = PodcastProcessor(mock_session)

        # Override config to disable apple transcripts
        processor.config = MagicMock()
        processor.config.apple_transcripts_enabled = False

        mock_episode = MagicMock()
        result = processor._get_apple_transcript(mock_episode)
        assert result is None

    def test_returns_none_when_disabled_with_callback(self):
        """When disabled, callback should report it's disabled."""
        from podsidian.core import PodcastProcessor

        mock_session = MagicMock()
        processor = PodcastProcessor(mock_session)
        processor.config = MagicMock()
        processor.config.apple_transcripts_enabled = False

        mock_episode = MagicMock()
        callback_calls = []
        result = processor._get_apple_transcript(
            mock_episode, progress_callback=lambda info: callback_calls.append(info)
        )
        assert result is None
        assert len(callback_calls) == 1
        assert "disabled" in callback_calls[0]["message"].lower()
