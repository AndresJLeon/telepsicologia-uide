import os
from typing import List, Dict, Generator, Optional
import streamlit as st
# pyrefly: ignore [missing-import]
from openai import OpenAI

from dotenv import load_dotenv

import re
from config.prompt import PROMPT_TELEPSICOLOGIA
from core.rag_engine import RAGEngine
from core.triage import TriageEngine

try:
    from utils.validators import validar_mensaje_chat
except ImportError:
    def validar_mensaje_chat(mensaje: str):
        if not mensaje or not str(mensaje).strip():
            return False, "Por favor escribe un mensaje."
        msg = str(mensaje).strip()
        if msg.isdigit():
            return False, "El chat no acepta entradas compuestas únicamente por números."
        if not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]", msg):
            return False, "Por favor ingresa un mensaje descriptivo en texto."
        return True, "Mensaje válido."



class ChatHandler:
    """Maneja el flujo de chat, la recuperacion RAG y la integracion con la API de DeepSeek."""

    def __init__(self, api_key: Optional[str] = None):
        load_dotenv()
        if not api_key:
            api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key and hasattr(st, "secrets"):
            api_key = st.secrets.get("DEEPSEEK_API_KEY") or st.secrets.get("deepseek", {}).get("api_key")

        self.api_key = api_key
        self.client = None
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

        self.model_name = "deepseek-chat"
        self.rag = RAGEngine()
        self.triage = TriageEngine()
        self.messages: List[Dict] = []
        self.chat_history: List[Dict] = []
        self.last_rag_used: bool = False
        self._response_cache: Dict[str, str] = {}
        self._init_system_message()

    def set_api_key(self, api_key: str):
        """Actualiza la clave API de DeepSeek."""
        self.api_key = api_key
        self.client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com")

    def is_configured(self) -> bool:
        """Verifica si la API de DeepSeek tiene una clave valida configurada."""
        return bool(self.api_key and self.client)

    def _init_system_message(self):
        """Construye el mensaje de sistema inicial con el prompt de telepsicologia."""
        self.chat_history = [
            {"role": "system", "content": PROMPT_TELEPSICOLOGIA},
        ]
        self.messages = []
        self.last_rag_used = False

    def update_system_with_rag(self, user_query: str) -> bool:
        """Añade contexto de la base de conocimiento (RAG) a la conversacion."""
        rag_context = self.rag.get_context_for_query(user_query, n_results=3)

        if rag_context and rag_context.strip():
            context_msg = (
                f"--- CONOCIMIENTO ADICIONAL DE LA BASE DE DATOS (RAG) ---\n"
                f"Utiliza la siguiente informacion de referencia para enriquecer tu respuesta si es relevante:\n\n"
                f"{rag_context}\n"
                f"--- FIN DEL CONOCIMIENTO ---"
            )
            self.chat_history.append({"role": "user", "content": context_msg})
            self.chat_history.append(
                {"role": "assistant", "content": "Entendido, tomare en cuenta el contexto proporcionado para orientar al usuario."}
            )
            self.last_rag_used = True
        else:
            self.last_rag_used = False
        return self.last_rag_used

    def get_response_stream(
        self, user_message: str, status_callback: Optional[callable] = None
    ) -> Generator[str, None, None]:
        """Transmite la respuesta de la API de DeepSeek notificando estados intermedios."""
        if not self.is_configured():
            yield "⚠️ No se ha configurado la API Key de DeepSeek. Por favor, ingresa tu clave API en la barra lateral para continuar."
            return

        # Validar entrada de usuario para restringir números aislados
        val_ok, val_msg = validar_mensaje_chat(user_message)
        if not val_ok:
            yield f"⚠️ {val_msg}"
            return

        if status_callback:
            status_callback("🔍 Analizando triaje y nivel de urgencia...")
        self.triage.analyze_message(user_message)

        if status_callback:
            status_callback("🧠 Consultando Base de Conocimiento (RAG)...")
        rag_found = self.update_system_with_rag(user_message)

        if status_callback:
            if rag_found:
                status_callback("📚 RAG: Información recuperada de la Base UIDE. Generando orientación...")
            else:
                status_callback("🤖 LLM: Generando orientación con modelo de lenguaje general...")

        self.messages.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "user", "content": user_message})

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.chat_history,
                temperature=0.7,
                stream=True,
            )

            full_response = ""
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    yield token

            source_type = "RAG" if self.last_rag_used else "LLM"
            self.chat_history.append({"role": "assistant", "content": full_response})
            self.messages.append({
                "role": "assistant",
                "content": full_response,
                "source_type": source_type
            })

        except Exception as e:
            error_msg = f"Error al comunicarse con la API de DeepSeek: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg, "source_type": "ERROR"})
            yield error_msg


    def get_response(self, user_message: str) -> str:
        """Obtiene una respuesta completa de la API de DeepSeek."""
        if not self.is_configured():
            return "⚠️ No se ha configurado la API Key de DeepSeek. Por favor, ingresa tu clave API en la barra lateral."

        val_ok, val_msg = validar_mensaje_chat(user_message)
        if not val_ok:
            return f"⚠️ {val_msg}"

        self.triage.analyze_message(user_message)
        self.update_system_with_rag(user_message)

        self.messages.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "user", "content": user_message})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.chat_history,
                temperature=0.7,
                stream=False,
            )
            full_response = response.choices[0].message.content or ""
            source_type = "RAG" if self.last_rag_used else "LLM"
            self.chat_history.append({"role": "assistant", "content": full_response})
            self.messages.append({
                "role": "assistant",
                "content": full_response,
                "source_type": source_type
            })
            return full_response
        except Exception as e:
            error_msg = f"Error al comunicarse con la API de DeepSeek: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg, "source_type": "ERROR"})
            return error_msg


    def load_previous_messages(self, messages: List[Dict]):
        """Carga una lista de mensajes anteriores en el estado del handler y restaura el estado de triaje."""
        self.messages = list(messages)
        self.chat_history = [{"role": "system", "content": PROMPT_TELEPSICOLOGIA}]
        self.triage.reset()
        for m in self.messages:
            if m.get("role") in ["user", "assistant"]:
                self.chat_history.append({"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]})
            if m.get("role") == "user":
                self.triage.analyze_message(m["content"])


    def get_conversation_history(self) -> List[Dict]:
        return self.messages

    def get_triage_summary(self) -> Dict:
        return self.triage.get_summary()

    def reset(self):
        self._init_system_message()
        self.triage.reset()
