from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from ..config import PROJECT_ROOT
from ..errors import RadixError
from .models import EvidenceText, JDAnalysisResult, SkillEvidence, valid_category_codes

DEFAULT_VOCABULARY = Path(__file__).with_name("skill_vocabulary.json")
REQUIRED_MARKERS = re.compile(r"\b(required|required qualifications|must have|must|required to|minimum qualifications|mandatory)\b", re.I)
PREFERRED_MARKERS = re.compile(r"\b(preferred|preferred qualifications|nice to have|bonus|desirable|good to have|a plus)\b", re.I)
EXPERIENCE = re.compile(r"\b(?:\d+\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:relevant\s+)?experience|experience\s+(?:of\s+)?\d+\+?\s*(?:years?|yrs?))\b", re.I)
EDUCATION = re.compile(r"\b(bachelor'?s|master'?s|ph\.?d\.?|degree|diploma|graduate|undergraduate|education)\b", re.I)


def _vocabulary(path: str | None = None) -> list[dict[str, str]]:
    source = Path(path) if path else DEFAULT_VOCABULARY
    if not source.is_absolute():
        source = PROJECT_ROOT / source
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
        skills = data["skills"]
        if not isinstance(skills, list):
            raise ValueError
        valid = valid_category_codes()
        result = []
        canonical_names = set()
        configured_terms: dict[str, str] = {}
        for item in skills:
            name, category = item["name"].strip(), item["category_code"]
            aliases = item.get("aliases", [])
            if not name or category not in valid or name.casefold() in canonical_names or not isinstance(aliases, list) or any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
                raise ValueError
            canonical_names.add(name.casefold())
            for term in [name, *aliases]:
                normalized = normalize_skill_name(term)
                previous = configured_terms.get(normalized)
                if not normalized or (previous is not None and previous.casefold() != name.casefold()):
                    raise ValueError
                configured_terms[normalized] = name
            result.append({"name": name, "category_code": category, "aliases": aliases})
        return result
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise RadixError(500, "INVALID_SKILL_VOCABULARY", "The configured JD skill vocabulary is missing or invalid.") from None


def normalize_skill_name(value: str) -> str:
    """Deterministic text normalization only; no implicit alias resolution."""
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"[^\w+#.]", " ", value, flags=re.UNICODE)
    return " ".join(value.split())


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _requirement_type(sentence: str, section: str) -> str:
    if PREFERRED_MARKERS.search(sentence) or section in {"preferred qualifications", "nice to have", "desired qualifications"}:
        return "preferred"
    if REQUIRED_MARKERS.search(sentence) or section in {"required qualifications", "requirements", "minimum qualifications"}:
        return "required"
    return "unspecified"


def _skills(sentences: list[str], vocabulary: list[dict[str, str]]) -> list[SkillEvidence]:
    found: dict[tuple[str, str, str], SkillEvidence] = {}
    section = ""
    patterns = [(item, term, re.compile(r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])", re.I)) for item in vocabulary for term in [item["name"], *item["aliases"]]]
    for sentence in sentences:
        header = sentence.strip(" :-#*").casefold()
        if len(header) <= 80 and re.fullmatch(r"[a-z][a-z /&-]*", header):
            section = header
        classification = _requirement_type(sentence, section)
        for item, term, pattern in patterns:
            match = pattern.search(sentence)
            if match:
                key = (item["name"].casefold(), classification, sentence)
                found[key] = SkillEvidence(skill_name=match.group(), canonical_skill=item["name"], category_code=item["category_code"], requirement_type=classification, evidence=sentence[:1000], confidence="high")
    return list(found.values())


def analyze_job_description(text: str, vocabulary_path: str | None = None, source_file: str | None = None) -> JDAnalysisResult:
    sentences = _sentences(text)
    title: str | None = None
    title_evidence: str | None = None
    for line in text.splitlines():
        match = re.match(r"\s*(?:job\s+title|position|role)\s*:\s*([^.!?\r\n]{2,120})", line, re.I)
        if match:
            title = match.group(1).strip()
            title_evidence = line.strip()
            break
    all_skills = _skills(sentences, _vocabulary(vocabulary_path or os.getenv("RADIX_JD_SKILL_VOCAB_PATH")))
    required = [skill for skill in all_skills if skill.requirement_type == "required"]
    preferred = [skill for skill in all_skills if skill.requirement_type == "preferred"]
    unspecified = [skill for skill in all_skills if skill.requirement_type == "unspecified"]
    by_category = {code: [skill for skill in all_skills if skill.category_code == code] for code in sorted(valid_category_codes()) if any(skill.category_code == code for skill in all_skills)}
    experience = [EvidenceText(text=sentence, evidence=sentence) for sentence in sentences if EXPERIENCE.search(sentence)]
    education = [EvidenceText(text=sentence, evidence=sentence) for sentence in sentences if EDUCATION.search(sentence)]
    responsibilities: list[EvidenceText] = []
    qualifications: list[EvidenceText] = []
    section = ""
    for sentence in sentences:
        heading = sentence.strip(" :-#*").casefold()
        if len(heading) <= 80 and re.fullmatch(r"[a-z][a-z /&-]*", heading):
            section = heading
            continue
        evidence = EvidenceText(text=sentence, evidence=sentence)
        if section in {"responsibilities", "what you will do", "key responsibilities", "duties"}:
            responsibilities.append(evidence)
        elif section in {"qualifications", "requirements", "required qualifications", "preferred qualifications", "minimum qualifications", "skills"}:
            qualifications.append(evidence)
    return JDAnalysisResult(source_file=source_file, role=title, skills=all_skills, job_title=title, job_title_evidence=title_evidence, required_skills=required, preferred_skills=preferred, unclassified_requirement_skills=unspecified, skills_by_category=by_category, experience_requirements=experience, education_requirements=education, responsibilities=responsibilities, key_qualifications=qualifications)
