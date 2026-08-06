import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, List, Optional


class CrisisNotifier:
    """Sends an email alert to Bienestar Estudiantil when the triage engine
    flags a session as CRITICO (ideas suicidas, autolesiones, o emergencia
    psicologica), para que una persona del equipo pueda contactar al
    estudiante directamente.
    """

    def __init__(self, smtp_config: Dict):
        self.host = smtp_config.get("host")
        self.port = int(smtp_config.get("port", 587))
        self.username = smtp_config.get("username")
        self.password = smtp_config.get("password")
        self.from_addr = smtp_config.get("from_addr") or self.username
        self.to_addr = smtp_config.get("to_addr")
        self.use_tls = smtp_config.get("use_tls", True)

    def is_configured(self) -> bool:
        """Check that the minimum SMTP settings are present."""
        return bool(self.host and self.username and self.password and self.to_addr)

    def send_crisis_alert(
        self,
        student_info: Dict,
        triage_summary: Dict,
        recent_messages: List[Dict],
        max_messages: int = 6,
    ) -> Dict[str, Optional[str]]:
        """
        Send the crisis alert email.
        Returns {"sent": bool, "error": str | None}.
        """
        if not self.is_configured():
            return {
                "sent": False,
                "error": (
                    "SMTP no configurado. Revisa la seccion [smtp] en "
                    ".streamlit/secrets.toml (host, username, password, to_addr)."
                ),
            }

        subject = (
            f"\U0001F534 ALERTA CRITICA - Triaje Telepsicologia - "
            f"{student_info.get('name', 'Estudiante')}"
        )

        transcript_lines = []
        for msg in recent_messages[-max_messages:]:
            role = "Estudiante" if msg.get("role") == "user" else "Asistente"
            transcript_lines.append(f"[{role}] {msg.get('content', '')}")
        transcript = "\n".join(transcript_lines) if transcript_lines else "(sin mensajes registrados)"

        body = f"""Se ha detectado un nivel de riesgo CRITICO en una sesion del chatbot de telepsicologia.

DATOS DEL ESTUDIANTE
Nombre: {student_info.get('name', 'No proporcionado')}
Correo: {student_info.get('email', 'No proporcionado')}
Cédula: {student_info.get('cedula', 'No proporcionado')}
Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

RESUMEN DE TRIAJE
Nivel actual: {triage_summary.get('current_level')}
Puntajes acumulados: {triage_summary.get('scores')}
Mensajes analizados: {triage_summary.get('messages_analyzed')}

ULTIMOS MENSAJES DE LA CONVERSACION
{transcript}

ACCION REQUERIDA
Por favor contacta al estudiante lo antes posible por el canal institucional
correspondiente (correo, telefono, o el protocolo de crisis vigente).

---
Este es un mensaje automatico generado por el sistema de triaje de
telepsicologia. No responder a este correo.
"""

        message = MIMEMultipart()
        message["From"] = self.from_addr
        message["To"] = self.to_addr
        message["Subject"] = subject
        message.attach(MIMEText(body, "plain", "utf-8"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.host, self.port, timeout=15) as server:
                if self.use_tls:
                    server.starttls(context=context)
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, [self.to_addr], message.as_string())
            return {"sent": True, "error": None}
        except Exception as e:
            return {"sent": False, "error": str(e)}
