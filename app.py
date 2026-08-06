import os
import re
import uuid
import pandas as pd
import streamlit as st

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

from core.chat import ChatHandler
from core.notifier import CrisisNotifier
from core.alert_log import CrisisAlertLog
from core.conversation_manager import ConversationManager
from utils.data_loader import load_csv, load_multiple_csvs, validate_csv, chunk_dataframe
from utils.pdf_loader import PDFLoader
from config.prompt import TRIAGE_LEVELS


def get_chat_handler(api_key: str = None):
    return ChatHandler(api_key=api_key)


st.set_page_config(
    page_title="Telepsicologia - Triaje Inteligente",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .triage-badge {
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 14px;
        display: inline-block;
        margin: 4px 0;
    }
    .disclaimer {
        background-color: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 16px;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chat_handler" not in st.session_state:
        st.session_state.chat_handler = None
    if "conv_manager" not in st.session_state:
        st.session_state.conv_manager = ConversationManager()
    if "data_indexed" not in st.session_state:
        st.session_state.data_indexed = False
    if "kb_stats" not in st.session_state:
        st.session_state.kb_stats = {"total_chunks": 0}
    if "uploaded_df" not in st.session_state:
        st.session_state.uploaded_df = None
    if "pdf_chunks" not in st.session_state:
        st.session_state.pdf_chunks = []
    if "pdf_metadata" not in st.session_state:
        st.session_state.pdf_metadata = []
    if "csv_merge_stats" not in st.session_state:
        st.session_state.csv_merge_stats = []
    if "student_info" not in st.session_state:
        st.session_state.student_info = None
    if "crisis_alert_sent" not in st.session_state:
        st.session_state.crisis_alert_sent = False
    if "crisis_alert_status" not in st.session_state:
        st.session_state.crisis_alert_status = None
def render_sidebar():
    with st.sidebar:
        st.header("⚙️ Configuracion")

        if st.session_state.student_info:
            st.caption(f"Sesion de: **{st.session_state.student_info['name']}**")
            st.caption(f"Cédula: **{st.session_state.student_info['cedula']}**")

        st.divider()
        st.header("📂 Subir Base de Conocimiento")

        upload_type = st.radio(
            "Tipo de archivo",
            ["CSV", "PDF"],
            horizontal=True,
            key="upload_type",
        )

        if upload_type == "CSV":
            uploaded_files = st.file_uploader(
                "Sube uno o varios archivos CSV",
                type=["csv"],
                accept_multiple_files=True,
                help="Puedes subir multiples CSV. Se fusionaran automaticamente.",
            )
        else:
            uploaded_files = st.file_uploader(
                "Sube tus documentos (PDF)",
                type=["pdf"],
                accept_multiple_files=True,
                help="Puedes subir multiples archivos PDF",
            )

        if uploaded_files:
            files_to_process = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]

            if upload_type == "CSV":
                try:
                    if len(files_to_process) == 1:
                        df = load_csv(files_to_process[0])
                        validation = validate_csv(df)
                        st.session_state.csv_merge_stats = [{"filename": files_to_process[0].name, "rows": len(df), "cols": len(df.columns)}]
                    else:
                        df, merge_stats = load_multiple_csvs(files_to_process)
                        validation = validate_csv(df)
                        st.session_state.csv_merge_stats = merge_stats

                    if validation["valid"]:
                        st.session_state.uploaded_df = df

                        if len(files_to_process) > 1:
                            st.success(f"{len(files_to_process)} CSV fusionados: {len(df)} registros totales")
                            with st.expander("📋 Detalle por archivo"):
                                for stat in st.session_state.csv_merge_stats:
                                    if "error" in stat:
                                        st.error(f"{stat['filename']}: {stat['error']}")
                                    else:
                                        st.write(f"**{stat['filename']}**: {stat['rows']} filas, {stat['cols']} columnas")
                        else:
                            st.success(f"CSV valido: {len(df)} registros")

                        st.dataframe(df.head(5), width="stretch")
                        st.caption(f"Columnas: {', '.join(df.columns.tolist())}")

                        if st.button("📥 Indexar para chatbot", width="stretch"):
                            with st.spinner("Procesando..."):
                                chunks = chunk_dataframe(df, text_columns=validation.get("text_columns"))
                                if st.session_state.chat_handler:
                                    indexed = st.session_state.chat_handler.rag.index_chunks(chunks)
                                    st.session_state.data_indexed = True
                                    st.session_state.kb_stats = st.session_state.chat_handler.rag.get_stats()
                                    st.success(f"Indexados {indexed} fragmentos para el chatbot")
                    else:
                        for error in validation["errors"]:
                            st.error(error)
                except Exception as e:
                    st.error(f"Error: {str(e)}")

            else:
                pdf_loader = PDFLoader()
                with st.spinner(f"Extrayendo texto de {len(files_to_process)} PDF(s)..."):
                    try:
                        results = pdf_loader.extract_all_pdfs(files_to_process)
                        all_chunks = pdf_loader.pdfs_to_dataframe(files_to_process)

                        st.session_state.pdf_chunks = all_chunks
                        st.session_state.pdf_metadata = [r["metadata"] for r in results]

                        st.success(f"{len(files_to_process)} PDF(s): {len(all_chunks)} fragmentos")

                        for r in results:
                            with st.expander(f"📄 {r['filename']} ({r['metadata']['pages']} pag)"):
                                st.text(r["full_text"][:500] + "..." if len(r["full_text"]) > 500 else r["full_text"])

                        if st.button("📥 Indexar PDFs", width="stretch"):
                            with st.spinner("Generando embeddings..."):
                                if st.session_state.chat_handler:
                                    indexed = st.session_state.chat_handler.rag.index_chunks(all_chunks)
                                    st.session_state.data_indexed = True
                                    st.session_state.kb_stats = st.session_state.chat_handler.rag.get_stats()
                                    st.success(f"Indexados {indexed} fragmentos de PDF")
                    except Exception as e:
                        st.error(f"Error al procesar PDFs: {str(e)}")

        if st.session_state.kb_stats.get("total_chunks", 0) > 0:
            st.divider()
            st.subheader("Estadisticas KB")
            st.metric("Fragmentos", st.session_state.kb_stats["total_chunks"])
            st.caption(
                f"📁 Guardado en `{st.session_state.kb_stats.get('persist_dir', './chroma_db')}`"
            )
            if st.button("🗑️ Reiniciar base de conocimiento", width="stretch"):
                if st.session_state.chat_handler is not None:
                    st.session_state.chat_handler.rag.reset_collection()
                    st.session_state.kb_stats = st.session_state.chat_handler.rag.get_stats()
                    st.success("Base de conocimiento reiniciada.")
                    st.rerun()

        # --- TRIAJE ---
        st.divider()
        st.subheader("Nivel de Triaje")
        triage_summary = None
        if st.session_state.chat_handler:
            triage_summary = st.session_state.chat_handler.get_triage_summary()

        if triage_summary and triage_summary["messages_analyzed"] > 0:
            level = triage_summary["current_level"]
            info = TRIAGE_LEVELS[level]
            st.markdown(
                f'<div class="triage-badge" style="background-color: {info["color"]}20; '
                f'color: {info["color"]}; border: 2px solid {info["color"]}">'
                f'{info["icon"]} {level}</div>',
                unsafe_allow_html=True,
            )
            st.caption(info["description"])
            st.info(f"Recomendacion: {info['recommendation']}")
        else:
            st.caption("El triaje se determina durante la conversacion.")

        # --- CONVERSACIONES GUARDADAS ---
        st.divider()
        with st.expander("💾 Conversaciones Guardadas", expanded=False):
            saved_convs = st.session_state.conv_manager.list_saved_conversations()
            if saved_convs:
                st.write(f"Total guardadas: **{len(saved_convs)}**")
                for c in saved_convs[:5]:
                    st.text(f"• {c['student_name']} ({c['cedula']})\n  Fecha: {c['updated_at'][:16]} | {c['total_messages']} msgs")
            else:
                st.caption("Aun no hay conversaciones guardadas.")

        st.divider()
        if st.session_state.chat_handler:
            if st.button("🔄 Nueva conversacion", width="stretch"):
                st.session_state.messages = []
                st.session_state.session_id = str(uuid.uuid4())[:8]
                st.session_state.chat_handler.reset()
                st.session_state.crisis_alert_sent = False
                st.session_state.crisis_alert_status = None
                st.rerun()

        st.divider()
        st.caption("v3.0 | DeepSeek AI & RAG Local | Telepsicologia")


def render_intake_gate():
    st.title("🧠 Telepsicologia - Triaje Inteligente")
    st.markdown(
        '<div class="disclaimer">'
        "⚠️ <b>Aviso:</b> Este asistente NO reemplaza una consulta psicologica profesional. "
        "Si estas en crisis ahora mismo, contacta los servicios de emergencia de tu localidad "
        "o acude presencialmente a urgencias."
        "</div>",
        unsafe_allow_html=True,
    )
    st.subheader("Antes de comenzar")
    st.caption(
        "Necesitamos tus datos de contacto. Si durante la conversacion se detecta "
        "un nivel de riesgo CRITICO (por ejemplo, ideas suicidas o autolesiones), "
        "el equipo de Bienestar Estudiantil sera notificado automaticamente por "
        "correo para que pueda contactarte."
    )

    with st.form("intake_form"):
        name = st.text_input("Nombre completo *", help="Solo se permiten letras y espacios.")
        email = st.text_input("Correo institucional *", help="Debe pertenecer al dominio @uide.edu.ec (ej. usuario@uide.edu.ec)")
        cedula = st.text_input("Cédula *", help="Ingresa exactamente 10 dígitos numéricos.")
        consent = st.checkbox(
            "Entiendo que mis datos de contacto podran ser compartidos con "
            "Bienestar Estudiantil unicamente en caso de deteccion de riesgo critico."
        )
        submitted = st.form_submit_button("Iniciar conversacion", width="stretch")

        if submitted:
            errors = []
            clean_name = name.strip()
            clean_email = email.strip()
            clean_cedula = cedula.strip()

            # Validacion estricta del nombre (solo letras y espacios)
            if not clean_name:
                errors.append("El nombre es obligatorio.")
            elif not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$", clean_name):
                errors.append("El nombre solo debe contener letras (sin numeros ni caracteres especiales).")

            # Validacion estricta del correo institucional (@uide.edu.ec)
            if not clean_email:
                errors.append("El correo institucional es obligatorio.")
            elif not clean_email.lower().endswith("@uide.edu.ec") or clean_email.count("@") != 1 or len(clean_email.split("@")[0].strip()) == 0:
                errors.append("Ingresa un correo institucional valido con dominio @uide.edu.ec (ej. usuario@uide.edu.ec).")

            # Validacion estricta de la cédula (solo numeros, exactamente 10 digitos)
            if not clean_cedula:
                errors.append("La cédula es obligatoria.")
            elif not re.match(r"^\d{10}$", clean_cedula):
                errors.append("La cédula solo debe contener numeros y tener exactamente 10 digitos.")

            # Consentimiento
            if not consent:
                errors.append("Debes aceptar el uso de tus datos de contacto para poder continuar.")

            if errors:
                for err in errors:
                    st.error(f"❌ {err}")
            else:
                st.session_state.student_info = {
                    "name": clean_name,
                    "email": clean_email,
                    "cedula": clean_cedula,
                }
                st.rerun()


def render_disclaimer():
    st.markdown(
        '<div class="disclaimer">'
        "⚠️ <b>Aviso:</b> Este asistente NO reemplaza una consulta psicologica profesional. "
        "Si estas en crisis, contacta los servicios de emergencia de tu localidad."
        "</div>",
        unsafe_allow_html=True,
    )


def render_main_content():
    st.title("🧠 Telepsicologia - Triaje Inteligente")
    st.caption("Asistente virtual de orientacion en salud mental con triaje inteligente (DeepSeek AI & RAG Local)")


def auto_save_current_conversation():
    """Guarda la conversacion actual en disco."""
    if st.session_state.student_info and st.session_state.chat_handler:
        triage_summary = st.session_state.chat_handler.get_triage_summary()
        st.session_state.conv_manager.save_conversation(
            session_id=st.session_state.session_id,
            student_info=st.session_state.student_info,
            messages=st.session_state.messages,
            triage_summary=triage_summary,
        )


def render_chat():
    if st.session_state.chat_handler is None:
        with st.spinner("Inicializando asistente de telepsicologia..."):
            st.session_state.chat_handler = get_chat_handler()
            st.session_state.kb_stats = st.session_state.chat_handler.rag.get_stats()

            if st.session_state.chat_handler.rag.reset_due_to_mismatch:
                st.warning(
                    "⚠️ Se encontro una base de conocimiento en `./chroma_db` "
                    "creada con un modelo incompatible y fue reiniciada automaticamente."
                )

    if not st.session_state.chat_handler.is_configured():
        st.error(
            "⚠️ **API Key de DeepSeek no configurada**: "
            "Por favor, configure `DEEPSEEK_API_KEY` en `.streamlit/secrets.toml` o en un archivo `.env`."
        )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "triage_level" in message:
                level = message["triage_level"]
                info = TRIAGE_LEVELS.get(level, TRIAGE_LEVELS["BAJO"])
                st.markdown(
                    f'<span style="color: {info["color"]}; font-size: 12px;">'
                    f'{info["icon"]} Triaje: {level}</span>',
                    unsafe_allow_html=True,
                )

    if prompt := st.chat_input("Cuentame como te sientes..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                response = st.write_stream(
                    st.session_state.chat_handler.get_response_stream(prompt)
                )

                triage_level = st.session_state.chat_handler.triage.current_level
                info = TRIAGE_LEVELS.get(triage_level, TRIAGE_LEVELS["BAJO"])
                st.markdown(
                    f'<span style="color: {info["color"]}; font-size: 12px;">'
                    f'{info["icon"]} Triaje: {triage_level}</span>',
                    unsafe_allow_html=True,
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "triage_level": triage_level,
                })

                # Guardado automatico de la conversacion
                auto_save_current_conversation()

                if triage_level == "CRITICO":
                    st.error(
                        "🚨 Si estas en peligro inmediato, llama a emergencias "
                        "o acude al servicio de emergencias mas cercano."
                    )

                    if not st.session_state.crisis_alert_sent:
                        smtp_config = dict(st.secrets.get("smtp", {}))
                        notifier = CrisisNotifier(smtp_config)
                        result = notifier.send_crisis_alert(
                            student_info=st.session_state.student_info,
                            triage_summary=st.session_state.chat_handler.get_triage_summary(),
                            recent_messages=st.session_state.messages,
                        )
                        st.session_state.crisis_alert_sent = True
                        st.session_state.crisis_alert_status = result

                        CrisisAlertLog().record(
                            student_info=st.session_state.student_info,
                            triage_level=triage_level,
                            email_result=result,
                        )

                        if result["sent"]:
                            st.success(
                                "✅ Bienestar Estudiantil ha sido notificado. "
                                "Alguien se pondra en contacto contigo pronto."
                            )
                        else:
                            st.warning(
                                "⚠️ No se pudo notificar automaticamente a Bienestar "
                                f"Estudiantil ({result['error']}). Por favor contacta "
                                "directamente a los servicios de emergencia de tu localidad."
                            )

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Lo siento, hubo un error. Intenta de nuevo.",
                })
                auto_save_current_conversation()


def main():
    init_session_state()

    if st.session_state.student_info is None:
        render_intake_gate()
        return

    render_disclaimer()
    render_sidebar()
    render_main_content()
    render_chat()


if __name__ == "__main__":
    main()
