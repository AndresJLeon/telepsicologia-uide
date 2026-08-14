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
try:
    from utils.validators import (
        validar_cedula_ecuador,
        validar_email_uide,
        validar_nombre,
        validar_mensaje_chat,
    )
except ImportError:
    from utils.validators import validar_cedula_ecuador, validar_email_uide, validar_nombre
    def validar_mensaje_chat(mensaje: str):
        if not mensaje or not str(mensaje).strip():
            return False, "Por favor escribe un mensaje."
        msg = str(mensaje).strip()
        if msg.isdigit():
            return False, "El chat no acepta entradas compuestas únicamente por números. Por favor describe lo que sientes con texto."
        if not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑ]", msg):
            return False, "Por favor ingresa un mensaje descriptivo en texto sobre cómo te sientes."
        return True, "Mensaje válido."


from config.prompt import TRIAGE_LEVELS


# --- CONFIGURACIÓN DE PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="Telepsicología UIDE - Triaje Inteligente",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- ESTILOS CSS CON ALTO CONTRASTE Y PALETA INSTITUCIONAL UIDE (BORGOÑA, MOSTAZA Y AZUL NAVY) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&family=Inter:wght@400;500;600&display=swap');

    /* Forzar fondo claro global y tipografía de alto contraste */
    html, body, [data-testid="stAppViewContainer"], .stApp {
        font-family: 'Inter', sans-serif !important;
        background-color: #F4F6F9 !important;
        color: #1A202C !important;
    }

    [data-testid="stHeader"] {
        background-color: #FFFFFF !important;
        border-bottom: 3px solid #E5A823 !important;
    }

    /* Encabezados con color institucional Borgoña y tipografía Outfit (excluyendo títulos del banner) */
    h2, h3, h4, h5, h6, 
    .stMarkdown h2, .stMarkdown h3,
    .stMarkdown h1:not(.uide-title-mustaza),
    h1:not(.uide-title-mustaza) {
        color: #800020 !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
    }


    p, span, label, div, li, td, th {
        color: #2D3748 !important;
    }

    /* Estilos del Sidebar */
    [data-testid="stSidebar"] {
        background-color: #FFFFFF !important;
        border-right: 1.5px solid #E2E8F0 !important;
    }

    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #2D3748 !important;
    }

    /* Formularios e Inputs */
    input[type="text"], input[type="email"], textarea, div[data-baseweb="input"] input {
        background-color: #FFFFFF !important;
        color: #1A202C !important;
        border: 1.5px solid #CBD5E0 !important;
        border-radius: 8px !important;
    }

    input[type="text"]:focus, input[type="email"]:focus, div[data-baseweb="input"]:focus-within {
        border-color: #800020 !important;
        box-shadow: 0 0 0 3px rgba(128, 0, 32, 0.15) !important;
    }

    /* Botones primarios UIDE - Mantener tamaño original de Streamlit */
    .stButton > button,
    div[data-testid="stFormSubmitButton"] > button {
        background-color: #800020 !important;
        color: #E5A823 !important;
        border-radius: 8px !important;
        border: none !important;
        font-weight: 700 !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Cambiar SOLO el color del texto de los hijos sin alterar tamaños ni padding */
    .stButton > button p,
    .stButton > button span,
    .stButton > button div,
    div[data-testid="stFormSubmitButton"] > button p,
    div[data-testid="stFormSubmitButton"] > button span,
    div[data-testid="stFormSubmitButton"] > button div,
    [data-testid="stSidebar"] .stButton > button p,
    [data-testid="stSidebar"] .stButton > button span,
    [data-testid="stSidebar"] .stButton > button div {
        color: #E5A823 !important;
        font-weight: 700 !important;
    }

    .stButton > button:hover,
    div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #5c0017 !important;
        box-shadow: 0 4px 12px rgba(128, 0, 32, 0.25) !important;
        color: #FFD700 !important;
    }

    .stButton > button:hover p,
    .stButton > button:hover span,
    .stButton > button:hover div,
    div[data-testid="stFormSubmitButton"] > button:hover p,
    div[data-testid="stFormSubmitButton"] > button:hover span,
    div[data-testid="stFormSubmitButton"] > button:hover div,
    [data-testid="stSidebar"] .stButton > button:hover p,
    [data-testid="stSidebar"] .stButton > button:hover span,
    [data-testid="stSidebar"] .stButton > button:hover div {
        color: #FFD700 !important;
    }



    /* Barra de entrada del Chat */
    [data-testid="stChatInput"] {
        background-color: #FFFFFF !important;
        border: 2px solid #CBD5E0 !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05) !important;
    }

    [data-testid="stChatInput"] textarea {
        color: #1A202C !important;
        background-color: transparent !important;
    }

    /* Burbujas del Chat */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        margin-bottom: 12px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03) !important;
    }

    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] span, [data-testid="stChatMessage"] div {
        color: #1A202C !important;
        font-size: 15px !important;
        line-height: 1.6 !important;
    }

    /* Banner Principal UIDE */
    .uide-header-banner {
        background: linear-gradient(135deg, #800020 0%, #5c0017 60%, #1A365D 100%);
        padding: 24px 28px;
        border-radius: 14px;
        margin-bottom: 24px;
        box-shadow: 0 8px 22px rgba(128, 0, 32, 0.2);
        border-bottom: 4px solid #E5A823;
    }

    .uide-banner-title,
    .uide-header-banner .uide-banner-title,
    h1.uide-title-mustaza,
    .uide-header-banner h1,
    div.uide-header-banner > h1,
    .stMarkdown .uide-header-banner h1,
    div[data-testid="stMarkdownContainer"] .uide-header-banner h1 {
        font-family: 'Outfit', sans-serif !important;
        color: #E5A823 !important;
        font-size: 28px !important;
        font-weight: 700 !important;
        margin: 0 0 6px 0 !important;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8) !important;
        line-height: 1.2 !important;
    }


    .uide-header-banner p,
    div.uide-header-banner > p,
    .stMarkdown .uide-header-banner p,
    div[data-testid="stMarkdownContainer"] .uide-header-banner p {
        color: #FFFFFF !important;
        font-size: 15px !important;
        font-weight: 500 !important;
        margin: 0 !important;
        text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5) !important;
    }




    /* Disclaimer box */
    .uide-disclaimer {
        background-color: #FFF8E7 !important;
        border-left: 5px solid #E5A823 !important;
        color: #744210 !important;
        padding: 16px 20px;
        border-radius: 10px;
        font-size: 14px;
        line-height: 1.6;
        margin-bottom: 22px;
    }

    .uide-disclaimer b, .uide-disclaimer span {
        color: #744210 !important;
    }

    /* Tarjetas del Dashboard / Admin */
    .uide-card {
        background-color: #FFFFFF !important;
        border-radius: 12px;
        padding: 20px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        margin-bottom: 20px;
    }

    /* Pestañas (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 44px;
        background-color: #EDF2F7 !important;
        border-radius: 8px 8px 0 0;
        color: #2D3748 !important;
        font-weight: 600;
        padding: 0 16px;
    }

    .stTabs [aria-selected="true"] {
        background-color: #800020 !important;
        color: #E5A823 !important;
    }

    .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span {
        color: #E5A823 !important;
    }


    /* Estado animado del Bot */
    .bot-status-container {
        display: flex;
        align-items: center;
        gap: 10px;
        background-color: #EBF8FF;
        border: 1px solid #BEE3F8;
        color: #1A365D !important;
        padding: 12px 18px;
        border-radius: 10px;
        font-size: 14px;
        font-weight: 500;
        margin-bottom: 14px;
    }
