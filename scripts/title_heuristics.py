#!/usr/bin/env python3
"""Shared title/hook heuristics for research collection and calendar generation."""

from __future__ import annotations

import re


def infer_hook_angle(title: str, desc: str) -> str:
    """Classify a live note's hook angle from its title and description."""
    text = f"{title} {desc}"
    if "?" in text or "？" in text:
        return "question-led hook"
    if re.search(r"\d|一|二|三|四|五|六|七|八|九|十", title):
        return "number/list hook"
    if any(word in text for word in ["避雷", "踩坑", "后悔", "不要"]):
        return "risk-avoidance hook"
    if any(word in text for word in ["教程", "方法", "步骤", "攻略"]):
        return "how-to hook"
    return "benefit-led hook"


def infer_title_family(reference_title: str) -> str:
    """Classify a benchmark title into the family used to bias generated titles."""
    if "？" in reference_title or "?" in reference_title:
        return "question"
    if any(char.isdigit() for char in reference_title):
        return "number"
    if any(token in reference_title for token in ["别再", "千万别", "不要"]):
        return "warning"
    if any(token in reference_title for token in ["对比", "VS", "vs"]):
        return "comparison"
    return "default"


def title_features(title: str) -> set[str]:
    features = set()
    if "？" in title or "?" in title:
        features.add("question")
    if any(char.isdigit() for char in title):
        features.add("number")
    if any(token in title for token in ["别再", "千万别", "不要", "避坑"]):
        features.add("warning")
    if any(token in title for token in ["对比", "差别", "VS", "vs"]):
        features.add("comparison")
    if any(token in title for token in ["怎么做", "怎么选", "先看", "攻略", "指南"]):
        features.add("intent")
    return features
