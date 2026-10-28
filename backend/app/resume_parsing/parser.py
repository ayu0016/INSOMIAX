from __future__ import annotations

import os
import re

from ..jd_analytics.analyzer import _vocabulary
from .models import ContactField, ResumeDate, ResumeEntry, ResumeParseResult, ResumeSkill

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d ().-]{7,}\d)(?!\w)")
DATE_RE = re.compile(r"\b(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+)?(?:19|20)\d{2}(?:\s*(?:-|\u2013|\u2014|to)\s*(?:Present|Current|(?:19|20)\d{2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}))?\b", re.I)
DURATION_RE = re.compile(r"\b\d+(?:\.\d+)?\+?\s+(?:years?|months?)\b", re.I)
SECTION_ALIASES = {
    "education": "education", "academic background": "education", "qualifications": "education", "education and qualifications": "education", "academic qualifications": "education",
    "experience": "experience", "work experience": "experience", "professional experience": "experience", "professional work experience": "experience", "employment history": "experience",
    "internship": "internship", "internships": "internship", "internship experience": "internship",
    "projects": "projects", "personal projects": "projects", "academic projects": "projects",
    "skills": "skills", "technical skills": "skills", "core skills": "skills", "technical expertise": "skills",
    "certifications": "certifications", "certificates": "certifications", "licenses and certifications": "certifications",
    "summary": "other", "professional summary": "other", "objective": "other", "profile": "other",
    "awards": "other", "awards and honors": "other", "achievements": "other", "publications": "other",
    "languages": "other", "volunteer experience": "other", "extracurricular activities": "other", "interests": "other",
    "hackathons": "other", "leadership": "other",
}
EXPLICIT_NAME = re.compile(r"^\s*(?:name|candidate)\s*:\s*(.{2,100})\s*$", re.I)
ROLE_WORDS = {"engineer", "developer", "designer", "analyst", "manager", "consultant", "intern", "scientist", "architect", "lead", "director", "resume", "curriculum", "vitae"}


def _lines(text: str) -> list[str]:
    return [re.sub(r"^[\s\u2022\u25aa\u25e6*\-]+", "", line).strip() for line in text.splitlines() if line.strip()]


def _section_for(line: str) -> str | None:
    candidate = line.strip(" :#*-\t").casefold()
    if candidate in SECTION_ALIASES:
        return SECTION_ALIASES[candidate]
    if ":" in line:
        return SECTION_ALIASES.get(line.split(":", 1)[0].strip(" :#*-\t").casefold())
    return None


def _entry(line: str, section: str) -> ResumeEntry:
    date = DATE_RE.search(line)
    duration = DURATION_RE.search(line)
    return ResumeEntry(text=line, evidence=line, source_section=section, dates=date.group() if date else None, duration=duration.group() if duration else None)


def _extract_skills(lines: list[str], sections: list[str], vocabulary_path: str | None) -> list[ResumeSkill]:
    vocabulary = _vocabulary(vocabulary_path or os.getenv("RADIX_JD_SKILL_VOCAB_PATH"))
    found: dict[tuple[str, str], ResumeSkill] = {}
    patterns = [(item, re.compile(r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])", re.I)) for item in vocabulary for term in [item["name"], *item["aliases"]]]
    explicit_sections = {"skills"}
    descriptive_sections = {"experience", "internship", "projects"}
    for line, section in zip(lines, sections):
        for item, pattern in patterns:
            match = pattern.search(line)
            if match is None:
                continue
            kind = "explicit" if section in explicit_sections else "inferred" if section in descriptive_sections else None
            if kind is None:
                continue
            key = (item["name"].casefold(), line)
            found[key] = ResumeSkill(skill_name=match.group(), canonical_skill=item["name"], category_code=item["category_code"], evidence=line, confidence="high", source_section=section, evidence_kind=kind)
    return list(found.values())


def parse_resume(text: str, source_file: str | None = None, vocabulary_path: str | None = None) -> ResumeParseResult:
    lines = _lines(text)
    sections: list[str] = []
    active = "header"
    name_candidates: list[ContactField] = []
    email_candidates: list[ContactField] = []
    phone_candidates: list[ContactField] = []
    for line in lines:
        explicit = EXPLICIT_NAME.match(line)
        if explicit:
            name_candidates.append(ContactField(value=explicit.group(1).strip(), evidence=line))
        if match := EMAIL_RE.search(line):
            email_candidates.append(ContactField(value=match.group(), evidence=line))
        if (match := PHONE_RE.search(line)) and not DATE_RE.fullmatch(match.group().strip()):
            phone_candidates.append(ContactField(value=match.group().strip(), evidence=line))
        section = _section_for(line)
        if section:
            active = section
        sections.append(active)

    # Many resumes place the person's name as the first line without a label. Only accept a simple name-shaped header.
    ambiguous: list[str] = []

    def select_contact(field: str, candidates: list[ContactField]) -> ContactField | None:
        unique = {candidate.value.casefold(): candidate for candidate in candidates}
        if len(unique) > 1:
            ambiguous.append(field)
            return None
        return next(iter(unique.values()), None)

    candidate_name = select_contact("candidate_name", name_candidates)
    email = select_contact("email", email_candidates)
    phone = select_contact("phone", phone_candidates)

    if candidate_name is None and not name_candidates and lines:
        first = lines[0]
        words = first.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Z][A-Za-z'.-]+", word) for word in words) and not any(word.casefold() in ROLE_WORDS for word in words) and not EMAIL_RE.search(first):
            candidate_name = ContactField(value=first, evidence=first)

    buckets: dict[str, list[ResumeEntry]] = {key: [] for key in ("education", "experience", "internship", "projects", "certifications")}
    dates: list[ResumeDate] = []
    for line, section in zip(lines, sections):
        if match := DATE_RE.search(line):
            dates.append(ResumeDate(value=match.group(), evidence=line, source_section=section))
        if section in buckets:
            # Ignore a heading itself if it was recognized as a heading.
            if _section_for(line) is None:
                buckets[section].append(_entry(line, section))
    skills = _extract_skills(lines, sections, vocabulary_path)
    missing = []
    if candidate_name is None and "candidate_name" not in ambiguous:
        missing.append("candidate_name")
    if email is None and "email" not in ambiguous:
        missing.append("email")
    if phone is None and "phone" not in ambiguous:
        missing.append("phone")
    if not buckets["education"]:
        missing.append("education")
    if not buckets["experience"] and not buckets["internship"]:
        missing.append("work_experience_or_internships")
    if not buckets["projects"]:
        missing.append("projects")
    if not skills:
        missing.append("skills")
    if not buckets["certifications"]:
        missing.append("certifications")
    missing.extend(f"{field} (multiple matches)" for field in ambiguous)
    return ResumeParseResult(source_file=source_file, candidate_name=candidate_name, email=email, phone=phone, education=buckets["education"], work_experience=buckets["experience"], internships=buckets["internship"], projects=buckets["projects"], skills=skills, certifications=buckets["certifications"], dates=dates, missing_or_ambiguous=missing)
