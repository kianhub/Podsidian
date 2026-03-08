"""Parser for Apple Podcasts TTML transcript format.

Parses TTML XML files into plain text with speaker labels and timestamped segments.
Returns None on any error — never raises exceptions to callers.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

logger = logging.getLogger(__name__)

# TTML namespaces used by Apple Podcasts
NAMESPACES = {
    "tt": "http://www.w3.org/ns/ttml",
    "ttm": "http://www.w3.org/ns/ttml#metadata",
    "podcasts": "http://www.apple.com/2024/ttml-extensions",
}


def _parse_time(time_str: str) -> Optional[float]:
    """Convert TTML time string to float seconds.

    Supports formats:
    - Plain seconds: "1.980"
    - HH:MM:SS.mmm or MM:SS.mmm: "2:14:23.660" or "14:23.660"
    """
    if not time_str:
        return None
    try:
        # Try plain float first (e.g. "1.980")
        return float(time_str)
    except ValueError:
        pass
    try:
        # Try time format: optional hours, minutes, seconds
        parts = time_str.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return float(h) * 3600 + float(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return float(m) * 60 + float(s)
    except (ValueError, IndexError):
        pass
    return None


def _get_text_content(element: ET.Element) -> str:
    """Extract all text content from an element and its children."""
    return "".join(element.itertext()).strip()


def parse_ttml(xml_content: str) -> Optional[dict]:
    """Parse Apple Podcasts TTML XML into structured transcript data.

    Args:
        xml_content: Raw XML string of TTML transcript.

    Returns:
        Dict with keys:
        - "text": Full transcript as plain text with speaker labels like "[Speaker 1]: ..."
        - "segments": List of dicts with "speaker", "text", "start", "end"
        Returns None on any error or if transcript is empty.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        logger.warning("Failed to parse TTML XML")
        return None
    except Exception:
        logger.warning("Unexpected error parsing TTML XML")
        return None

    try:
        # Find <body> then <div> containing <p> elements
        body = root.find("tt:body", NAMESPACES)
        if body is None:
            # Try without namespace
            body = root.find("body")
        if body is None:
            # Try searching all descendants
            body = root

        # Collect all <p> elements (speaker turns)
        p_elements = body.findall(".//tt:p", NAMESPACES)
        if not p_elements:
            p_elements = body.findall(".//{http://www.w3.org/ns/ttml}p")
        if not p_elements:
            p_elements = body.findall(".//p")

        if not p_elements:
            logger.warning("No <p> elements found in TTML")
            return None

        segments = []
        text_parts = []
        current_speaker = None

        for p in p_elements:
            # Extract speaker from ttm:agent attribute
            speaker = p.get(f"{{{NAMESPACES['ttm']}}}agent", "")
            if not speaker:
                speaker = p.get("ttm:agent", "")

            # Format speaker label for display
            speaker_label = _format_speaker(speaker)

            # Extract sentence spans
            sentence_spans = p.findall(
                ".//tt:span[@podcasts:unit='sentence']",
                {**NAMESPACES, "podcasts": NAMESPACES["podcasts"]},
            )

            # If no sentence spans found, try alternative XPath approaches
            if not sentence_spans:
                sentence_spans = []
                for span in p.findall(".//{http://www.w3.org/ns/ttml}span"):
                    unit = span.get(f"{{{NAMESPACES['podcasts']}}}unit", "")
                    if unit == "sentence":
                        sentence_spans.append(span)

            # If still no sentence spans, treat the whole <p> as one segment
            if not sentence_spans:
                text = _get_text_content(p)
                if text:
                    begin = _parse_time(p.get("begin", ""))
                    end = _parse_time(p.get("end", ""))
                    segments.append({
                        "speaker": speaker_label,
                        "text": text,
                        "start": begin if begin is not None else 0.0,
                        "end": end if end is not None else 0.0,
                    })
                    if speaker_label != current_speaker:
                        current_speaker = speaker_label
                        text_parts.append(f"\n[{speaker_label}]: {text}")
                    else:
                        text_parts.append(f" {text}")
                continue

            for sentence_span in sentence_spans:
                # Get text from word spans within the sentence
                word_spans = []
                for span in sentence_span.findall(".//{http://www.w3.org/ns/ttml}span"):
                    unit = span.get(f"{{{NAMESPACES['podcasts']}}}unit", "")
                    if unit == "word":
                        word_spans.append(span)

                if word_spans:
                    sentence_text = " ".join(
                        _get_text_content(w) for w in word_spans if _get_text_content(w)
                    )
                    # Get timestamps from first/last word spans
                    begin = _parse_time(word_spans[0].get("begin", ""))
                    end = _parse_time(word_spans[-1].get("end", ""))
                else:
                    sentence_text = _get_text_content(sentence_span)
                    begin = _parse_time(sentence_span.get("begin", ""))
                    end = _parse_time(sentence_span.get("end", ""))

                if not sentence_text:
                    continue

                segments.append({
                    "speaker": speaker_label,
                    "text": sentence_text,
                    "start": begin if begin is not None else 0.0,
                    "end": end if end is not None else 0.0,
                })

                if speaker_label != current_speaker:
                    current_speaker = speaker_label
                    text_parts.append(f"\n[{speaker_label}]: {sentence_text}")
                else:
                    text_parts.append(f" {sentence_text}")

        if not segments:
            logger.warning("No transcript segments extracted from TTML")
            return None

        full_text = "".join(text_parts).strip()
        if not full_text or not full_text.strip():
            return None

        return {"text": full_text, "segments": segments}

    except Exception as e:
        logger.warning("Error processing TTML content: %s", e)
        return None


def _format_speaker(raw_speaker: str) -> str:
    """Format a raw speaker identifier into a display label.

    Converts "SPEAKER_0" → "Speaker 1", "SPEAKER_1" → "Speaker 2", etc.
    Passes through other formats as-is.
    """
    if not raw_speaker:
        return "Unknown"

    match = re.match(r"SPEAKER_(\d+)", raw_speaker)
    if match:
        num = int(match.group(1)) + 1
        return f"Speaker {num}"

    return raw_speaker
