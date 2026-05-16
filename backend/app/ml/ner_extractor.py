"""
Contract Named Entity Recognition (NER)
=========================================
Extracts structured entities from raw contract text:
  - Party names      (Company A, LLC / natural persons)
  - Effective date   (ISO date string)
  - Expiration date  (ISO date string)
  - Governing law    (jurisdiction string)
  - Contract type    (Employment / SaaS / NDA / etc.)
  - Monetary values  [(label, amount, currency)]
  - Notice periods   [(label, days)]
  - Defined terms    {term: definition}

Strategy:
  1. spaCy en_core_web_sm/trf for base NER (ORG, PERSON, DATE, MONEY)
  2. Regex patterns for legal-specific patterns (net-N payment, notice periods, etc.)
  3. Rule-based contract-type classifier
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MonetaryValue:
    label: str
    amount: float
    currency: str = "USD"


@dataclass
class NoticePeriod:
    label: str
    days: int


@dataclass
class ContractEntities:
    parties: list[str] = field(default_factory=list)
    effective_date: str | None = None
    expiration_date: str | None = None
    governing_law: str | None = None
    contract_type: str | None = None
    monetary_values: list[MonetaryValue] = field(default_factory=list)
    notice_periods: list[NoticePeriod] = field(default_factory=list)
    defined_terms: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parties": self.parties,
            "effective_date": self.effective_date,
            "expiration_date": self.expiration_date,
            "governing_law": self.governing_law,
            "contract_type": self.contract_type,
            "monetary_values": [v.__dict__ for v in self.monetary_values],
            "notice_periods": [n.__dict__ for n in self.notice_periods],
            "defined_terms": self.defined_terms,
        }


# ── spaCy loader ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _nlp() -> Any | None:
    for model_name in ("en_core_web_trf", "en_core_web_sm"):
        try:
            import spacy  # type: ignore[import]
            return spacy.load(model_name, exclude=["parser"])
        except Exception:
            continue
    print("[ner] spaCy model not available — using regex-only NER", file=sys.stderr)
    return None


# ── Regex patterns ────────────────────────────────────────────────────────────

_RE_PARTY_BETWEEN = re.compile(
    r"(?:between|by and between)\s+(.+?)\s+(?:and|,)\s+(.+?)(?:\.|,|\(|$)",
    re.IGNORECASE,
)
_RE_PARTY_HEREINAFTER = re.compile(
    r'"([A-Z][A-Za-z\s,\.]+?)"\s*(?:\(|hereinafter)',
    re.IGNORECASE,
)
_RE_EFFECTIVE = re.compile(
    r"(?:effective|commencement|start|begins?)\s+(?:date[:\s]+|as of\s+)?(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    re.IGNORECASE,
)
_RE_EXPIRATION = re.compile(
    r"(?:expir(?:es?|ation)|terminat(?:es?|ion)\s+date|end\s+date)\s*(?:is|shall be|:)?\s*(\w+\s+\d{1,2},?\s+\d{4}|\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
    re.IGNORECASE,
)
_RE_GOVERNING = re.compile(
    r"governed\s+by\s+(?:the\s+)?(?:laws?\s+of\s+(?:the\s+)?|laws?\s+and\s+regulations?\s+of\s+(?:the\s+)?)?([A-Z][A-Za-z\s]+?)(?:\.|,|$)",
    re.IGNORECASE,
)
_RE_MONEY = re.compile(
    r"(?P<currency>USD|EUR|GBP|INR|\$|€|£)?\s*(?P<amount>[\d,]+(?:\.\d{1,2})?)\s*(?P<currency2>USD|EUR|GBP|million|billion|k)?",
    re.IGNORECASE,
)
_RE_NOTICE = re.compile(
    r"(?P<label>[^\.\n]{0,60}?)\b(?P<days>\d+)\s*(?:calendar\s+|business\s+)?days?\s+(?:prior\s+)?notice",
    re.IGNORECASE,
)
_RE_DEFINED = re.compile(
    r'"([A-Z][A-Za-z\s]+?)"\s+(?:means|shall mean|refers? to)\s+([^\.]+\.)',
    re.IGNORECASE,
)

_CONTRACT_TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("Employment Agreement",      re.compile(r"\bemployment\s+agreement\b", re.I)),
    ("NDA / Confidentiality",     re.compile(r"\bnon[-\s]?disclosure\b|\bnda\b|\bconfidentiality\s+agreement\b", re.I)),
    ("SaaS / Software License",   re.compile(r"\bsoftware\s+(?:license|as\s+a\s+service)\b|\bsaas\b", re.I)),
    ("Master Services Agreement", re.compile(r"\bmaster\s+services\s+agreement\b|\bmsa\b", re.I)),
    ("Vendor / Supplier",         re.compile(r"\bvendor\s+agreement\b|\bsupplier\s+agreement\b|\bpurchase\s+order\b", re.I)),
    ("Lease Agreement",           re.compile(r"\blease\s+agreement\b|\btenancy\b|\blandlord\b", re.I)),
    ("Partnership Agreement",     re.compile(r"\bpartnership\s+agreement\b|\bjoint\s+venture\b", re.I)),
    ("Terms of Service",          re.compile(r"\bterms\s+of\s+(?:service|use)\b|\btos\b|\bterms\s+and\s+conditions\b", re.I)),
]


# ── Main extractor ────────────────────────────────────────────────────────────

class ContractNERExtractor:
    """
    Extract structured entities from raw contract text.

    Example:
        extractor = ContractNERExtractor()
        entities = extractor.extract(raw_text)
        print(entities.parties)          # ["Acme Corp", "John Doe"]
        print(entities.effective_date)   # "January 1, 2025"
        print(entities.contract_type)    # "Employment Agreement"
    """

    def extract(self, text: str) -> ContractEntities:
        ents = ContractEntities()
        ents.parties      = self._extract_parties(text)
        ents.effective_date  = self._extract_date(_RE_EFFECTIVE, text)
        ents.expiration_date = self._extract_date(_RE_EXPIRATION, text)
        ents.governing_law   = self._extract_governing_law(text)
        ents.contract_type   = self._extract_contract_type(text)
        ents.monetary_values = self._extract_monetary(text)
        ents.notice_periods  = self._extract_notices(text)
        ents.defined_terms   = self._extract_defined_terms(text)
        return ents

    # ── party extraction ───────────────────────────────────────────────────

    def _extract_parties(self, text: str) -> list[str]:
        parties: list[str] = []

        # Regex: "between X and Y"
        m = _RE_PARTY_BETWEEN.search(text[:2000])
        if m:
            parties += [g.strip().strip('"') for g in m.groups()]

        # Regex: defined in quotes e.g. "Acme Corp" (hereinafter "Company")
        for m in _RE_PARTY_HEREINAFTER.finditer(text[:3000]):
            name = m.group(1).strip()
            if 3 < len(name) < 80:
                parties.append(name)

        # spaCy ORG / PERSON entities
        nlp = _nlp()
        if nlp is not None:
            doc = nlp(text[:3000])
            for ent in doc.ents:
                if ent.label_ in ("ORG", "PERSON") and 3 < len(ent.text) < 80:
                    parties.append(ent.text.strip())

        # Deduplicate preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for p in parties:
            clean = re.sub(r"\s+", " ", p).strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                deduped.append(clean)
        return deduped[:6]  # cap to 6 most prominent

    def _extract_date(self, pattern: re.Pattern, text: str) -> str | None:
        m = pattern.search(text)
        if m:
            return m.group(1).strip()
        # spaCy DATE entities
        nlp = _nlp()
        if nlp is not None:
            doc = nlp(text[:3000])
            for ent in doc.ents:
                if ent.label_ == "DATE" and len(ent.text) > 5:
                    return ent.text.strip()
        return None

    def _extract_governing_law(self, text: str) -> str | None:
        m = _RE_GOVERNING.search(text)
        if m:
            return m.group(1).strip().rstrip(".,")
        lower = text.lower()
        for state in ("california", "new york", "delaware", "texas", "england",
                      "india", "singapore", "ireland", "germany"):
            if state in lower:
                return state.title()
        return None

    def _extract_contract_type(self, text: str) -> str | None:
        for label, pattern in _CONTRACT_TYPE_PATTERNS:
            if pattern.search(text[:2000]):
                return label
        return None

    def _extract_monetary(self, text: str) -> list[MonetaryValue]:
        values: list[MonetaryValue] = []
        # Find dollar amounts: $1,500, USD 50,000, €2,000
        pattern = re.compile(
            r"(?:USD|US\$|\$|EUR|€|GBP|£|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)\s*"
            r"(?:million|billion|thousand|k)?",
            re.IGNORECASE,
        )
        currency_map = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR",
                        "us$": "USD", "usd": "USD", "eur": "EUR", "gbp": "GBP", "inr": "INR"}
        for m in list(pattern.finditer(text))[:10]:
            prefix = m.group(0).split(m.group(1))[0].strip().lower()
            currency = currency_map.get(prefix, "USD")
            raw_amount = m.group(1).replace(",", "")
            try:
                amount = float(raw_amount)
                suffix_text = text[m.end():m.end()+10].lower()
                if "million" in suffix_text:
                    amount *= 1_000_000
                elif "billion" in suffix_text:
                    amount *= 1_000_000_000
                elif "thousand" in suffix_text or "k" in suffix_text:
                    amount *= 1_000
                values.append(MonetaryValue(label=m.group(0)[:30], amount=amount, currency=currency))
            except ValueError:
                pass
        return values

    def _extract_notices(self, text: str) -> list[NoticePeriod]:
        periods: list[NoticePeriod] = []
        for m in list(_RE_NOTICE.finditer(text))[:5]:
            try:
                days = int(m.group("days"))
                label = m.group("label").strip()[-50:]
                periods.append(NoticePeriod(label=label or "notice", days=days))
            except (ValueError, IndexError):
                pass
        return periods

    def _extract_defined_terms(self, text: str) -> dict[str, str]:
        terms: dict[str, str] = {}
        for m in list(_RE_DEFINED.finditer(text))[:20]:
            term = m.group(1).strip()
            defn = m.group(2).strip()
            if 2 < len(term) < 60:
                terms[term] = defn[:200]
        return terms


@lru_cache(maxsize=1)
def get_ner_extractor() -> ContractNERExtractor:
    return ContractNERExtractor()
