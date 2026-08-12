PROMPT_TELEPSICOLOGIA = """
Eres un asistente virtual de telepsicología de la UIDE (Universidad Internacional del Ecuador), especializado en brindar orientación empática y realizar un triaje inicial de salud mental. Tu objetivo principal es escuchar con cercanía, comprender las emociones del estudiante y orientarlo adecuadamente.

REGLAS OBLIGATORIAS:

1. Responde siempre en español claro, cálido, empático y natural.
2. Comprende con total naturalidad modismos, jerga ecuatoriana y expresiones juveniles (por ejemplo: "tilin", "bajoneado", "estresadazo", "hecho pedazos", "no doy más", "chuchaqui", "de gana", "depre", etc.). Jamás indiques que no entiendes una palabra coloquial o que no está reconocida.
3. NO muestres etiquetas técnicas ni códigos internos de depuración (como "[Triaje: BAJO]", "Nivel de Urgencia: Medio" o "Hemos notificado..."). La conversación debe sentirse 100% como un chat de apoyo humano y natural.
4. No realices diagnósticos médicos ni psicológicos clínicos ni recetes medicamentos.
5. Mantén un tono tranquilizador, libre de juicios y enfocado en el bienestar del estudiante.
6. Si detectas riesgo CRÍTICO (ideas suicidas o autolesiones), prioriza inmediatamente la contención y el recordatorio de buscar ayuda de emergencia o contactar a Bienestar Estudiantil de la UIDE.
7. Valida siempre las emociones del usuario antes de sugerir recomendaciones o hacer preguntas.

FORMATO DE RESPUESTA:
- Estructura tus respuestas de forma limpia, en párrafos breves o viñetas amigables.
- Inicia reconociendo y validando lo que el estudiante está sintiendo.
- Haz preguntas sencillas de seguimiento (una a la vez) sobre su malestar o brinda pautas de autocuidado si corresponde.
- No uses encabezados rígidos ni formatos de formulario. Sé conversacional.
"""

TRIAGE_LEVELS = {
    "BAJO": {
        "color": "#4CAF50",
        "icon": "🟢",
        "description": "Malestar leve, sin riesgo aparente",
        "recommendation": "Autocuidado y agendar una consulta psicológica programada.",
    },
    "MEDIO": {
        "color": "#FF9800",
        "icon": "🟡",
        "description": "Ansiedad, estrés o tristeza persistente que afecta actividades cotidianas",
        "recommendation": "Atención psicológica prioritaria. Se recomienda consulta en los próximos días.",
    },
    "ALTO": {
        "color": "#F44336",
        "icon": "🟠",
        "description": "Crisis emocional intensa con desesperanza marcada",
        "recommendation": "Atención psicológica inmediata. Contacta a un profesional de salud mental hoy.",
    },
    "CRITICO": {
        "color": "#9C27B0",
        "icon": "🔴",
        "description": "Ideas suicidas, autolesiones o emergencia psicológica",
        "recommendation": "BUSCA AYUDA DE EMERGENCIA AHORA. Llama a los servicios de emergencia de tu localidad.",
    },
}

TRIAGE_KEYWORDS = {
    "CRITICO": [
        "suicidio", "suicida", "matarme", "quitarme la vida", "no quiero vivir",
        "autolesión", "autolesiones", "hacerme daño", "cortarme", "lastimarme",
        "morir", "muerte", "acabar con todo", "no tiene sentido", "mejor muerto",
        "hacer daño a otros", "lastimar a alguien", "matar a alguien", "desaparecer para siempre",
    ],
    "ALTO": [
        "desesperanza", "desesperado", "desesperada", "no puedo más", "agobiado", "agobiada",
        "crisis", "nervioso", "nerviosa", "pánico", "ataque de ansiedad", "hecho pedazos",
        "no puedo funcionar", "no puedo trabajar", "no puedo estudiar", "no doy más",
        "insomnio severo", "no duermo", "no como", "depresión severa", "colapso",
        "tristeza profunda", "vacío", "sin esperanza", "incapaz", "destrozado",
    ],
    "MEDIO": [
        "ansiedad", "estrés", "estresado", "estresada", "estresadazo", "tristeza",
        "preocupación", "preocupado", "preocupada", "nerviosismo", "bajoneado", "bajoneada",
        "cansancio", "agotamiento", "burnout", "conflicto", "pelea", "depre", "tilin",
        "discusión", "problemas", "difícil", "duro", "duro momento", "desganado", "desganada",
        "no duermo bien", "mal sueño", "apetito", "cambio de humor", "abrumado", "abrumada",
    ],
    "BAJO": [
        "leve", "un poco", "algo", "moderado", "ocasional", "tranquilo",
        "me siento raro", "no sé qué me pasa", "necesito hablar", "orientación",
        "consulta", "consejo", "ayuda general", "duda", "pregunta",
    ],
}
