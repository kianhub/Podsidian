"""Tests for Apple transcript CLI commands and display features."""

from unittest.mock import patch, MagicMock
from click.testing import CliRunner
import pytest

from podsidian.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestShowConfigAppleTranscripts:
    """Test that show-config displays Apple transcript status."""

    @patch("podsidian.cli.get_db_session")
    @patch("podsidian.cli.config")
    def test_show_config_includes_apple_transcripts_section(self, mock_config, mock_get_db, runner):
        mock_config.config_path = "/tmp/config.toml"
        mock_config.apple_transcripts_enabled = True
        mock_config.apple_transcripts_prefer_over_rss = False
        mock_config.apple_transcripts_include_speaker_labels = True
        mock_config.vault_path = "/tmp/vault"
        mock_config.note_template = "<template>"
        mock_config.whisper_model = "large-v3"
        mock_config.whisper_language = None
        mock_config.whisper_cpu_only = False
        mock_config.whisper_threads = 4
        mock_config.openrouter_api_key = "sk-test1234"
        mock_config.openrouter_model = "openai/gpt-4"
        mock_config.openrouter_processing_model = "openai/gpt-4"
        mock_config.topic_sample_size = 4000
        mock_config.transcript_correction_enabled = False
        mock_config.transcript_correction_chunk_size = 8000
        mock_config.cost_tracking_enabled = True
        mock_config.openrouter_prompt = "prompt"
        mock_config.value_prompt_enabled = False
        mock_config.value_prompt = "value prompt"
        mock_config.annoy_index_path = "/tmp/annoy.idx"

        session = MagicMock()
        mock_get_db.return_value = session
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.filter_by.return_value.count.return_value = 3

        mock_ttml_dir = MagicMock()
        mock_ttml_dir.exists.return_value = False

        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value=None), \
             patch("podsidian.apple_podcasts.TTML_CACHE_DIR", mock_ttml_dir):
            result = runner.invoke(cli, ["show-config"])

        assert result.exit_code == 0, result.output
        assert "Apple Transcripts" in result.output
        assert "enabled" in result.output
        assert "prefer_over_rss" in result.output
        assert "include_speaker_labels" in result.output

    @patch("podsidian.cli.get_db_session")
    @patch("podsidian.cli.config")
    def test_show_config_apple_db_found(self, mock_config, mock_get_db, runner):
        mock_config.config_path = "/tmp/config.toml"
        mock_config.apple_transcripts_enabled = True
        mock_config.apple_transcripts_prefer_over_rss = False
        mock_config.apple_transcripts_include_speaker_labels = True
        mock_config.vault_path = "/tmp/vault"
        mock_config.note_template = "<template>"
        mock_config.whisper_model = "large-v3"
        mock_config.whisper_language = None
        mock_config.whisper_cpu_only = False
        mock_config.whisper_threads = 4
        mock_config.openrouter_api_key = "sk-test1234"
        mock_config.openrouter_model = "openai/gpt-4"
        mock_config.openrouter_processing_model = "openai/gpt-4"
        mock_config.topic_sample_size = 4000
        mock_config.transcript_correction_enabled = False
        mock_config.transcript_correction_chunk_size = 8000
        mock_config.cost_tracking_enabled = True
        mock_config.openrouter_prompt = "prompt"
        mock_config.value_prompt_enabled = False
        mock_config.value_prompt = "value prompt"
        mock_config.annoy_index_path = "/tmp/annoy.idx"

        session = MagicMock()
        mock_get_db.return_value = session
        session.query.return_value.count.return_value = 10
        session.query.return_value.filter.return_value.count.return_value = 5
        session.query.return_value.filter_by.return_value.count.return_value = 3

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (42,)

        mock_ttml_dir = MagicMock()
        mock_ttml_dir.exists.return_value = True
        mock_ttml_dir.glob.return_value = ["a.ttml", "b.ttml", "c.ttml"]

        with patch("os.path.exists", return_value=True), \
             patch("os.path.getsize", return_value=1024), \
             patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value="/tmp/apple.db"), \
             patch("sqlite3.connect", return_value=mock_conn), \
             patch("podsidian.apple_podcasts.TTML_CACHE_DIR", mock_ttml_dir):
            result = runner.invoke(cli, ["show-config"])

        assert result.exit_code == 0, result.output
        assert "Found" in result.output
        assert "42" in result.output
        assert "3" in result.output


