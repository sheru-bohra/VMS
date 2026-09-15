"""Structured AI response models and provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AIRecommendedAction:
    label: str
    path: str
    action_type: str = "navigate"


@dataclass
class AIInsightItem:
    type: str
    title: str
    explanation: str
    priority: str = "INFORMATION"
    evidence: List[str] = field(default_factory=list)


@dataclass
class AISourceReference:
    label: str
    path: Optional[str] = None
    reference: Optional[str] = None


@dataclass
class AIStructuredResponse:
    answer: str
    summary: str
    insights: List[AIInsightItem] = field(default_factory=list)
    recommended_actions: List[AIRecommendedAction] = field(default_factory=list)
    source_references: List[AISourceReference] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    denied: bool = False
    unavailable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "summary": self.summary,
            "insights": [
                {
                    "type": i.type,
                    "title": i.title,
                    "explanation": i.explanation,
                    "priority": i.priority,
                    "evidence": i.evidence,
                }
                for i in self.insights
            ],
            "recommended_actions": [
                {"label": a.label, "path": a.path, "action_type": a.action_type}
                for a in self.recommended_actions
            ],
            "source_references": [
                {"label": s.label, "path": s.path, "reference": s.reference}
                for s in self.source_references
            ],
            "limitations": self.limitations,
            "denied": self.denied,
            "unavailable": self.unavailable,
        }


class AIProvider(ABC):
    @abstractmethod
    def generate_structured_response(
        self,
        intent: str,
        question: str,
        context: Dict[str, Any],
        role: str,
    ) -> AIStructuredResponse:
        ...
