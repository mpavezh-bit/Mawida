import streamlit as st
import jinja2
import os
import subprocess
import uuid
import qrcode
from datetime import datetime

# --- FUNCIONES DE AYUDA (RUT CHILENO) ---
def calcular_dv(rut_cuerpo):
    """Calcula el dígito verificador usando Módulo 11"""
    secuencia = [2, 3, 4, 5, 6, 7]
    acumulado = 0
    multiplicador = 0
    
    # Invertimos el rut para recorrerlo de derecha a izquierda
    for d in str(rut_cuerpo)[::-1]:
        acumulado += int(d) * secuencia[multiplicador % 6]
        multiplicador += 1
    
    resto = acumulado % 11
    resultado = 11 - resto
    
    if resultado == 11: return '0'
    if resultado == 10: return 'K'
    return str(resultado)

def formatear_rut(rut_raw):
    """Recibe '12345678' y devuelve '12.345.678-5'"""
    if not rut_raw: return ""
    limpio = str(rut_raw).replace(".", "").replace("-", "").upper()
    
    try:
        cuerpo = int(limpio)
        dv = calcular_dv(cuerpo)
        # Formato con puntos
        cuerpo_fmt = "{:,}".format(cuerpo).replace(",", ".")
        return f"{cuerpo_fmt}-{dv}"
    except ValueError:
        return rut_raw 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Mawida EtoVet",
    page_icon="🐾",
    layout="wide"
)

# --- CONFIGURACIÓN LATEX ---
latex_jinja_env = jinja2.Environment(
    block_start_string='\BLOCK{', block_end_string='}',
    variable_start_string='\VAR{', variable_end_string='}',
    comment_start_string='\#{', comment_end_string='}',
    line_statement_prefix='%%', line_comment_prefix='%#',
    trim_blocks=True, autoescape=False,
    loader=jinja2.FileSystemLoader(os.path.abspath('.'))
)

def generar_qr(url_verificacion):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url_verificacion)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qr_temp.png")

def generar_pdf(datos):
    template = latex_jinja_env.get_template('receta_template.tex')
    with open('receta.tex', 'w') as f:
        f.write(template.render(datos))
    
    # Ejecutamos XeLaTeX
    result = subprocess.run(
        ['xelatex', '-interaction=nonstopmode', 'receta.tex'], 
        capture_output=True, 
        text=True
    )
    
    if result.returncode != 0:
        st.error("❌ Error de compilación LaTeX:")
        st.code(result.stdout[-800:]) # Muestra el error si falla
        raise Exception("Error al generar PDF")
        
    return 'receta.pdf'

# --- INTERFAZ BARRA LATERAL ---
with st.sidebar:
    st.header("👨‍⚕️ Médico Tratante")
    medico_nombre = st.text_input("Nombre Médico", placeholder="Ej: Juan Pérez")
    # CORRECCIÓN 1: Etiqueta precisa
    medico_rut_raw = st.text_input("RUT Médico (sin puntos ni dígito verificador)", placeholder="Ej: 12345678")
    
    st.divider()
    if st.button("🔄 Nueva Receta (Limpiar)", type="secondary"):
        st.session_state.clear()
        st.rerun()

# --- CUERPO PRINCIPAL ---
if not os.path.exists("logo.png"):
    st.warning("⚠️ Falta 'logo.png'.")
else:
    st.image("logo.png", width=120)

st.title("Recetario Digital Mawida")

# 1. Datos del Paciente
st.subheader("1. Identificación del Paciente")
c1, c2, c3 = st.columns(3)
paciente = c1.text_input("Nombre Paciente", placeholder="Ej: Luna")

# CORRECCIÓN 2: Lista Alfabética
lista_especies = sorted(["Canino", "Felino", "Exótico", "Equino", "Bovino", "Ovino", "Caprino"])
especie = c2.selectbox("Especie", lista_especies)

peso = c3.text_input("Peso", placeholder="Ej: 25 kg")

c4, c5 = st.columns(2)
tutor = c4.text_input("Nombre Tutor", placeholder="Ej: Ana González")
# CORRECCIÓN 1: Etiqueta precisa
rut_tutor_raw = c5.text_input("RUT Tutor (sin puntos ni dígito verificador)", placeholder="Ej: 13904156")

# 2. Medicamentos
st.divider()
st.subheader("2. Prescripción Médica")

if 'lista_meds' not in st.session_state:
    st.session_state.lista_meds = []

with st.form("form_medicamentos", clear_on_submit=True):
    col_a, col_b = st.columns([1, 1])
    f_nombre = col_a.text_input("Fármaco", placeholder="Ej: Fluoxetina 20mg")
    f_dosis = col_b.text_input("Dosis", placeholder="Ej: 1 comprimido")
    f_frec = col_a.text_input("Frecuencia", placeholder="Ej: c/24 hrs por 5 días")
    f_notas = col_b.text_input("Indicaciones", placeholder="Ej: Dar con comida")
    
    if st.form_submit_button("➕ Agregar Medicamento"):
        if f_nombre:
            st.session_state.lista_meds.append({
                "farmaco": f_nombre,
                "dosis": f_dosis,
                "frecuencia": f_frec,
                "indicaciones": f_notas
            })
        else:
            st.warning("Debe escribir el nombre del fármaco")

if len(st.session_state.lista_meds) > 0:
    st.table(st.session_state.lista_meds)
    if st.button("🗑️ Borrar Todo"):
        st.session_state.lista_meds = []
        st.rerun()

st.divider()

# 3. Emisión
if st.button("🖨️ EMITIR DOCUMENTO OFICIAL", type="primary", use_container_width=True):
    errores = []
    if not medico_nombre: errores.append("Falta el nombre del médico")
    if not paciente: errores.append("Falta el nombre del paciente")
    if not st.session_state.lista_meds: errores.append("La lista de medicamentos está vacía")
    
    if errores:
        for e in errores:
            st.error(f"⚠️ {e}")
    else:
        # Calcular DVs y formatear
        rut_medico_fmt = formatear_rut(medico_rut_raw)
        rut_tutor_fmt = formatear_rut(rut_tutor_raw)
        
        id_unico = str(uuid.uuid4())[:8].upper()
        fecha_hora = datetime.now()
        
        # URL Temporal
        url_validacion = f"https://mawida-etovet.streamlit.app/verificar?id={id_unico}"
        generar_qr(url_validacion)
        
        datos_pdf = {
            "medico_nombre": medico_nombre,
            "medico_rut": rut_medico_fmt,
            "fecha_actual": fecha_hora.strftime("%d/%m/%Y"),
            "hora_actual": fecha_hora.strftime("%H:%M"),
            "paciente_nombre": paciente,
            "paciente_especie": especie,
            "paciente_peso": peso,
            "tutor_nombre": tutor,
            "tutor_rut": rut_tutor_fmt,
            "items": st.session_state.lista_meds,
            "id_unico": id_unico,
            "url_qr": url_validacion
        }
        
        try:
            with st.spinner("Firmando digitalmente..."):
                pdf_file = generar_pdf(datos_pdf)
            
            c_exito1, c_exito2 = st.columns([3, 1])
            with open(pdf_file, "rb") as f:
                c_exito1.success(f"✅ Receta Generada. Folio: {id_unico}")
                c_exito1.download_button(
                    label=f"⬇️ Descargar PDF",
                    data=f,
                    file_name=f"Receta_{paciente}_{id_unico}.pdf",
                    mime="application/pdf"
                )
            c_exito2.image("qr_temp.png", caption="QR Verificación", width=100)
            
        except Exception as e:
            # El error detallado ya se muestra en generar_pdf
            pass
