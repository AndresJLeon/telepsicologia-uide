import re
from typing import Tuple


def validar_cedula_ecuador(cedula: str) -> Tuple[bool, str]:
    """
    Valida un número de cédula de identidad de Ecuador utilizando el algoritmo Módulo 10.
    Retorna una tupla (es_valido, mensaje_error_o_exito).
    """
    if not cedula:
        return False, "La cédula es obligatoria."

    cedula_limpia = str(cedula).strip()

    if not cedula_limpia.isdigit():
        return False, "La cédula solo debe contener números."

    if len(cedula_limpia) != 10:
        return False, "La cédula debe tener exactamente 10 dígitos numéricos."

    # Validar código de provincia (dos primeros dígitos: 01-24 o 30 para residentes en el exterior)
    provincia = int(cedula_limpia[:2])
    if not ((1 <= provincia <= 24) or provincia == 30):
        return False, "El código de provincia (dos primeros dígitos) no es válido en Ecuador."

    # Validar tercer dígito (debe ser menor a 6 para personas naturales)
    tercer_digito = int(cedula_limpia[2])
    if tercer_digito >= 6:
        return False, "El tercer dígito debe ser menor a 6 para personas naturales."

    # Algoritmo Módulo 10 para el dígito verificador (décimo dígito)
    coeficientes = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    suma = 0

    for i in range(9):
        multiplicacion = int(cedula_limpia[i]) * coeficientes[i]
        if multiplicacion >= 10:
            multiplicacion -= 9
        suma += multiplicacion

    digito_verificador_calculado = (10 - (suma % 10)) % 10
    digito_verificador_real = int(cedula_limpia[9])

    if digito_verificador_calculado != digito_verificador_real:
        return False, "Número de cédula inválido (el dígito verificador no coincide)."

    return True, "Cédula ecuatoriana válida."


def validar_email_uide(email: str) -> Tuple[bool, str]:
    """
    Valida que el correo sea una dirección válida y pertenezca al dominio @uide.edu.ec.
    """
    if not email:
        return False, "El correo institucional es obligatorio."

    email_limpio = str(email).strip().lower()

    if not email_limpio.endswith("@uide.edu.ec"):
        return False, "El correo debe tener dominio institucional @uide.edu.ec (ej. usuario@uide.edu.ec)."

    if email_limpio.count("@") != 1 or len(email_limpio.split("@")[0].strip()) == 0:
        return False, "Formato de correo no válido."

    return True, "Correo UIDE válido."


def validar_nombre(nombre: str) -> Tuple[bool, str]:
    """
    Valida que el nombre solo contenga letras y espacios.
    """
    if not nombre:
        return False, "El nombre completo es obligatorio."

    nombre_limpio = str(nombre).strip()

    if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$", nombre_limpio):
        return False, "El nombre solo debe contener letras y espacios (sin números ni caracteres especiales)."

    if len(nombre_limpio) < 3:
        return False, "El nombre debe tener al menos 3 caracteres."

    return True, "Nombre válido."
