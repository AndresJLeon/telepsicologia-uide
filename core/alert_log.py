import csv
import os
from datetime import datetime
from typing import Dict


class CrisisAlertLog:
    """Guarda un registro local (CSV) de cada alerta CRITICA detectada por el
    triaje, independientemente de si el correo a Bienestar Estudiantil se
    pudo enviar o no. Sirve como respaldo/auditoria: si el SMTP falla o nadie
    revisa el correo a tiempo, este archivo sigue siendo la evidencia de que
    hubo una alerta y de que estudiante se trataba.
    """

    def __init__(self, log_path: str = "./logs/crisis_alerts.csv"):
        self.log_path = log_path
        self._ensure_file()

    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(
                    [
                        "timestamp",
                        "nombre",
                        "correo",
                        "cedula",
                        "nivel_triaje",
                        "correo_enviado",
                        "error_envio",
                    ]
                )

    def record(self, student_info: Dict, triage_level: str, email_result: Dict):
        self._ensure_file()
        with open(self.log_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    student_info.get("name", ""),
                    student_info.get("email", ""),
                    student_info.get("cedula", ""),
                    triage_level,
                    email_result.get("sent", False),
                    email_result.get("error") or "",
                ]
            )