</style>
""", unsafe_allow_html=True)


def get_chat_handler(api_key: str = None):
    return ChatHandler(api_key=api_key)


import hashlib

def get_admin_password() -> str:
    """Obtiene la contraseña de administrador configurada o por defecto ('uide2026admin')."""
    if hasattr(st, "secrets") and "ADMIN_PASSWORD" in st.secrets:
        return str(st.secrets["ADMIN_PASSWORD"])
    if hasattr(st, "secrets") and "admin" in st.secrets and "password" in st.secrets.admin:
        return str(st.secrets.admin.password)
    return "uide2026admin"


def verify_admin_password(input_password: str) -> bool:
    """Verifica si la contraseña ingresada coincide con la contraseña configurada usando SHA-256."""
    expected = get_admin_password().strip()
    input_clean = str(input_password).strip()
    return hashlib.sha256(input_clean.encode()).hexdigest() == hashlib.sha256(expected.encode()).hexdigest()


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
    if "current_status_text" not in st.session_state:
        st.session_state.current_status_text = ""
    if "app_mode" not in st.session_state:
        st.session_state.app_mode = "Estudiante"
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False


def auto_save_current_conversation():
    """Guarda la conversacion del estudiante de forma aislada en disco."""
    if st.session_state.student_info and st.session_state.chat_handler:
        triage_summary = st.session_state.chat_handler.get_triage_summary()
        st.session_state.conv_manager.save_conversation(
            session_id=st.session_state.session_id,
            student_info=st.session_state.student_info,
            messages=st.session_state.messages,
            triage_summary=triage_summary,
        )


def render_intake_gate():
    """Formulario de registro del estudiante con validaciones estrictas y algoritmo Módulo 10 de Cédula Ecuatoriana."""
    st.markdown("""
    <div class="uide-header-banner">
        <div class="uide-banner-title" style="color: #E5A823 !important; font-family: 'Outfit', sans-serif !important; font-size: 28px !important; font-weight: 700 !important; margin: 0 0 6px 0 !important; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8) !important;">🧠 Telepsicología UIDE - Orientación en Salud Mental</div>
        <p style="color: #FFFFFF !important; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5) !important;">Universidad Internacional del Ecuador | Sistema Integrado de Triaje Inteligente</p>
    </div>



    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="uide-disclaimer">'
        "⚠️ <b>Aviso Importante:</b> Este asistente virtual no reemplaza una consulta psicológica profesional. "
        "Si te encuentras en una crisis grave o emergencia inmediata, por favor contacta a los servicios de emergencia de tu localidad "
        "o acude al centro de salud más cercano."
        "</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([3, 2])

    with col1:
        with st.form("intake_form"):
            st.subheader("📋 Registro de Ingreso Estudiantil")
            st.caption("Por favor ingresa tus datos institucionales para comenzar.")

            name = st.text_input("Nombre completo *", help="Ingresa tu nombre y apellido (solo letras).")
            email = st.text_input("Correo institucional UIDE *", help="Debe terminar en @uide.edu.ec")
            cedula = st.text_input("Cédula de Identidad Ecuatoriana *", help="Exactamente 10 dígitos numéricos válidos en Ecuador.")

            with st.expander("📄 Política de Tratamiento de Datos Personales (LOPDP Ecuador)", expanded=False):
                st.markdown("""
                <div style="font-size: 13px; color: #2D3748; line-height: 1.6;">
                <b>Tratamiento de Datos Personales:</b> De conformidad con la Ley Orgánica de Protección de Datos Personales de Ecuador (LOPDP), la Universidad Internacional del Ecuador (UIDE) informa que sus datos identificativos (nombre, correo institucional y cédula) y las interacciones realizadas en esta plataforma serán tratadas de manera estrictamente confidencial.<br><br>
                <b>Finalidad:</b> Orientación emocional psicoeducativa primaria, registro de sesión y acompañamiento seguro para el bienestar estudiantil.<br><br>
                <b>Derechos ARCO:</b> Usted puede ejercer sus derechos de acceso, rectificación, cancelación y oposición de acuerdo a la normativa vigente.
                </div>
                """, unsafe_allow_html=True)

            consent = st.checkbox(
                "He leído y acepto la política de tratamiento de datos personales y términos de confidencialidad UIDE."
            )
            submitted = st.form_submit_button("Iniciar Conversación ➔", use_container_width=True)

            if submitted:
                errors = []

                val_n_ok, val_n_msg = validar_nombre(name)
                if not val_n_ok:
                    errors.append(val_n_msg)

                val_e_ok, val_e_msg = validar_email_uide(email)
                if not val_e_ok:
                    errors.append(val_e_msg)

                val_c_ok, val_c_msg = validar_cedula_ecuador(cedula)
                if not val_c_ok:
                    errors.append(val_c_msg)

                if not consent:
                    errors.append("Debes aceptar la política de tratamiento de datos personales para continuar.")


                if errors:
                    for err in errors:
                        st.error(f"❌ {err}")
                else:
                    st.session_state.student_info = {
                        "name": name.strip(),
                        "email": email.strip().lower(),
                        "cedula": cedula.strip(),
                    }
                    st.rerun()


    with col2:

        if os.path.exists("salud_mental_uide.jpg"):
            st.image("salud_mental_uide.jpg", use_container_width=True)
            st.markdown("""
            <div style="text-align: center; padding: 10px 0;">
                <h3 style="color: #800020; font-family: 'Outfit'; margin: 0;">💜 Mente sana, vida plena</h3>
                <p style="font-size: 14px; color: #4A5568; margin-top: 6px;">Tu bienestar emocional es nuestra prioridad. Habla en un espacio seguro, confidencial y diseñado para ti en la UIDE.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="uide-card">
                <h3 style="color: #800020; font-family: 'Outfit'; margin-top:0;">💜 Mente sana, vida plena</h3>
                <p style="font-size: 14px; line-height: 1.8; color: #2D3748;">Tu bienestar emocional es nuestra prioridad. La UIDE te brinda un espacio seguro, confidencial y libre de juicios para orientarte en todo momento.</p>
            </div>
            """, unsafe_allow_html=True)


