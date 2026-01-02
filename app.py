import streamlit as st
import jinja2
import os
import subprocess
import uuid
import qrcode
import time
from datetime import datetime
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Mawida EtoVet", page_icon="🐾", layout="wide")

# ==========================================
# 🔐 SISTEMA DE LOGIN (EL PORTERO)
# ==========================================
def check_password():
    """Retorna True si el usuario ya inició sesión correctamente"""
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        # Pantalla de Login
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title("🔐 Acceso Restringido")
            if os.path.exists("logo.png"):
                st.image("logo.png", width=150)
            
            usuario = st.text_input("Usuario")
            contra = st.text_input("Contraseña", type="password")
            
            if st.button("Ingresar", type="primary"):
                # Verificamos contra los Secrets
                # Usamos try/except por si olvidó poner los secrets
                try:
                    sec_user = st.secrets["acceso"]["usuario"]
                    sec_pass = st.secrets["acceso"]["password"]
                    
                    if usuario == sec_user and contra == sec_pass:
                        st.session_state.logged_in = True
                        st.success("Acceso Correcto. Cargando...")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Credenciales incorrectas")
                except Exception:
                    st.error("⚠️ Error: No se han configurado las claves en 'Secrets'.")
        
        # DETIENE TODO AQUÍ SI NO ESTÁ LOGUEADO
        st.stop() 

# EJECUTAMOS EL PORTERO ANTES DE NADA
check_password()

# ==========================================
# 🚀 APLICACIÓN PRINCIPAL (Solo carga si pasó el login)
# ==========================================

# CONEXIÓN SUPABASE
try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    supabase: Client = create_client(url, key)
    CONEXION_NUBE = True
except Exception:
    st.warning("⚠️ Sin conexión a Nube (Supabase no configurado). Modo Offline.")
    CONEXION_NUBE = False

# LATEX ENV
latex_jinja_env = jinja2.Environment(
    block_start_string='\BLOCK{', block_end_string='}',
    variable_start_string='\VAR{', variable_end_string='}',
    comment_start_string='\#{', comment_end_string='}',
    line_statement_prefix='%%', line_comment_prefix='%#',
    trim_blocks=True, autoescape=False,
    loader=jinja2.FileSystemLoader(os.path.abspath('.'))
)

# --- FUNCIONES ---
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
        st.error("❌ Error LaTeX")
        st.code(result.stdout[-500:])
        raise Exception("Fallo al generar PDF")
    return 'receta.pdf'

def subir_a_supabase(archivo_local, nombre_nube):
    with open(archivo_local, 'rb') as f:
        supabase.storage.from_("recetas").upload(file=f, path=nombre_nube, file_options={"content-type": "application/pdf"})
    return supabase.storage.from_("recetas").get_public_url(nombre_nube)

def guardar_en_bitacora(datos_db):
    try:
        supabase.table("historial_recetas").insert(datos_db).execute()
    except Exception as e:
        st.error(f"Error guardando datos en bitácora: {e}")

# --- INTERFAZ DE BARRA LATERAL ---
with st.sidebar:
    # Botón de Salir (Logout)
    if st.button("🔒 Cerrar Sesión", type="primary"):
        st.session_state.logged_in = False
        st.rerun()
    
    st.divider()
    st.header("👨‍⚕️ Médico")
    medico_nombre = st.text_input("Nombre", placeholder="Ej: Juan Pérez")
    medico_rut_raw = st.text_input("RUT (sin puntos/DV)", placeholder="Ej: 12345678")
    
    st.divider()
    if st.button("🔄 Nueva Receta"):
        st.session_state.lista_meds = []
        st.rerun()

# --- CUERPO PRINCIPAL ---
if not os.path.exists("logo.png"): st.warning("Falta logo.png")
else: st.image("logo.png", width=120)

st.title("Recetario Digital Mawida")

# DATOS
c1, c2, c3 = st.columns(3)
paciente = c1.text_input("Paciente")
especie = c2.selectbox("Especie", sorted(["Canino", "Felino", "Exótico", "Equino", "Bovino", "Ovino", "Caprino"]))
peso = c3.text_input("Peso")

c4, c5 = st.columns(2)
tutor = c4.text_input("Tutor")
rut_tutor_raw = c5.text_input("RUT Tutor (sin puntos/DV)")

st.divider()
if 'lista_meds' not in st.session_state: st.session_state.lista_meds = []

with st.form("meds", clear_on_submit=True):
    ca, cb = st.columns(2)
    f_nom = ca.text_input("Fármaco")
    f_dos = cb.text_input("Dosis")
    f_fre = ca.text_input("Frecuencia")
    f_ind = cb.text_input("Indicaciones")
    if st.form_submit_button("➕ Agregar"):
        if f_nom: st.session_state.lista_meds.append({"farmaco":f_nom, "dosis":f_dos, "frecuencia":f_fre, "indicaciones":f_ind})

if st.session_state.lista_meds:
    st.table(st.session_state.lista_meds)
    if st.button("🗑️ Borrar"): st.session_state.lista_meds = []; st.rerun()

st.divider()

# EMISIÓN
if st.button("🖨️ EMITIR OFICIAL", type="primary", use_container_width=True):
    if not medico_nombre or not paciente or not st.session_state.lista_meds:
        st.error("⚠️ Faltan datos (Médico, Paciente o Medicamentos)")
    else:
        id_unico = str(uuid.uuid4())[:8].upper()
        nombre_pdf = f"Receta_{id_unico}.pdf"
        
        # URL
        if CONEXION_NUBE:
            # Construimos URL manual para el QR
            url_qr = f"{st.secrets['supabase']['url']}/storage/v1/object/public/recetas/{nombre_pdf}"
        else:
            url_qr = "offline"

        generar_qr(url_qr)
        
        rut_med = formatear_rut(medico_rut_raw)
        rut_tut = formatear_rut(rut_tutor_raw)
        
        datos_pdf = {
            "medico_nombre": medico_nombre, "medico_rut": rut_med,
            "fecha_actual": datetime.now().strftime("%d/%m/%Y"),
            "hora_actual": datetime.now().strftime("%H:%M"),
            "paciente_nombre": paciente, "paciente_especie": especie, "paciente_peso": peso,
            "tutor_nombre": tutor, "tutor_rut": rut_tut,
            "items": st.session_state.lista_meds,
            "id_unico": id_unico, "url_qr": url_qr
        }
        
        try:
            with st.spinner("Procesando..."):
                pdf_local = generar_pdf(datos_pdf)
                
                if CONEXION_NUBE:
                    subir_a_supabase(pdf_local, nombre_pdf)
                    
                    datos_db = {
                        "folio_unico": id_unico,
                        "medico_nombre": medico_nombre,
                        "medico_rut": rut_med,
                        "paciente_nombre": paciente,
                        "paciente_especie": especie,
                        "tutor_nombre": tutor,
                        "tutor_rut": rut_tut,
                        "url_pdf": url_qr,
                        "detalle_medicamentos": st.session_state.lista_meds 
                    }
                    guardar_en_bitacora(datos_db)

            c1, c2 = st.columns([3, 1])
            with open(pdf_local, "rb") as f:
                c1.success(f"✅ Receta Generada. Folio: {id_unico}")
                c1.download_button("⬇️ Descargar PDF", f, file_name=nombre_pdf)
            c2.image("qr_temp.png", width=100)
            
        except Exception as e:
            st.error(f"Error: {e}")
