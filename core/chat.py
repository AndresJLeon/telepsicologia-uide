import os
from typing import List, Dict, Generator, Optional
import streamlit as st
# pyrefly: ignore [missing-import]
from openai import OpenAI

from dotenv import load_dotenv

from config.prompt import PROMPT_TELEPSICOLOGIA
from core.rag_engine import RAGEngine
from core.triage import TriageEngine


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

    def update_system_with_rag(self, user_query: str):
        """Añade contexto de la base de conocimiento (RAG) a la conversacion."""
        rag_context = self.rag.get_context_for_query(user_query, n_results=3)

        if rag_context:
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

    def get_response_stream(self, user_message: str) -> Generator[str, None, None]:
        """Transmite la respuesta de la API de DeepSeek en tiempo real."""
        if not self.is_configured():
            yield "⚠️ No se ha configurado la API Key de DeepSeek. Por favor, ingresa tu clave API en la barra lateral para continuar."
            return

        self.triage.analyze_message(user_message)
        self.update_system_with_rag(user_message)

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

            self.chat_history.append({"role": "assistant", "content": full_response})
            self.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            error_msg = f"Error al comunicarse con la API de DeepSeek: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg})
            yield error_msg

    def get_response(self, user_message: str) -> str:
        """Obtiene una respuesta completa de la API de DeepSeek."""
        if not self.is_configured():
            return "⚠️ No se ha configurado la API Key de DeepSeek. Por favor, ingresa tu clave API en la barra lateral."

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
            self.chat_history.append({"role": "assistant", "content": full_response})
            self.messages.append({"role": "assistant", "content": full_response})
            return full_response
        except Exception as e:
            error_msg = f"Error al comunicarse con la API de DeepSeek: {str(e)}"
            self.messages.append({"role": "assistant", "content": error_msg})
            return error_msg

    def get_conversation_history(self) -> List[Dict]:
        return self.messages

    def get_triage_summary(self) -> Dict:
        return self.triage.get_summary()

    def reset(self):
        self._init_system_message()
        self.triage.reset()
