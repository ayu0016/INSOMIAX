from __future__ import annotations

from .models import CandidateProfile, ProfilePreviewResponse


def preview_profile(profile: CandidateProfile) -> ProfilePreviewResponse:
    missing: list[str] = []
    warnings: list[str] = []
    for field in ("name", "email"):
        if getattr(profile, field) is None:
            missing.append(field)
    for field, label in (("education", "education"), ("work_experience", "work experience or internships"), ("projects", "projects"), ("skills", "skills"), ("certifications", "certifications")):
        if not getattr(profile, field) and not (field == "work_experience" and profile.internships):
            missing.append(label)
    if profile.phone is None:
        warnings.append("Phone number was not provided; it is optional.")
    for field_name in ("name", "email", "phone"):
        field_value = getattr(profile, field_name)
        if field_value and field_value.source == "resume" and not field_value.evidence:
            warnings.append(f"{field_name} came from resume extraction but has no supporting excerpt.")
    for section in ("education", "work_experience", "internships", "projects", "certifications", "hackathons", "preferred_roles"):
        for index, entry in enumerate(getattr(profile, section)):
            if entry.source == "resume" and not entry.evidence:
                warnings.append(f"{section}[{index}] came from resume extraction but has no supporting excerpt.")
            if section in {"work_experience", "internships", "education"} and not entry.dates:
                warnings.append(f"{section}[{index}] has no identified date; no date was inferred.")
    for index, skill in enumerate(profile.skills):
        if skill.source == "resume" and not skill.evidence:
            warnings.append(f"skills[{index}] came from resume extraction but has no supporting excerpt.")
        if skill.evidence_kind == "inferred":
            warnings.append(f"skills[{index}] was mentioned in descriptive resume text; this does not establish proficiency.")
        if skill.proficiency_level is None:
            warnings.append(f"skills[{index}] proficiency is unknown.")
    return ProfilePreviewResponse(profile=profile, missing_fields=missing, warnings=warnings)
