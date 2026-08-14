import re
from typing import Dict, List
from config.prompt import TRIAGE_KEYWORDS, TRIAGE_LEVELS


class TriageEngine:
    """Engine for classifying mental health urgency levels based on conversation."""

    LEVEL_RANK = {"BAJO": 1, "MEDIO": 2, "ALTO": 3, "CRITICO": 4}

    def __init__(self):
        self.history: List[Dict] = []
        self.current_level = "BAJO"
        self.urgency_scores = {"BAJO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}

    def analyze_message(self, user_message: str) -> str:
        """Analyze a user message and return the detected urgency level."""
        clean_msg = str(user_message).strip()

        # Omitir análisis si el mensaje es solo números o carece de texto alfabético
        if clean_msg.isdigit() or not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]", clean_msg):
            return self.current_level

        message_lower = user_message.lower()


        for level in ["CRITICO", "ALTO", "MEDIO", "BAJO"]:
            for keyword in TRIAGE_KEYWORDS[level]:
                if keyword in message_lower:
                    self.urgency_scores[level] += 2
                    if level == "CRITICO":
                        self.urgency_scores[level] += 3

        self.history.append({
            "message": user_message,
            "scores": dict(self.urgency_scores),
        })

        new_level = self._calculate_level()
        if self.LEVEL_RANK.get(new_level, 1) > self.LEVEL_RANK.get(self.current_level, 1):
            self.current_level = new_level
        return self.current_level

    def _calculate_level(self) -> str:
        """Calculate the overall urgency level from accumulated scores."""
        scores = self.urgency_scores

        if scores["CRITICO"] > 0:
            return "CRITICO"
        if scores["ALTO"] >= 4:
            return "ALTO"
        if scores["MEDIO"] >= 3:
            return "MEDIO"
        if scores["ALTO"] > 0:
            return "ALTO"
        if scores["MEDIO"] > 0:
            return "MEDIO"
        return "BAJO"

    def get_level_info(self, level: str = None) -> Dict:
        """Get display information for an urgency level."""
        if level is None:
            level = self.current_level
        return TRIAGE_LEVELS.get(level, TRIAGE_LEVELS["BAJO"])

    def get_summary(self) -> Dict:
        """Get a summary of the triage assessment."""
        return {
            "current_level": self.current_level,
            "level_info": self.get_level_info(),
            "messages_analyzed": len(self.history),
            "scores": dict(self.urgency_scores),
        }

    def reset(self):
        """Reset the triage engine state."""
        self.history = []
        self.current_level = "BAJO"
        self.urgency_scores = {"BAJO": 0, "MEDIO": 0, "ALTO": 0, "CRITICO": 0}

    @staticmethod
    def get_triage_badge(level: str) -> str:
        """Return a formatted badge string for display."""
        info = TRIAGE_LEVELS.get(level, TRIAGE_LEVELS["BAJO"])
        return f"{info['icon']} Nivel: {level}"

    @staticmethod
    def is_crisis_message(message: str) -> bool:
        """Quick check if a message contains critical crisis keywords."""
        message_lower = message.lower()
        return any(kw in message_lower for kw in TRIAGE_KEYWORDS["CRITICO"])
