import os
import json
from datetime import datetime
from typing import Dict, List, Optional

CONVERSATIONS_DIR = os.path.join(".", "data", "conversations")

class ConversationManager:
    """Maneja el almacenamiento y recuperacion persistente de conversaciones en disco (archivos JSON)."""

    def __init__(self, storage_dir: str = CONVERSATIONS_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)

    def _get_filename(self, cedula: str, session_id: str) -> str:
        clean_cedula = "".join(filter(str.isalnum, str(cedula))) or "desconocido"
        return os.path.join(self.storage_dir, f"conv_{clean_cedula}_{session_id}.json")

    def save_conversation(
        self,
        session_id: str,
        student_info: Dict[str, str],
        messages: List[Dict],
        triage_summary: Optional[Dict] = None,
    ) -> str:
        """Guarda o actualiza la conversacion en formato JSON."""
        cedula = student_info.get("cedula", "desconocido")
        filepath = self.get_filepath(cedula, session_id)

        created_at = datetime.now().isoformat()
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    created_at = existing_data.get("created_at", created_at)
            except Exception:
                pass

        data = {
            "session_id": session_id,
            "created_at": created_at,
            "updated_at": datetime.now().isoformat(),
            "student_info": student_info,
            "triage_summary": triage_summary or {},
            "total_messages": len(messages),
            "messages": messages,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return filepath

    def get_filepath(self, cedula: str, session_id: str) -> str:
        return self._get_filename(cedula, session_id)

    def list_saved_conversations(self, cedula: Optional[str] = None) -> List[Dict]:
        """Devuelve la lista de conversaciones guardadas con su metadato basico.
        Si se especifica cedula, solo retorna las conversaciones de ese estudiante.
        """
        if not os.path.exists(self.storage_dir):
            return []

        clean_target_cedula = "".join(filter(str.isalnum, str(cedula))) if cedula else None

        convs = []
        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                full_path = os.path.join(self.storage_dir, filename)
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        student_info = data.get("student_info", {})
                        conv_cedula = "".join(filter(str.isalnum, str(student_info.get("cedula", ""))))

                        if clean_target_cedula and conv_cedula != clean_target_cedula:
                            continue

                        convs.append({
                            "filename": filename,
                            "filepath": full_path,
                            "session_id": data.get("session_id"),
                            "student_name": student_info.get("name", "N/A"),
                            "cedula": student_info.get("cedula", "N/A"),
                            "email": student_info.get("email", "N/A"),
                            "updated_at": data.get("updated_at"),
                            "total_messages": data.get("total_messages", 0),
                            "triage_level": data.get("triage_summary", {}).get("current_level", "N/A"),
                            "messages": data.get("messages", []),
                        })
                except Exception:
                    continue

        convs.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return convs

    def load_conversation(self, filepath: str) -> Optional[Dict]:
        """Carga una conversacion desde su archivo JSON."""
        if not os.path.exists(filepath):
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