class TestEpisodesTranscriptSource:
    """Test that episodes command shows transcript_source."""

    @patch("podsidian.cli.get_db_session")
    def test_episodes_shows_transcript_source(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        from datetime import datetime

        mock_podcast = MagicMock()
        mock_podcast.title = "Test Podcast"

        mock_ep1 = MagicMock()
        mock_ep1.id = 1
        mock_ep1.title = "Episode 1"
        mock_ep1.published_at = datetime(2026, 1, 1)
        mock_ep1.transcript = "Some transcript"
        mock_ep1.transcript_source = "apple"
        mock_ep1.rating = None
        mock_ep1.quality_score = None
        mock_ep1.labels = None
        mock_ep1.podcast = mock_podcast

        mock_ep2 = MagicMock()
        mock_ep2.id = 2
        mock_ep2.title = "Episode 2"
        mock_ep2.published_at = datetime(2026, 1, 2)
        mock_ep2.transcript = "Some transcript"
        mock_ep2.transcript_source = "whisper"
        mock_ep2.rating = None
        mock_ep2.quality_score = None
        mock_ep2.labels = None
        mock_ep2.podcast = mock_podcast

        mock_ep3 = MagicMock()
        mock_ep3.id = 3
        mock_ep3.title = "Episode 3"
        mock_ep3.published_at = datetime(2026, 1, 3)
        mock_ep3.transcript = "Some transcript"
        mock_ep3.transcript_source = "external"
        mock_ep3.rating = None
        mock_ep3.quality_score = None
        mock_ep3.labels = None
        mock_ep3.podcast = mock_podcast

        query_mock = MagicMock()
        session.query.return_value.join.return_value = query_mock
        query_mock.order_by.return_value.all.return_value = [mock_ep1, mock_ep2, mock_ep3]

        result = runner.invoke(cli, ["episodes"])

        assert result.exit_code == 0
        assert "[apple]" in result.output
        assert "[whisper]" in result.output
        assert "[external]" in result.output

    @patch("podsidian.cli.get_db_session")
    def test_episodes_no_source_no_tag(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        from datetime import datetime

        mock_podcast = MagicMock()
        mock_podcast.title = "Test Podcast"

        mock_ep = MagicMock()
        mock_ep.id = 1
        mock_ep.title = "Episode 1"
        mock_ep.published_at = datetime(2026, 1, 1)
        mock_ep.transcript = "Some transcript"
        mock_ep.transcript_source = None
        mock_ep.rating = None
        mock_ep.quality_score = None
        mock_ep.labels = None
        mock_ep.podcast = mock_podcast

        query_mock = MagicMock()
        session.query.return_value.join.return_value = query_mock
        query_mock.order_by.return_value.all.return_value = [mock_ep]

        result = runner.invoke(cli, ["episodes"])

        assert result.exit_code == 0
        assert "[apple]" not in result.output
        assert "[whisper]" not in result.output


class TestAppleTranscriptsCommand:
    """Test the apple-transcripts CLI command."""

    @patch("podsidian.cli.get_db_session")
    def test_no_apple_db(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        with patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value=None):
            result = runner.invoke(cli, ["apple-transcripts"])

        assert result.exit_code == 0
        assert "not found" in result.output.lower()

    @patch("podsidian.cli.get_db_session")
    def test_shows_stats(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (100,)

        from datetime import datetime

        mock_podcast = MagicMock()
        mock_podcast.title = "Test Podcast"

        mock_ep1 = MagicMock()
        mock_ep1.id = 1
        mock_ep1.guid = "guid1"
        mock_ep1.title = "Episode 1"
        mock_ep1.audio_url = "http://example.com/1.mp3"
        mock_ep1.transcript_source = "whisper"
        mock_ep1.published_at = datetime(2026, 1, 1)
        mock_ep1.podcast = mock_podcast

        mock_ep2 = MagicMock()
        mock_ep2.id = 2
        mock_ep2.guid = "guid2"
        mock_ep2.title = "Episode 2"
        mock_ep2.audio_url = "http://example.com/2.mp3"
        mock_ep2.transcript_source = "apple"
        mock_ep2.published_at = datetime(2026, 1, 2)
        mock_ep2.podcast = mock_podcast

        session.query.return_value.join.return_value.all.return_value = [mock_ep1, mock_ep2]

        def mock_find_episode(guid=None, title=None, audio_url=None):
            if guid == "guid1":
                return {"z_pk": 1, "title": "Episode 1", "guid": "guid1",
                        "transcript_id": "tx1", "store_track_id": 123}
            if guid == "guid2":
                return {"z_pk": 2, "title": "Episode 2", "guid": "guid2",
                        "transcript_id": "tx2", "store_track_id": 456}
            return None

        with patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value="/tmp/apple.db"), \
             patch("sqlite3.connect", return_value=mock_conn), \
             patch("podsidian.apple_podcasts.find_episode_in_apple_db", side_effect=mock_find_episode):
            result = runner.invoke(cli, ["apple-transcripts"])

        assert result.exit_code == 0, result.output
        assert "100" in result.output
        assert "2" in result.output
        assert "1" in result.output
        assert "Episode 1" in result.output
        assert "--apply" in result.output

    @patch("podsidian.cli.get_db_session")
    def test_no_switchable(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (50,)

        session.query.return_value.join.return_value.all.return_value = []

        with patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value="/tmp/apple.db"), \
             patch("sqlite3.connect", return_value=mock_conn):
            result = runner.invoke(cli, ["apple-transcripts"])

        assert result.exit_code == 0
        assert "0" in result.output

    @patch("podsidian.cli.get_db_session")
    def test_apply_no_episodes(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (0,)

        session.query.return_value.join.return_value.all.return_value = []

        with patch("podsidian.apple_podcasts.find_apple_podcast_db", return_value="/tmp/apple.db"), \
             patch("sqlite3.connect", return_value=mock_conn):
            result = runner.invoke(cli, ["apple-transcripts", "--apply"])

        assert result.exit_code == 0
        assert "No episodes to switch" in result.output

    @patch("podsidian.cli.get_db_session")
    def test_apply_reingests_episodes(self, mock_get_db, runner):
        session = MagicMock()
        mock_get_db.return_value = session

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (100,)

        from datetime import datetime

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
        mock_processor.reingest_episode.assert_called_once()
        call_args = mock_processor.reingest_episode.call_args
        assert call_args[0][0] == 42
        assert "Switched: 1" in result.output
