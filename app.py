import streamlit as st
import jinja2
import os
import subprocess
import uuid
import qrcode
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mawida EtoVet", page_icon="🐾", layout="wide")

# --- CONEXIÓN A SUPABASE ---
# Intentamos conectar solo si existen los secretos
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
    CONEXION_NUBE = True
except Exception:
    st.warning("⚠️ No se detectaron las claves de Supabase en los 'Secrets'. El sistema funcionará en modo local (los QR no servirán fuera de aquí).")
    CONEXION_NUBE = False

# --- CONFIGURACIÓN LATEX ---
latex_jinja_env = jinja2.Environment(
    block_start_string='\BLOCK{', block_end_string='}',
    variable_start_string='\VAR{', variable_end_string='}',
    comment_start_string='\#{', comment_end_string='}',
    line_statement_prefix='%%', line_comment_prefix='%#',
    trim_blocks=True, autoescape=False,
    loader=jinja2.FileSystemLoader(os.path.abspath('.'))
)

# --- FUNCIONES AUXILIARES ---
def calcular_dv(rut_cuerpo):
    secuencia = [2, 3, 4, 5, 6, 7]
    acumulado = 0
    multiplicador = 0
    for d in str(rut_cuerpo)[::-1]:
        acumulado += int(d) * secuencia[multiplicador % 6]
        multiplicador += 1
    resto = acumulado % 11
    resultado = 11 - resto
    if resultado == 11: return '0'
    if resultado == 10: return 'K'
    return str(resultado)

def formatear_rut(rut_raw):
    if not rut_raw: return ""
    limpio = str(rut_raw).replace(".", "").replace("-", "").upper()
    try:
        cuerpo = int(limpio)
        dv = calcular_dv(cuerpo)
        cuerpo_fmt = "{:,}".format(cuerpo).replace(",", ".")
        return f"{cuerpo_fmt}-{dv}"
    except ValueError:
        return rut_raw 

def generar_qr(url_destino):
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(url_destino)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save("qr_temp.png")

def generar_pdf(datos):
    template = latex_jinja_env.get_template('receta_template.tex')
    with open('receta.tex', 'w') as f:
        f.write(template.render(datos))
    
    result = subprocess.run(['xelatex', '-interaction=nonstopmode', 'receta.tex'], capture_output=True, text=True)
    if result.returncode != 0:
        st.error("❌ Error de compilación LaTeX")
        st.code(result.stdout[-500:])
        raise Exception("Fallo al generar PDF")
    return 'receta.pdf'

def subir_a_supabase(archivo_local, nombre_nube):
    """Sube el PDF al bucket 'recetas' y devuelve la URL pública"""
    with open(archivo_local, 'rb') as f:
        supabase.storage.from_("recetas").upload(
            file=f,
            path=nombre_nube,
            file_options={"content-type": "application/pdf"}
        )
    # Obtenemos la URL pública
    url_publica = supabase.storage.from_("recetas").get_public_url(nombre_nube)
    return url_publica

# --- INTERFAZ ---
with st.sidebar:
    st.header("👨‍⚕️ Médico Tratante")
    medico_nombre = st.text_input("Nombre Médico", placeholder="Ej: Juan Pérez")
    medico_rut_raw = st.text_input("RUT Médico (sin puntos ni DV)", placeholder="Ej: 12345678")
    st.divider()
    if st.button("🔄 Nueva Receta"):
        st.session_state.clear()
        st.rerun()

if not os.path.exists("logo.png"):
    st.warning("⚠️ Falta 'logo.png'")
else:
    st.image("logo.png", width=120)

st.title("Recetario Digital Mawida")

# DATOS
st.subheader("1. Paciente")
c1, c2, c3 = st.columns(3)
paciente = c1.text_input("Nombre Paciente")
lista_especies = sorted(["Canino", "Felino", "Exótico", "Equino", "Bovino", "Ovino", "Caprino"])
especie = c2.selectbox("Especie", lista_especies)
peso = c3.text_input("Peso")

