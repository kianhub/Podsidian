"""Tests for the TTML parser module."""

import pytest
from podsidian.ttml_parser import parse_ttml, _parse_time, _format_speaker


# --- Time parsing tests ---


class TestParseTime:
    def test_plain_seconds(self):
        assert _parse_time("1.980") == 1.98

    def test_zero(self):
        assert _parse_time("0") == 0.0

    def test_mm_ss_format(self):
        assert _parse_time("14:23.660") == pytest.approx(863.66)

    def test_hh_mm_ss_format(self):
        assert _parse_time("2:14:23.660") == pytest.approx(8063.66)

    def test_empty_string(self):
        assert _parse_time("") is None

    def test_none(self):
        assert _parse_time(None) is None

    def test_invalid(self):
        assert _parse_time("not-a-time") is None


# --- Speaker formatting tests ---


class TestFormatSpeaker:
    def test_speaker_0(self):
        assert _format_speaker("SPEAKER_0") == "Speaker 1"

    def test_speaker_2(self):
        assert _format_speaker("SPEAKER_2") == "Speaker 3"

    def test_empty(self):
        assert _format_speaker("") == "Unknown"

    def test_custom_name(self):
        assert _format_speaker("John") == "John"


# --- TTML parsing tests ---

SAMPLE_TTML = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <head>
    <metadata>
      <ttm:agent xml:id="SPEAKER_0"/>
      <ttm:agent xml:id="SPEAKER_1"/>
    </metadata>
  </head>
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

SAMPLE_TTML_NO_SPEAKER = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <body>
    <div>
      <p>
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="0.500" end="0.900">Hello</span>
          <span podcasts:unit="word" begin="1.000" end="1.500">world.</span>
        </span>
      </p>
    </div>
  </body>
</tt>
"""

SAMPLE_TTML_MULTI_SENTENCE = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <body>
    <div>
      <p ttm:agent="SPEAKER_0">
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="0.500" end="0.900">First</span>
          <span podcasts:unit="word" begin="1.000" end="1.500">sentence.</span>
        </span>
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="2.000" end="2.500">Second</span>
          <span podcasts:unit="word" begin="2.600" end="3.000">sentence.</span>
        </span>
      </p>
    </div>
  </body>
</tt>
"""


class TestParseTtml:
    def test_basic_parsing(self):
        result = parse_ttml(SAMPLE_TTML)
        assert result is not None
        assert "text" in result
        assert "segments" in result

    def test_speaker_labels_in_text(self):
        result = parse_ttml(SAMPLE_TTML)
        assert "[Speaker 1]:" in result["text"]
        assert "[Speaker 2]:" in result["text"]

    def test_segments_structure(self):
        result = parse_ttml(SAMPLE_TTML)
        assert len(result["segments"]) == 2
        seg = result["segments"][0]
        assert seg["speaker"] == "Speaker 1"
        assert seg["text"] == "Hello world."
        assert seg["start"] == pytest.approx(0.5)
        assert seg["end"] == pytest.approx(1.5)

    def test_second_speaker(self):
        result = parse_ttml(SAMPLE_TTML)
        seg = result["segments"][1]
        assert seg["speaker"] == "Speaker 2"
        assert seg["text"] == "Hi there."
        assert seg["start"] == pytest.approx(2.0)
        assert seg["end"] == pytest.approx(2.8)

    def test_no_speaker(self):
        result = parse_ttml(SAMPLE_TTML_NO_SPEAKER)
        assert result is not None
        assert result["segments"][0]["speaker"] == "Unknown"

    def test_multi_sentence_same_speaker(self):
        result = parse_ttml(SAMPLE_TTML_MULTI_SENTENCE)
        assert result is not None
        assert len(result["segments"]) == 2
        # Both segments should be same speaker
        assert result["segments"][0]["speaker"] == "Speaker 1"
        assert result["segments"][1]["speaker"] == "Speaker 1"
        # Text should not repeat speaker label
        assert result["text"].count("[Speaker 1]:") == 1

    def test_malformed_xml(self):
        assert parse_ttml("<not valid xml") is None

    def test_empty_content(self):
        assert parse_ttml("") is None

    def test_valid_xml_no_p_elements(self):
        xml = '<?xml version="1.0"?><tt xmlns="http://www.w3.org/ns/ttml"><body></body></tt>'
        assert parse_ttml(xml) is None

    def test_returns_none_on_whitespace_only(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <body>
    <div>
      <p ttm:agent="SPEAKER_0">
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="0.500" end="0.900">   </span>
        </span>
      </p>
    </div>
  </body>
</tt>
"""
        # Word span contains only whitespace - should still produce a segment
        # but the text should not be empty
        result = parse_ttml(xml)
        # The whitespace-only word gets filtered by _get_text_content strip
        # so this should return None
        assert result is None


class TestParseTtmlTimestampFormats:
    """Test that both timestamp formats (seconds and MM:SS.mmm) work."""

    def test_seconds_format(self):
        result = parse_ttml(SAMPLE_TTML)
        assert result["segments"][0]["start"] == pytest.approx(0.5)

    def test_colon_format_in_timestamps(self):
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<tt xmlns="http://www.w3.org/ns/ttml"
    xmlns:ttm="http://www.w3.org/ns/ttml#metadata"
    xmlns:podcasts="http://www.apple.com/2024/ttml-extensions">
  <body>
    <div>
      <p ttm:agent="SPEAKER_0">
        <span podcasts:unit="sentence">
          <span podcasts:unit="word" begin="1:02:03.500" end="1:02:04.000">Test</span>
        </span>
      </p>
    </div>
  </body>
</tt>
"""
        result = parse_ttml(xml)
        assert result is not None
        assert result["segments"][0]["start"] == pytest.approx(3723.5)
        assert result["segments"][0]["end"] == pytest.approx(3724.0)