def render_admin_login_gate():
    """Pantalla de inicio de sesión protegida para Administradores de Bienestar UIDE."""
    st.markdown("""
    <div class="uide-header-banner" style="background: linear-gradient(135deg, #1A365D 0%, #0F2942 100%);">
        <h1>🔐 Acceso Restringido - Personal UIDE</h1>
        <p>Bienestar Estudiantil y Gestión de Salud Mental</p>
    </div>
    """, unsafe_allow_html=True)

    col1, _ = st.columns([2, 1])
    with col1:
        with st.form("admin_login_form"):
            st.subheader("Ingreso con Contraseña Cifrada")
            st.caption("Esta sección está reservada exclusivamente para el personal autorizado de la UIDE.")

            password_input = st.text_input(
                "Contraseña de Administrador *",
                type="password",
                placeholder="••••••••••••",
                help="Ingresa la contraseña de administración configurada."
            )
            submit = st.form_submit_button("Acceder al Panel ➔", use_container_width=True)

            if submit:
                if verify_admin_password(password_input):
                    st.session_state.admin_authenticated = True
                    st.session_state.app_mode = "Administrador"
                    st.success("✅ Autenticación exitosa. Redirigiendo...")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta. Acceso denegado.")


def render_student_sidebar():
    """Sidebar para la vista del estudiante con selector de historial privado y acceso admin oculto."""
    with st.sidebar:
        st.markdown(
            '<div style="text-align: center; padding: 10px 0;">'
            '<h2 style="color: #800020; font-family: Outfit, sans-serif; margin:0;">🎓 Mi Espacio UIDE</h2>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        if st.session_state.student_info:
            st.markdown(f"👤 Estudiante: **{st.session_state.student_info['name']}**")
            st.caption(f"🆔 Cédula: `{st.session_state.student_info['cedula']}`")
            st.caption(f"📧 Correo: `{st.session_state.student_info['email']}`")

            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                st.session_state.student_info = None
                st.session_state.messages = []
                st.session_state.chat_handler = None
                st.rerun()

        st.divider()

        # Historial de conversaciones PRIVADO del estudiante (filtrado estrictamente por cédula)
        st.subheader("💾 Mis Conversaciones")
        if st.session_state.student_info:
            user_cedula = st.session_state.student_info["cedula"]
            user_convs = st.session_state.conv_manager.list_saved_conversations(cedula=user_cedula)

            if user_convs:
                st.caption(f"Tienes {len(user_convs)} conversación(es) guardada(s):")
                for c in user_convs[:6]:
                    is_active = (c["session_id"] == st.session_state.get("session_id"))
                    icon = "📌" if is_active else "💬"
                    active_tag = " (Activa)" if is_active else ""

                    # Extraer el primer mensaje del estudiante para título descriptivo
                    first_user_msg = next((m.get("content", "") for m in c.get("messages", []) if m.get("role") == "user"), "")
                    clean_first_msg = " ".join(first_user_msg.split())
                    if clean_first_msg:
                        title_text = f'"{clean_first_msg[:24].strip()}..."' if len(clean_first_msg) > 24 else f'"{clean_first_msg}"'
                    else:
                        title_text = c['updated_at'][:16]

                    label = f"{icon} {title_text} ({c['total_messages']} msgs){active_tag}"

                    if st.button(label, key=f"load_conv_{c['session_id']}", use_container_width=True):
                        full_conv = st.session_state.conv_manager.load_conversation(c["filepath"])
                        if full_conv and "messages" in full_conv:
                            st.session_state.session_id = c["session_id"]
                            st.session_state.messages = full_conv["messages"]

                            if st.session_state.chat_handler is None:
                                st.session_state.chat_handler = get_chat_handler()

                            st.session_state.chat_handler.load_previous_messages(full_conv["messages"])
                            st.success("Conversación cargada. Puedes continuar chateando.")
                            st.rerun()
            else:
                st.caption("Aún no tienes conversaciones previas guardadas.")



        st.divider()

        if st.button("➕ Nueva Conversación", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())[:8]
            if st.session_state.chat_handler:
                st.session_state.chat_handler.reset()
            st.session_state.crisis_alert_sent = False
            st.session_state.crisis_alert_status = None
            st.rerun()

        st.divider()



        # Acceso discreto para administradores de Bienestar UIDE
        with st.expander("🔒 Acceso Administración UIDE", expanded=False):
            admin_pwd = st.text_input("Contraseña Admin", type="password", key="side_admin_pwd")
            if st.button("Ingresar como Admin", key="side_admin_btn", use_container_width=True):
                if verify_admin_password(admin_pwd):
                    st.session_state.admin_authenticated = True
                    st.session_state.app_mode = "Administrador"
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")

        st.caption("UIDE Telepsicología v4.0 | RAG & DeepSeek AI")


def render_student_chat():
    """Interfaz principal del chat para el estudiante."""
    if st.session_state.chat_handler is None:
        with st.spinner("Inicializando asistente de telepsicología UIDE..."):
            st.session_state.chat_handler = get_chat_handler()
            st.session_state.kb_stats = st.session_state.chat_handler.rag.get_stats()

    st.markdown("""
    <div class="uide-header-banner">
        <div class="uide-banner-title" style="color: #E5A823 !important; font-family: 'Outfit', sans-serif !important; font-size: 28px !important; font-weight: 700 !important; margin: 0 0 6px 0 !important; text-shadow: 0 2px 8px rgba(0, 0, 0, 0.8) !important;">💬 Orientación Psicológica UIDE</div>
        <p style="color: #FFFFFF !important; text-shadow: 0 1px 3px rgba(0, 0, 0, 0.5) !important;">Habla con nuestro asistente virtual sobre lo que sientes. Tu bienestar es nuestra prioridad.</p>
    </div>


    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="uide-disclaimer">'
        "⚠️ <b>Aviso de Acompañamiento y Exención Médica:</b> Este chat ofrece orientación emocional y acompañamiento psicoeducativo temporal. "
        "<b>NO emite diagnósticos médicos ni psicológicos clínicos ni receta fármacos.</b> "
        "Si requieres atención médica o te encuentras en una crisis grave, contacta inmediatamente al <b>911</b>, a la línea <b>171 Opción 6</b> o a Bienestar Estudiantil UIDE."
        "</div>",
        unsafe_allow_html=True,
    )

    # Mostrar mensajes existentes en el chat con indicación de procedencia (RAG vs LLM)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                source = message.get("source_type")
                if source == "RAG":
                    st.caption("📚 *Respuesta respaldada con la Base de Conocimiento UIDE (RAG)*")
                elif source == "LLM":
                    st.caption("🤖 *Orientación generada por el Modelo LLM (DeepSeek AI)*")

    # Alerta sutil en caso de riesgo crítico
    if st.session_state.chat_handler and st.session_state.chat_handler.triage.current_level == "CRITICO":
        st.error(
            "🚨 **Atención de Emergencia**: Si te sientes en peligro o necesitas ayuda inmediata, "
            "contacta al 911 o acude al centro de salud o urgencias más cercano."
        )

    # Input del usuario con validación estricta de texto

    if prompt := st.chat_input("Cuéntame cómo te sientes hoy..."):
        val_ok, val_msg = validar_mensaje_chat(prompt)
        if not val_ok:
            st.warning(f"⚠️ {val_msg}")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                status_box = st.empty()

                def update_status(status_msg: str):
                    status_box.markdown(
                        f'<div class="bot-status-container"><span>⏳</span> <b>Estado del Asistente:</b> {status_msg}</div>',
                        unsafe_allow_html=True,
                    )

                try:
                    # Transmisión con actualización de estados en vivo
                    response = st.write_stream(
                        st.session_state.chat_handler.get_response_stream(
                            prompt, status_callback=update_status
                        )
                    )

                    # Limpiar la caja de estado al finalizar
                    status_box.empty()

                    triage_level = st.session_state.chat_handler.triage.current_level
                    source_type = "RAG" if getattr(st.session_state.chat_handler, "last_rag_used", False) else "LLM"

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "triage_level": triage_level,
                        "source_type": source_type,
                    })

                    # Guardado automático privado de la conversación
                    auto_save_current_conversation()

                    # Notificación automática únicamente si el triaje detecta nivel CRÍTICO
                    if triage_level == "CRITICO" and not st.session_state.crisis_alert_sent:
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

                    st.rerun()

                except Exception as e:
                    status_box.empty()
                    st.error(f"Ocurrió un error al procesar tu mensaje: {str(e)}")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "Lo siento, tuve un problema de conexión. Por favor inténtalo nuevamente.",
                    })
                    auto_save_current_conversation()



def render_admin_panel():
    """Panel de administración e inspección de triaje para la UIDE."""
    if not st.session_state.get("admin_authenticated", False):
        render_admin_login_gate()
        return

    with st.sidebar:
        st.markdown("<h3 style='color: #1A365D; font-family: Outfit;'>📊 Panel Administrador</h3>", unsafe_allow_html=True)
        st.caption("Sesión de Administración Activa")
        if st.button("🚪 Salir del Panel Admin", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.session_state.app_mode = "Estudiante"
            st.rerun()
        st.divider()

    st.markdown("""
    <div class="uide-header-banner" style="background: linear-gradient(135deg, #1A365D 0%, #0F2942 100%);">
        <h1>📊 Panel de Administración & Triaje UIDE</h1>
        <p>Gestión de casos, monitoreo de salud mental e indexación de base de conocimientos RAG.</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.chat_handler is None:
        st.session_state.chat_handler = get_chat_handler()

    tab1, tab2, tab3 = st.tabs(["📋 Monitoreo de Casos Guardados", "📂 Base de Conocimiento RAG", "🚨 Bitácora de Alertas de Crisis"])

    with tab1:
        st.subheader("Conversaciones Guardadas en la Plataforma")

        all_convs = st.session_state.conv_manager.list_saved_conversations(cedula=None)

        if not all_convs:
            st.info("Aún no existen conversaciones guardadas en el sistema.")
        else:
            col_search, col_filter = st.columns([2, 1])
            with col_search:
                search_query = st.text_input("🔍 Buscar por Nombre o Cédula", "")
            with col_filter:
                filter_level = st.selectbox("Filtrar por Triaje", ["TODOS", "BAJO", "MEDIO", "ALTO", "CRITICO"])

            filtered = []
            for c in all_convs:
                if filter_level != "TODOS" and c["triage_level"] != filter_level:
                    continue
                if search_query:
                    q = search_query.lower()
                    if q not in c["student_name"].lower() and q not in c["cedula"].lower():
                        continue
                filtered.append(c)

            st.metric("Total Conversaciones Registradas", len(filtered))

            for c in filtered:
                level = c["triage_level"]
                info = TRIAGE_LEVELS.get(level, TRIAGE_LEVELS["BAJO"])

                with st.expander(f"{info['icon']} Estudiante: {c['student_name']} (Cédula: {c['cedula']}) | Nivel: {level} | Fecha: {c['updated_at'][:16]}"):
                    st.write(f"**Correo:** {c['email']}")
                    st.write(f"**Mensajes totales:** {c['total_messages']}")
                    st.write(f"**Nivel de riesgo:** <span style='color: {info['color']}; font-weight: bold;'>{level}</span>", unsafe_allow_html=True)
                    st.write(f"**Recomendación:** {info['recommendation']}")

                    st.divider()
                    st.subheader("Transcripción de la Conversación:")
                    for m in c.get("messages", []):
                        role_icon = "👤 Estudiante" if m["role"] == "user" else "🤖 Asistente"
                        source_tag = ""
                        if m["role"] == "assistant":
                            src = m.get("source_type", "N/A")
                            if src == "RAG":
                                source_tag = " `[Fuente: Base de Conocimiento RAG]`"
                            elif src == "LLM":
                                source_tag = " `[Fuente: Modelo DeepSeek LLM]`"
                        st.markdown(f"**{role_icon}{source_tag}:** {m['content']}")


    with tab2:
        st.subheader("Gestión e Indexación de Base de Conocimiento (CSVs / PDFs)")

        kb_stats = st.session_state.chat_handler.rag.get_stats()
        st.metric("Total Fragmentos (Chunks) en ChromaDB", kb_stats.get("total_chunks", 0))

        st.divider()

        upload_type = st.radio("Tipo de documento a indexar", ["CSV", "PDF"], horizontal=True)

        if upload_type == "CSV":
            uploaded_files = st.file_uploader("Sube archivos CSV", type=["csv"], accept_multiple_files=True)
            if uploaded_files:
                try:
                    files_list = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]
                    if len(files_list) == 1:
                        df = load_csv(files_list[0])
                        validation = validate_csv(df)
                    else:
                        df, _ = load_multiple_csvs(files_list)
                        validation = validate_csv(df)

                    if validation["valid"]:
                        st.dataframe(df.head(5), use_container_width=True)
                        if st.button("📥 Indexar CSV en RAG", use_container_width=True):
                            with st.spinner("Indexando fragmentos..."):
                                chunks = chunk_dataframe(df, text_columns=validation.get("text_columns"))
                                count = st.session_state.chat_handler.rag.index_chunks(chunks)
                                st.success(f"Se indexaron exitosamente {count} fragmentos en la base de datos de conocimiento.")
                                st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar CSV: {str(e)}")
        else:
            uploaded_files = st.file_uploader("Sube archivos PDF", type=["pdf"], accept_multiple_files=True)
            if uploaded_files:
                try:
                    pdf_loader = PDFLoader()
                    files_list = uploaded_files if isinstance(uploaded_files, list) else [uploaded_files]
                    all_chunks = pdf_loader.pdfs_to_dataframe(files_list)
                    st.success(f"Procesados {len(files_list)} PDF(s): {len(all_chunks)} fragmentos de texto.")

                    if st.button("📥 Indexar PDFs en RAG", use_container_width=True):
                        with st.spinner("Indexando PDFs..."):
                            count = st.session_state.chat_handler.rag.index_chunks(all_chunks)
                            st.success(f"Se indexaron exitosamente {count} fragmentos de PDF en ChromaDB.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar PDFs: {str(e)}")

        st.divider()
        if st.button("🗑️ Reiniciar Base de Conocimiento RAG", use_container_width=True):
            st.session_state.chat_handler.rag.reset_collection()
            st.success("La base de conocimiento ChromaDB ha sido reiniciada.")
            st.rerun()

    with tab3:
        st.subheader("Bitácora de Alertas de Crisis Notificadas")
        alert_log = CrisisAlertLog().get_history()
        if alert_log:
            st.dataframe(pd.DataFrame(alert_log), use_container_width=True)
        else:
            st.info("No hay registros de alertas críticas en la bitácora.")


def main():
    init_session_state()

    if st.session_state.app_mode == "Estudiante":
        render_student_sidebar()
        if st.session_state.student_info is None:
            render_intake_gate()
        else:
            render_student_chat()
    else:
        render_admin_panel()


if __name__ == "__main__":
    main()