c4, c5 = st.columns(2)
tutor = c4.text_input("Nombre Tutor")
rut_tutor_raw = c5.text_input("RUT Tutor (sin puntos ni DV)")

# PRESCRIPCION
st.divider()
st.subheader("2. Prescripción")
if 'lista_meds' not in st.session_state: st.session_state.lista_meds = []

with st.form("form_meds", clear_on_submit=True):
    ca, cb = st.columns(2)
    f_nom = ca.text_input("Fármaco", placeholder="Ej: Amoxicilina")
    f_dos = cb.text_input("Dosis", placeholder="Ej: 500mg")
    f_fre = ca.text_input("Frecuencia", placeholder="Ej: c/8h")
    f_ind = cb.text_input("Indicaciones")
    if st.form_submit_button("➕ Agregar"):
        if f_nom:
            st.session_state.lista_meds.append({"farmaco":f_nom, "dosis":f_dos, "frecuencia":f_fre, "indicaciones":f_ind})

if st.session_state.lista_meds:
    st.table(st.session_state.lista_meds)
    if st.button("🗑️ Borrar Todo"):
        st.session_state.lista_meds = []; st.rerun()

st.divider()

# EMISIÓN
if st.button("🖨️ EMITIR DOCUMENTO OFICIAL", type="primary", use_container_width=True):
    errores = []
    if not medico_nombre: errores.append("Falta médico")
    if not paciente: errores.append("Falta paciente")
    if not st.session_state.lista_meds: errores.append("Lista vacía")
    
    if errores:
        for e in errores: st.error(f"⚠️ {e}")
    else:
        # 1. Preparar Datos
        id_unico = str(uuid.uuid4())[:8].upper()
        nombre_archivo_nube = f"Receta_{id_unico}.pdf"
        
        # 2. PREDECIR URL (Truco para el QR)
        # Si tenemos Supabase, construimos la URL real. Si no, una falsa.
        if CONEXION_NUBE:
            # Esta URL es estándar en Supabase: url_proyecto + /storage/v1/object/public/bucket/archivo
            project_url = st.secrets["supabase"]["url"]
            url_qr = f"{project_url}/storage/v1/object/public/recetas/{nombre_archivo_nube}"
        else:
            url_qr = "https://sistema-offline/verificar"

        # 3. Generar QR con esa URL
        generar_qr(url_qr)
        
        # 4. Generar PDF
        rut_med = formatear_rut(medico_rut_raw)
        rut_tut = formatear_rut(rut_tutor_raw)
        
        datos = {
            "medico_nombre": medico_nombre, "medico_rut": rut_med,
            "fecha_actual": datetime.now().strftime("%d/%m/%Y"),
            "hora_actual": datetime.now().strftime("%H:%M"),
            "paciente_nombre": paciente, "paciente_especie": especie, "paciente_peso": peso,
            "tutor_nombre": tutor, "tutor_rut": rut_tut,
            "items": st.session_state.lista_meds,
            "id_unico": id_unico,
            "url_qr": url_qr
        }
        
        try:
            with st.spinner("Firmando, Generando y Subiendo a la Nube..."):
                pdf_local = generar_pdf(datos)
                
                # 5. SUBIR A LA NUBE (Solo si hay conexión)
                if CONEXION_NUBE:
                    url_final = subir_a_supabase(pdf_local, nombre_archivo_nube)
                    msj_exito = f"✅ Receta en la Nube. Folio: {id_unico}"
                else:
                    msj_exito = f"✅ Receta Local (Sin Nube). Folio: {id_unico}"

            # 6. RESULTADO
            c1, c2 = st.columns([3, 1])
            with open(pdf_local, "rb") as f:
                c1.success(msj_exito)
                c1.download_button(f"⬇️ Descargar PDF", f, file_name=nombre_archivo_nube)
                if CONEXION_NUBE:
                    c1.markdown(f"**Link Público:** [Ver Documento en Nube]({url_qr})")
            
            c2.image("qr_temp.png", caption="Escanea para ver el PDF original")
            
        except Exception as e:
            st.error(f"Error: {e}")
