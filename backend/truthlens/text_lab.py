"""Lexical comparison of two pasted texts. Not a semantic verifier."""

from __future__ import annotations

import re

from backend.truthlens.observations import observation

_TOKEN = re.compile(r"[a-z0-9']+")
_URGENCY = (
    "urgent",
    "immediately",
    "wire",
    "transfer",
    "confidential",
    "verify",
    "suspend",
    "password",
    "now",
)


def tokens(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


def analyze_text(statement: str, comparison: str, sha256: str) -> dict:
    task = (
        "Simple lexical screening of pasted text. Token overlap is not semantic similarity "
        "and is not a claim-support verdict."
    )
    left = tokens(statement)
    right = tokens(comparison)
    left_set = set(left)
    right_set = set(right)
    shared = sorted(left_set & right_set)
    only_left = sorted(left_set - right_set)
    only_right = sorted(right_set - left_set)
    union = left_set | right_set
    jaccard = float(len(shared) / len(union)) if union else None
    urgency_hits = sorted({word for word in left + right if word in _URGENCY})
    both_present = bool(statement.strip() and comparison.strip())

    observations = []
    if both_present:
        if len(shared) <= 1:
            overlap_result = (
                f"{len(shared)} shared token(s). One shared token, or none, is not described as a match. "
                "Different wording is not described as a contradiction."
            )
        else:
            overlap_result = (
                f"{len(shared)} shared tokens and Jaccard {jaccard:.3f}. "
                "Shared tokens are a lexical observation only. They do not show that the statements mean the same thing."
            )
        observations.append(
            observation(
                name="Lexical token overlap",
                modality="text",
                source_sha256=sha256,
                location="both pasted texts",
                method="Lowercase alphanumeric tokens. Jaccard is the size of the intersection divided by the size of the union.",
                result=overlap_result,
                measured_value=None if jaccard is None else round(jaccard, 6),
                score_type="Jaccard overlap of surface tokens; not a semantic similarity and not a probability",
                threshold="No match threshold is applied.",
                threshold_exceeded=False,
                alternative_explanations=[
                    "Paraphrases can share few tokens and still discuss one topic.",
                    "Unrelated sentences can share function words or a single repeated word.",
                ],
                limitation="No semantic verifier is installed. This screen cannot support or refute a claim.",
                detector_id="lexical_token_overlap",
            )
        )
    if urgency_hits:
        observations.append(
            observation(
                name="Lexical urgency list",
                modality="text",
                source_sha256=sha256,
                location="either pasted text",
                method="Exact token lookup against a fixed list: " + ", ".join(_URGENCY) + ".",
                result="Tokens from the list were present: " + ", ".join(urgency_hits) + ".",
                measured_value=len(urgency_hits),
                score_type="count of listed tokens; not an intent score",
                threshold="No threshold. Listed tokens are shown and are not treated as proof.",
                threshold_exceeded=False,
                alternative_explanations=[
                    "News copy, safety notices, and ordinary requests use the same words.",
                ],
                limitation=(
                    "Urgency wording does not prove that an audio sample was cloned, "
                    "that a person was impersonated, or that a fraud was committed."
                ),
                detector_id="lexical_token_overlap",
            )
        )

    unique_left = len(left_set)
    type_token = float(unique_left / len(left)) if left else None
    return {
        "status": "analyzed" if statement.strip() or comparison.strip() else "not_provided",
        "task": task,
        "error": None,
        "metadata": {
            "statement_token_count": len(left),
            "comparison_token_count": len(right),
            "type_token_ratio_statement": None if type_token is None else round(type_token, 6),
            "semantic_verifier": "UNAVAILABLE",
            "ai_text_classifier": "UNAVAILABLE",
        },
        "lexical": {
            "both_texts_present": both_present,
            "jaccard": None if jaccard is None else round(jaccard, 6),
            "shared_tokens": shared,
            "only_in_statement": only_left,
            "only_in_comparison": only_right,
            "statement_text": statement,
            "comparison_text": comparison,
            "label": "simple lexical screening",
        },
        "observations": observations,
        "indicators": [],
        "unavailable_detectors": ["semantic_entailment"],
    }
