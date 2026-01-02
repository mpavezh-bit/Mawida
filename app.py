import streamlit as st
import jinja2
import os
import subprocess
import uuid
import qrcode
from datetime import datetime

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
    
    # Ejecutamos XeLaTeX (Debe estar instalado en el sistema)
    subprocess.run(['xelatex', '-interaction=nonstopmode', 'receta.tex'], check=True)
    return 'receta.pdf'

# --- INTERFAZ BARRA LATERAL ---
with st.sidebar:
    st.header("👨‍⚕️ Médico Tratante")
    # En el futuro, esto puede venir de una base de datos o login
    medico_nombre = st.text_input("Nombre", "Juan Pérez")
    medico_rut = st.text_input("RUT", "12.345.678-9")
    
    st.divider()
    if st.button("🔄 Nueva Receta (Limpiar)", type="secondary"):
        st.session_state.clear()
        st.rerun()

# --- CUERPO PRINCIPAL ---
# Verificamos si existe el logo, si no, mostramos advertencia
if not os.path.exists("logo.png"):
    st.warning("⚠️ Falta el archivo 'logo.png' en la carpeta del proyecto.")
else:
    st.image("logo.png", width=100)

st.title("Recetario Digital Mawida")

# 1. Datos del Paciente
st.subheader("1. Identificación del Paciente")
c1, c2, c3 = st.columns(3)
paciente = c1.text_input("Nombre Paciente", "Luna")
especie = c2.selectbox("Especie", ["Canino", "Felino", "Exótico", "Equino"])
peso = c3.text_input("Peso (kg)", "25")

c4, c5 = st.columns(2)
tutor = c4.text_input("Nombre Tutor", "Ana González")
rut_tutor = c5.text_input("RUT Tutor", "11.222.333-4")

# 2. Medicamentos
st.divider()
st.subheader("2. Prescripción Médica")

if 'lista_meds' not in st.session_state:
    st.session_state.lista_meds = []

with st.form("form_medicamentos", clear_on_submit=True):
    col_a, col_b = st.columns([1, 1])
    f_nombre = col_a.text_input("Fármaco / Principio Activo")
    f_dosis = col_b.text_input("Dosis (Ej: 10mg)")
    f_frec = col_a.text_input("Frecuencia (Ej: c/12 hrs)")
    f_notas = col_b.text_input("Indicaciones (Ej: con comida)")
    
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

# Tabla de revisión
if len(st.session_state.lista_meds) > 0:
    st.table(st.session_state.lista_meds)
    if st.button("🗑️ Borrar Todo"):
        st.session_state.lista_meds = []
        st.rerun()

st.divider()

# 3. Emisión
if st.button("🖨️ EMITIR DOCUMENTO OFICIAL", type="primary", use_container_width=True):
    if not st.session_state.lista_meds:
        st.error("⚠️ La lista de medicamentos está vacía.")
    else:
        # Generación de IDs
        id_unico = str(uuid.uuid4())[:8].upper()
        fecha_hora = datetime.now()
        
        # URL Temporal (Luego la conectaremos a la base de datos real)
        url_validacion = f"https://mawida-etovet.streamlit.app/verificar?id={id_unico}"
        
        # Generamos QR
        generar_qr(url_validacion)
        
        datos_pdf = {
            "medico_nombre": medico_nombre,
            "medico_rut": medico_rut,
            "fecha_actual": fecha_hora.strftime("%d/%m/%Y"),
            "hora_actual": fecha_hora.strftime("%H:%M"),
            "paciente_nombre": paciente,
            "paciente_especie": especie,
            "paciente_peso": peso,
            "tutor_nombre": tutor,
            "tutor_rut": rut_tutor,
            "items": st.session_state.lista_meds,
            "id_unico": id_unico,
            "url_qr": url_validacion
        }
        
        try:
            with st.spinner("Firmando digitalmente y generando PDF..."):
                pdf_file = generar_pdf(datos_pdf)
            
            # Éxito
            c_exito1, c_exito2 = st.columns([3, 1])
            
            with open(pdf_file, "rb") as f:
                c_exito1.success(f"✅ Receta Generada Exitosamente. Folio: {id_unico}")
                c_exito1.download_button(
                    label=f"⬇️ Descargar PDF (Folio {id_unico})",
                    data=f,
                    file_name=f"Receta_{paciente}_{id_unico}.pdf",
                    mime="application/pdf"
                )
            
            c_exito2.image("qr_temp.png", caption="QR Generado", width=120)
            
        except Exception as e:
            st.error(f"Error al generar PDF: {e}")
            st.error("Verifique que 'packages.txt' esté instalado correctamente en el servidor.")