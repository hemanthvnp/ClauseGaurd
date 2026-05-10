from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.core.config import get_settings

settings = get_settings()


@dataclass(slots=True)
class Segment:
    text: str
    start: int
    end: int


class ClauseSegmenter:
    """Split legal text into clause-sized segments.

    Input: raw document text.
    Output: ordered clause segments with original offsets.
    """

    def __init__(self) -> None:
        self._nlp = self._load_nlp()

    def _load_nlp(self):
        try:
            import spacy

            try:
                return spacy.load(settings.spacy_model)
            except Exception:
                nlp = spacy.blank('en')
                if 'sentencizer' not in nlp.pipe_names:
                    nlp.add_pipe('sentencizer')
                return nlp
        except Exception:
            return None

    def segment(self, text: str) -> list[Segment]:
        """Return clause-like segments from the provided text."""
        if not text.strip():
            return []

        normalized = text.replace('\r\n', '\n')
        paragraphs = [paragraph.strip() for paragraph in re.split(r'\n{2,}', normalized) if paragraph.strip()]
        segments: list[Segment] = []
        cursor = 0
        for paragraph in paragraphs:
            paragraph_start = normalized.find(paragraph, cursor)
            if paragraph_start < 0:
                paragraph_start = cursor
            paragraph_end = paragraph_start + len(paragraph)
            cursor = paragraph_end
            sentence_segments = list(self._split_paragraph(paragraph, paragraph_start))
            segments.extend(sentence_segments or [Segment(text=paragraph, start=paragraph_start, end=paragraph_end)])
        return segments

    def _split_paragraph(self, paragraph: str, paragraph_start: int) -> Iterable[Segment]:
        if self._nlp is None:
            yield from self._heuristic_split(paragraph, paragraph_start)
            return

        doc = self._nlp(paragraph)
        for sentence in doc.sents:
            sentence_text = sentence.text.strip()
            if sentence_text:
                start = paragraph_start + sentence.start_char
                end = paragraph_start + sentence.end_char
                yield Segment(text=sentence_text, start=start, end=end)

    def _heuristic_split(self, paragraph: str, paragraph_start: int) -> Iterable[Segment]:
        clause_boundaries = re.split(r'(?<=[.;:])\s+(?=(?:\d+[.)]|[A-Z][a-z]+|You agree|Company reserves|The parties|Each party))', paragraph)
        offset = 0
        for clause in clause_boundaries:
            clause_text = clause.strip()
            if not clause_text:
                continue
            start = paragraph.find(clause_text, offset)
            if start < 0:
                start = offset
            end = start + len(clause_text)
            offset = end
            yield Segment(text=clause_text, start=paragraph_start + start, end=paragraph_start + end)
