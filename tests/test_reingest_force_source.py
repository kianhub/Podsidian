"""Tests for reingest_episode force_source parameter."""

from unittest.mock import patch, MagicMock
import pytest

from podsidian.core import PodcastProcessor


def _make_processor(session):
    """Create a PodcastProcessor with mocked config."""
    mock_config = MagicMock()
    mock_config.apple_transcripts_enabled = True
    mock_config.apple_transcripts_prefer_over_rss = False
    mock_config.apple_transcripts_include_speaker_labels = True

    with patch("podsidian.config.config", mock_config):
        processor = PodcastProcessor(session)
    processor.config = mock_config
    return processor


def _make_episode():
    """Create a mock episode."""
    ep = MagicMock()
    ep.id = 1
    ep.title = "Test Episode"
    ep.audio_url = "http://example.com/ep.mp3"
    ep.transcript_url = "http://example.com/transcript.vtt"
    ep.transcript = None
    ep.transcript_source = None
    ep.vector_embedding = None
    ep.processed_at = None
    ep.guid = "test-guid"
    return ep


class TestReingestForceSource:
    """Test force_source parameter in reingest_episode."""

    def test_invalid_force_source_raises(self):
        """Test that invalid force_source values raise ValueError."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with pytest.raises(ValueError, match="Invalid force_source"):
            processor.reingest_episode(1, force_source="invalid")

    @patch("os.unlink")
    def test_force_apple_success(self, mock_unlink):
        """Test force_source='apple' uses Apple transcript when available."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_get_apple_transcript", return_value="Apple transcript text") as mock_apple, \
             patch.object(processor, "_generate_embedding", return_value=MagicMock(tolist=lambda: [0.1])), \
             patch.object(processor, "_write_to_obsidian"), \
             patch.object(processor, "_init_annoy_index"):
            processor.reingest_episode(1, force_source="apple")

        assert episode.transcript == "Apple transcript text"
        assert episode.transcript_source == "apple"
        mock_apple.assert_called_once()

    @patch("os.unlink")
    def test_force_apple_unavailable_raises(self, mock_unlink):
        """Test force_source='apple' raises ValueError when unavailable."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_get_apple_transcript", return_value=None):
            with pytest.raises(Exception, match="Apple transcript not available"):
                processor.reingest_episode(1, force_source="apple")

    @patch("os.unlink")
    def test_force_external_success(self, mock_unlink):
        """Test force_source='external' uses external transcript."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_download_transcript", return_value="External text"), \
             patch.object(processor, "_generate_embedding", return_value=MagicMock(tolist=lambda: [0.1])), \
             patch.object(processor, "_write_to_obsidian"), \
             patch.object(processor, "_init_annoy_index"):
            processor.reingest_episode(1, force_source="external")

        assert episode.transcript == "External text"
        assert episode.transcript_source == "external"

    @patch("os.unlink")
    def test_force_external_no_url_raises(self, mock_unlink):
        """Test force_source='external' raises when no transcript URL."""
        session = MagicMock()
        episode = _make_episode()
        episode.transcript_url = None
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"):
            with pytest.raises(Exception, match="No external transcript URL"):
                processor.reingest_episode(1, force_source="external")

    @patch("os.unlink")
    def test_force_whisper(self, mock_unlink):
        """Test force_source='whisper' uses Whisper transcription."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_transcribe_audio", return_value="Whisper text") as mock_whisper, \
             patch.object(processor, "_generate_embedding", return_value=MagicMock(tolist=lambda: [0.1])), \
             patch.object(processor, "_write_to_obsidian"), \
             patch.object(processor, "_init_annoy_index"):
            processor.reingest_episode(1, force_source="whisper")

        assert episode.transcript == "Whisper text"
        assert episode.transcript_source == "whisper"
        mock_whisper.assert_called_once()

    @patch("os.unlink")
    def test_no_force_source_uses_priority_chain(self, mock_unlink):
        """Test that without force_source, normal priority chain is used (falls to whisper)."""
        session = MagicMock()
        episode = _make_episode()
        episode.transcript_url = None
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_get_apple_transcript", return_value=None), \
             patch.object(processor, "_transcribe_audio", return_value="Whisper fallback"), \
             patch.object(processor, "_generate_embedding", return_value=MagicMock(tolist=lambda: [0.1])), \
             patch.object(processor, "_write_to_obsidian"), \
             patch.object(processor, "_init_annoy_index"):
            processor.reingest_episode(1)

        assert episode.transcript == "Whisper fallback"
        assert episode.transcript_source == "whisper"

    @patch("os.unlink")
    def test_force_apple_skips_external_and_whisper(self, mock_unlink):
        """Test that force_source='apple' does not try external or whisper."""
        session = MagicMock()
        episode = _make_episode()
        session.query.return_value.filter.return_value.first.return_value = episode

        processor = _make_processor(session)

        mock_dl = MagicMock()
        mock_whisper = MagicMock()

        with patch.object(processor, "_download_audio", return_value="/tmp/audio.mp3"), \
             patch.object(processor, "_get_apple_transcript", return_value="Apple text"), \
             patch.object(processor, "_download_transcript", mock_dl), \
             patch.object(processor, "_transcribe_audio", mock_whisper), \
             patch.object(processor, "_generate_embedding", return_value=MagicMock(tolist=lambda: [0.1])), \
             patch.object(processor, "_write_to_obsidian"), \
             patch.object(processor, "_init_annoy_index"):
            processor.reingest_episode(1, force_source="apple")
            mock_dl.assert_not_called()
            mock_whisper.assert_not_called()


class TestReingestCLIForceSource:
    """Test that CLI apple-transcripts --apply passes force_source."""

    @patch("podsidian.cli.get_db_session")
    def test_apply_passes_force_source_apple(self, mock_get_db):
        from click.testing import CliRunner
        from podsidian.cli import cli
        from datetime import datetime

        runner = CliRunner()
        session = MagicMock()
        mock_get_db.return_value = session

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (100,)

        mock_podcast = MagicMock()
        mock_podcast.title = "Test Podcast"

        mock_ep = MagicMock()
        mock_ep.id = 42
        mock_ep.guid = "guid42"
        mock_ep.title = "Switchable Episode"
        mock_ep.audio_url = "http://example.com/42.mp3"
        mock_ep.transcript_source = "whisper"
        mock_ep.published_at = datetime(2026, 1, 1)
        mock_ep.podcast = mock_podcast

        session.query.return_value.join.return_value.all.return_value = [mock_ep]

        def mock_find_episode(guid=None, title=None, audio_url=None):
            return {"z_pk": 42, "title": "Switchable Episode", "guid": "guid42",
                    "transcript_id": "tx42", "store_track_id": 789}

        mock_processor = MagicMock()

        with patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value="/tmp/apple.db"), \
             patch("sqlite3.connect", return_value=mock_conn), \
             patch("podsidian.apple_podcasts.find_episode_in_apple_db", side_effect=mock_find_episode), \
             patch("podsidian.core.PodcastProcessor", return_value=mock_processor):
            result = runner.invoke(cli, ["apple-transcripts", "--apply"])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_processor.reingest_episode.call_args[1]
        assert call_kwargs.get("force_source") == "apple"
