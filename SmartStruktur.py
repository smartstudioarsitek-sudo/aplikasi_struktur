import streamlit as st
import google.generativeai as genai
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
from PIL import Image
import PyPDF2
from io import BytesIO
import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS PRO
# ==========================================
st.set_page_config(
    page_title="ENGINEX TITAN SUITE", 
    page_icon="🏗️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling CSS "Grandmaster"
st.markdown("""
<style>
    .main-header {font-size: 32px; font-weight: 800; color: #1565C0; margin-bottom: 10px;}
    .sub-header {font-size: 18px; color: #546E7A; margin-bottom: 20px;}
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        height: 50px; white-space: pre-wrap; background-color: #F1F3F4;
        border-radius: 8px; color: #000; font-weight: 600;
        border: 1px solid #ddd;
    }
    .stTabs [aria-selected="true"] {
        background-color: #1565C0; color: #FFF; border: none;
    }

    /* Metric Box */
    .metric-box {
        background-color: #FFFFFF; border-left: 5px solid #0D47A1;
        padding: 20px; border-radius: 8px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }
    
    /* Status Boxes */
    .success-box { border-left: 5px solid #2E7D32; background-color: #E8F5E9; padding: 15px; border-radius: 5px; color: #1B5E20; font-weight: bold; }
    .danger-box { border-left: 5px solid #C62828; background-color: #FFEBEE; padding: 15px; border-radius: 5px; color: #B71C1C; font-weight: bold; }

    /* Tombol */
    .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. CORE SYSTEM: SESSION STATE
# ==========================================

# Init Data Proyek Global
if 'project_data' not in st.session_state:
    st.session_state['project_data'] = {
        'nama_proyek': 'Gedung TITAN V1',
        'lokasi': 'Jakarta Selatan',
        'fc': 25.0, 'fy': 400.0,
        'ss': 0.80, 's1': 0.40, 'site_class': 'SD',
        'gamma_tanah': 18.0, 'phi_tanah': 30.0, 'c_tanah': 5.0, 'sigma_tanah': 150.0
    }

if 'chat_history' not in st.session_state: st.session_state['chat_history'] = []
if 'api_key' not in st.session_state: st.session_state['api_key'] = ""

# --- [BARU] State untuk menyimpan daftar model dan model yang dipilih ---
if 'gemini_models_list' not in st.session_state: st.session_state['gemini_models_list'] = []
if 'selected_model_name' not in st.session_state: st.session_state['selected_model_name'] = "models/gemini-1.5-flash" # Default aman

# State untuk menyimpan hasil perhitungan (Untuk Report)
if 'calc_results' not in st.session_state:
    st.session_state['calc_results'] = {
        'struktur': {}, 'baja': {}, 'gempa': {}, 'geo': {}, 'pondasi': {}
    }

# ==========================================
# 3. ENGINEX CORE (GABUNGAN SEMUA LIBRARY)
# ==========================================
class EnginexCore:
    """
    Super Class yang menggabungkan logika SNI Beton, Baja, Gempa, Geoteknik, dan AHSP.
    """
    
    # --- A. STRUKTUR BETON (SNI 2847:2019) ---
    @staticmethod
    def hitung_tulangan_balok(Mu_kNm, b_mm, h_mm, fc, fy, ds=40):
        phi = 0.9
        d = h_mm - ds
        Mu = Mu_kNm * 1e6 # Nmm
        
        # Rumus As Perlu
        As_perlu = Mu / (phi * fy * 0.875 * d)
        
        # Cek Minimum Reinforcement
        As_min1 = (0.25 * np.sqrt(fc) / fy) * b_mm * d
        As_min2 = (1.4 / fy) * b_mm * d
        As_min = max(As_min1, As_min2)
        
        As_final = max(As_perlu, As_min)
        
        # Hitung Kapasitas Momen (Phi Mn) Check
        a = (As_final * fy) / (0.85 * fc * b_mm)
        Mn = As_final * fy * (d - a/2)
        Phi_Mn = (phi * Mn) / 1e6
        
        return As_final, Phi_Mn

    @staticmethod
    def hitung_geser_balok(Vu_kN, b_mm, h_mm, fc, fy):
        d = h_mm - 50
        Vc = 0.17 * np.sqrt(fc) * b_mm * d / 1000 # kN
        Phi_Vc = 0.75 * Vc
        
        Vs_perlu = 0
        if Vu_kN > Phi_Vc:
            Vs_perlu = (Vu_kN - Phi_Vc) / 0.75
            
        return Phi_Vc, Vs_perlu

    # --- B. BAJA STRUKTUR (SNI 1729:2015) ---
    @staticmethod
    def cek_balok_wf(Mu_kNm, Zx_cm3, Lb_m, fy):
        phi_b = 0.9
        Zx = Zx_cm3 * 1000 # mm3
        Mp = fy * Zx
        
        # Reduksi Tekuk Torsi Lateral (Simplifikasi)
        faktor_tekuk = 1.0
        if Lb_m > 2.0:
            penurunan = 0.1 * (Lb_m - 2.0)
            faktor_tekuk = max(0.6, 1.0 - penurunan)
            
        Mn = Mp * faktor_tekuk
        Phi_Mn = phi_b * Mn / 1e6 # kNm
        
        ratio = Mu_kNm / Phi_Mn if Phi_Mn > 0 else 99
        status = "AMAN" if ratio <= 1.0 else "TIDAK AMAN"
        
        return Phi_Mn, ratio, status

    @staticmethod
    def hitung_atap_baja_ringan(luas_m2, jenis_genteng):
        # Rule of thumb
        if "Metal" in jenis_genteng:
            k_c, k_reng = 0.35, 0.6
        else:
            k_c, k_reng = 0.55, 1.2
            
        btg_c = np.ceil(luas_m2 * k_c)
        btg_reng = np.ceil(luas_m2 * k_reng)
        sekrup = np.ceil((luas_m2 * 12) + (btg_c * 8) + (btg_reng * 4))
        
        return btg_c, btg_reng, sekrup

    # --- C. GEMPA (SNI 1726:2019) ---
    @staticmethod
    def hitung_base_shear(Ss, S1, site_class, W_total, R):
        # Tabel Fa Fv Sederhana
        fa_map = {'SE': 0.9 if Ss >= 1 else 2.5, 'SD': 1.1 if Ss >= 1 else 1.6, 'SC': 1.0}
        fv_map = {'SE': 2.4 if S1 >= 0.5 else 3.5, 'SD': 1.6 if S1 >= 0.5 else 2.4, 'SC': 1.0}
        
        Fa = fa_map.get(site_class, 1.0)
        Fv = fv_map.get(site_class, 1.0)
        
        Sds = (2/3) * (Fa * Ss)
        Sd1 = (2/3) * (Fv * S1)
        
        Cs = Sds / R # Asumsi Ie = 1.0
        V = Cs * W_total
        return V, Sds, Sd1

    # --- D. GEOTEKNIK & PONDASI ---
    @staticmethod
    def hitung_talud(H, b_atas, b_bawah, gamma, phi, c):
        # Rankine Active Pressure
        Ka = np.tan(np.radians(45 - phi/2))**2
        Pa = 0.5 * gamma * (H**2) * Ka
        
        # Berat Dinding (Batu Kali approx 22 kN/m3)
        W_dinding = ((b_atas + b_bawah)/2) * H * 22.0
        
        # Momen Guling & Tahan
        M_guling = Pa * (H/3)
        M_tahan = W_dinding * (b_bawah/2) # Simplifikasi lengan momen
        
        SF_guling = M_tahan / M_guling if M_guling > 0 else 99
        
        # Geser
        mu = np.tan(np.radians(2/3 * phi))
        F_geser = (W_dinding * mu) + (c * b_bawah)
        SF_geser = F_geser / Pa if Pa > 0 else 99
        
        return SF_guling, SF_geser

    @staticmethod
    def hitung_footplate(Pu, B, sigma_tanah):
        Area = B * B
        q_contact = Pu / Area
        status = "AMAN" if q_contact <= sigma_tanah else "BAHAYA"
        return q_contact, status

    # --- E. EXPORT DXF (Simple Generator) ---
    @staticmethod
    def create_dxf_content(type_draw, params):
        dxf = "0\nSECTION\n2\nENTITIES\n"
        def line(x1, y1, x2, y2, lay="0"):
            return f"0\nLINE\n8\n{lay}\n10\n{x1}\n20\n{y1}\n30\n0.0\n11\n{x2}\n21\n{y2}\n31\n0.0\n"
        def text(x, y, txt, h=0.15):
            return f"0\nTEXT\n8\nTEXT\n10\n{x}\n20\n{y}\n30\n0.0\n40\n{h}\n1\n{txt}\n"

        if type_draw == "BALOK":
            b, h = params['b']/1000, params['h']/1000
            dxf += line(0,0,b,0) + line(b,0,b,h) + line(b,h,0,h) + line(0,h,0,0) # Kotak
            dxf += text(0, -0.3, f"BALOK {int(params['b'])}x{int(params['h'])}")
            
        elif type_draw == "TALUD":
            bb, ba, H = params['bb'], params['ba'], params['H']
            dxf += line(0,0,bb,0) + line(bb,0,bb,H) + line(bb,H,bb-ba,H) + line(bb-ba,H,0,0)
            dxf += text(0, -0.3, f"TALUD H={H}m")
            
        dxf += "0\nENDSEC\n0\nEOF"
        return dxf

    # --- F. AHSP COST ESTIMATION (RAB Engine) ---
    @staticmethod
    def hitung_ahsp(kode, prices):
        # Database Koefisien Mini
        coeffs = {
            "beton_k250": {"semen": 384, "pasir": 0.494, "split": 0.77, "pekerja": 1.65, "tukang": 0.275},
            "bekisting":  {"kayu": 0.04, "paku": 0.4, "pekerja": 0.66, "tukang": 0.33},
            "pembesian":  {"besi": 10.5, "kawat": 0.15, "pekerja": 0.07, "tukang": 0.07},
            "batu_kali":  {"batu": 1.2, "semen": 163, "pasir": 0.52, "pekerja": 1.5, "tukang": 0.75}
        }
        
        if kode not in coeffs: return 0
        
        total = 0
        data = coeffs[kode]
        for item, coef in data.items():
            price = prices.get(item, 0)
            total += coef * price
        return total

# ==========================================
# 4. SIDEBAR SETUP (DENGAN MODEL SELECTOR)
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/engineer.png", width=70)
    st.title("ENGINEX TITAN")
    st.caption("AI + BIM + Structural Calculation")
    
    st.markdown("### 🔑 API Key & Model AI")
    
    # 1. Input/Cek API Key
    api_key_input = st.text_input("Google API Key:", type="password", value=st.session_state['api_key'], help="Masukkan API Key lalu tekan Enter untuk memuat daftar model.")
    
    # Jika ada input baru atau perubahan, update session state
    if api_key_input and api_key_input != st.session_state['api_key']:
        st.session_state['api_key'] = api_key_input
        # Reset daftar model agar dimuat ulang dengan key baru
        st.session_state['gemini_models_list'] = [] 

    # Cek Secrets jika input kosong
    if not st.session_state['api_key'] and "GOOGLE_API_KEY" in st.secrets:
         st.session_state['api_key'] = st.secrets["GOOGLE_API_KEY"]

    # 2. Logika Fetch Model & Dropdown
    if st.session_state['api_key']:
        try:
            # Konfigurasi cuma sekali di sini untuk fetch model
            genai.configure(api_key=st.session_state['api_key'])
            
            # Jika daftar model belum ada di memori, ambil dari Google
            if not st.session_state['gemini_models_list']:
                with st.spinner("Mengambil daftar model dari Google..."):
                    models = []
                    # Ambil semua model yg mendukung 'generateContent'
                    for m in genai.list_models():
                        if 'generateContent' in m.supported_generation_methods:
                            models.append(m.name)
                    # Sortir agar model terbaru biasanya di atas (heuristic)
                    st.session_state['gemini_models_list'] = sorted(models, reverse=True)
            
            # Tampilkan Dropdown jika daftar berhasil diambil
            if st.session_state['gemini_models_list']:
                st.success("✅ API Key Valid. Model dimuat.")
                
                # Pastikan pilihan sebelumnya masih ada di daftar baru, jika tidak reset ke index 0
                current_index = 0
                if st.session_state['selected_model_name'] in st.session_state['gemini_models_list']:
                    current_index = st.session_state['gemini_models_list'].index(st.session_state['selected_model_name'])
                
                selected_model = st.selectbox(
                    "🤖 Pilih Model Gemini:",
                    st.session_state['gemini_models_list'],
                    index=current_index,
                    help="Pilih versi model AI yang ingin digunakan. Jika satu gagal, coba yang lain."
                )
                # Simpan pilihan user ke session state
                st.session_state['selected_model_name'] = selected_model
            else:
                st.warning("API Key valid, tapi tidak ada model 'generateContent' yang ditemukan.")

        except Exception as e:
            st.error(f"Gagal memuat model. Cek API Key Anda.\nError: {e}")
            st.session_state['gemini_models_list'] = [] # Reset jika gagal
    else:
        st.info("👉 Masukkan API Key untuk melihat daftar model yang tersedia.")

    st.markdown("---")

    # Global Config Input
    with st.expander("🛠️ Konfigurasi Proyek", expanded=False):
        st.session_state['project_data']['fc'] = st.number_input("Mutu Beton (MPa)", 15.0, 60.0, 25.0)
        st.session_state['project_data']['fy'] = st.number_input("Mutu Baja (MPa)", 240.0, 550.0, 400.0)
        st.session_state['project_data']['sigma_tanah'] = st.number_input("Daya Dukung Tanah (kN/m2)", 50.0, 300.0, 150.0)

    app_mode = st.radio("Mode Aplikasi:", ["🤖 AI Consultant", "🏗️ Engineering Studio"])
    
    if st.button("🧹 Reset Data & Chat"):
        st.session_state['chat_history'] = []
        # Optional: reset model selection too if needed
        # st.session_state['gemini_models_list'] = []
        st.rerun()

# ==========================================
# 5. MODE 1: AI CONSULTANT (STREAMING EFFECT)
# ==========================================
def render_ai_consultant():
    st.markdown('<div class="main-header">🤖 AI Structural Consultant</div>', unsafe_allow_html=True)
    
    # Tampilkan info model
    if st.session_state['api_key'] and st.session_state.get('selected_model_name'):
         st.caption(f"Moda Operasi: Menggunakan Model **{st.session_state['selected_model_name']}** (High Speed)")
    
    if st.session_state['api_key']:
        try: genai.configure(api_key=st.session_state['api_key'])
        except: pass

    # --- DEFINISI PERSONA (Gunakan yang GEMS Grandmaster tadi) ---
    personas = {
        "👑 The GEMS Grandmaster (All-in-One)": """
            ANDA ADALAH "THE GEMS GRANDMASTER" (Omniscient Project Director).
            Anda adalah manifestasi kecerdasan kolektif dari 4 Ahli Terbaik:
            1. 🏗️ Ahli Struktur (Pakar SNI Beton/Baja & Gempa)
            2. 🪨 Ahli Geoteknik (Pakar Pondasi & Tanah)
            3. 💰 Ahli QS/Estimator (Pakar RAB, AHSP & Efisiensi Biaya)
            4. 👔 Project Manager (Pakar Manajemen Risiko & Metode Kerja)

            INSTRUKSI UTAMA:
            Setiap kali user bertanya, JANGAN menjawab dari satu sudut pandang saja.
            Anda WAJIB melakukan "360-Degree Analysis" dengan struktur jawaban sbb:
            
            1. 🛡️ ANALISA STRUKTUR & KEAMANAN: Jelaskan aspek teknis, dimensi, dan standar SNI yang relevan.
            2. ⛰️ TINJAUAN GEOTEKNIK: Bahas kondisi tanah, risiko guling/geser, atau jenis pondasi yang tepat.
            3. 💵 ESTIMASI BIAYA (RAB): Berikan perkiraan kasar biaya, material yang boros vs hemat, dan strategi efisiensi.
            4. 📋 METODE KERJA & REKOMENDASI FINAL: Langkah konkret di lapangan dan kesimpulan terbaik.

            Gaya Bicara: Tegas, Strategis, Holistik, dan Solutif. Hindari jawaban ragu-ragu.
        """,
        "🏗️ Ahli Struktur": "Anda adalah Ahli Struktur Senior...",
        "🪨 Ahli Geoteknik": "Anda adalah Geotechnical Engineer...",
        "💰 Ahli RAB": "Anda adalah Quantity Surveyor..."
    }
    
    c1, c2 = st.columns([1, 2])
    with c1: selected_persona = st.selectbox("Pilih Ahli:", list(personas.keys()))
    with c2: uploaded_files = st.file_uploader("Upload Data (Gambar/PDF):", accept_multiple_files=True)

    # Chat History Container
    chat_container = st.container()
    with chat_container:
        for chat in st.session_state['chat_history']:
            with st.chat_message(chat['role']): st.markdown(chat['content'])

    # Input User
    prompt = st.chat_input("Konsultasikan proyek Anda di sini...")
    
    if prompt:
        if not st.session_state['api_key']:
            st.error("⛔ API Key belum dimasukkan!"); return
        if not st.session_state.get('selected_model_name'):
             st.error("⛔ Model belum dimuat. Tunggu sebentar..."); return

        # 1. Tampilkan Chat User
        with st.chat_message("user"): st.markdown(prompt)
        st.session_state['chat_history'].append({"role": "user", "content": prompt})
        
        # 2. Respon AI dengan Efek Mengetik
        with st.chat_message("assistant"):
            try:
                target_model_name = st.session_state['selected_model_name']
                model = genai.GenerativeModel(target_model_name, system_instruction=personas[selected_persona])
                
                content = [prompt]
                if uploaded_files:
                    for f in uploaded_files:
                        if f.type.startswith('image'): content.append(Image.open(f))
                        elif f.type == 'application/pdf':
                            pdf = PyPDF2.PdfReader(f)
                            text = "".join([p.extract_text() for p in pdf.pages])
                            content.append(f"Isi PDF: {text[:2000]}")
                
                # --- LOGIKA STREAMING (KUNCI EFEK MENGETIK) ---
                # Tambahkan stream=True
                response_stream = model.generate_content(content, stream=True)
                
                # Fungsi Generator untuk Streamlit
                def stream_data():
                    for chunk in response_stream:
                        if chunk.text:
                            yield chunk.text
                
                # st.write_stream akan merender teks seolah diketik
                # dan mengembalikan teks full di akhir
                full_response = st.write_stream(stream_data)
                
                # Simpan jawaban lengkap ke memori
                st.session_state['chat_history'].append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                err_msg = str(e)
                if "404" in err_msg: st.error("Model tidak ditemukan. Ganti model di sidebar.")
                else: st.error(f"Error AI: {err_msg}")
# ==========================================
# 6. MODE 2: ENGINEERING STUDIO (TITAN)
# ==========================================
def render_engineering_studio():
    st.markdown('<div class="main-header">🏗️ Engineering Studio (TITAN)</div>', unsafe_allow_html=True)
    
    tabs = st.tabs([
        "1. Struktur Beton", "2. Struktur Baja", "3. Analisa Gempa", 
        "4. Geoteknik & Pondasi", "5. RAB & Report"
    ])
    
    data = st.session_state['project_data']
    
    # --- TAB 1: BETON ---
    with tabs[0]:
        st.subheader("Analisa Balok Beton (SNI 2847)")
        c1, c2 = st.columns(2)
        with c1:
            b = st.number_input("Lebar (mm)", 150, 1000, 300)
            h = st.number_input("Tinggi (mm)", 200, 2000, 600)
            Mu = st.number_input("Momen Ultimate (kNm)", 10.0, 2000.0, 150.0)
            Vu = st.number_input("Geser Ultimate (kN)", 10.0, 1000.0, 100.0)
        with c2:
            As, Phi_Mn = EnginexCore.hitung_tulangan_balok(Mu, b, h, data['fc'], data['fy'])
            Phi_Vc, Vs = EnginexCore.hitung_geser_balok(Vu, b, h, data['fc'], data['fy'])
            
            st.metric("Tulangan Perlu (As)", f"{As:.2f} mm2")
            n_d16 = np.ceil(As / (0.25*3.14*16**2))
            st.info(f"Rekomendasi: **{int(n_d16)} D16**")
            
            if Vu > Phi_Vc: st.warning(f"Perlu Sengkang! Vs = {Vs:.1f} kN")
            else: st.success("Geser Aman (Sengkang Praktis)")
            
            # DXF Export
            dxf = EnginexCore.create_dxf_content("BALOK", {'b': b, 'h': h})
            st.download_button("📥 Download DXF Balok", dxf, "balok.dxf")
            
            # Save for report
            st.session_state['calc_results']['struktur'] = {'b': b, 'h': h, 'As': As, 'Mu': Mu}

    # --- TAB 2: BAJA ---
    with tabs[1]:
        st.subheader("Struktur Baja (SNI 1729) & Atap")
        t1, t2 = st.tabs(["Balok WF", "Atap Ringan"])
        
        with t1:
            c1, c2 = st.columns(2)
            with c1:
                mu_baja = st.number_input("Momen (kNm)", 10.0, 500.0, 50.0, key="mu_baja")
                lb_baja = st.number_input("Panjang Bentang (m)", 1.0, 20.0, 6.0)
                pilih_wf = st.selectbox("Profil WF", ["WF 200x100 (Zx=213)", "WF 300x150 (Zx=481)", "WF 400x200 (Zx=1190)"])
                zx_map = {"WF 200x100 (Zx=213)": 213, "WF 300x150 (Zx=481)": 481, "WF 400x200 (Zx=1190)": 1190}
            with c2:
                phi_mn, ratio, status = EnginexCore.cek_balok_wf(mu_baja, zx_map[pilih_wf], lb_baja, 240)
                st.metric("Ratio Kapasitas", f"{ratio:.3f}", status)
                if status == "AMAN": st.balloons()
        
        with t2:
            luas_atap = st.number_input("Luas Atap (m2)", 20.0, 500.0, 100.0)
            genteng = st.radio("Jenis Genteng", ["Metal Pasir", "Keramik"])
            c, r, s = EnginexCore.hitung_atap_baja_ringan(luas_atap, genteng)
            st.info(f"Kebutuhan: Kanal C {int(c)} btg, Reng {int(r)} btg, Sekrup {int(s)} pcs")

    # --- TAB 3: GEMPA ---
    with tabs[2]:
        st.subheader("Analisa Gempa (SNI 1726)")
        c1, c2 = st.columns(2)
        with c1:
            ss = st.number_input("Ss", 0.0, 3.0, data['ss'])
            s1 = st.number_input("S1", 0.0, 2.0, data['s1'])
            site = st.selectbox("Kelas Situs", ["SE", "SD", "SC"])
        with c2:
            wt = st.number_input("Berat Bangunan (kN)", 100.0, 10000.0, 2000.0)
            V, sds, sd1 = EnginexCore.hitung_base_shear(ss, s1, site, wt, 8.0)
            st.metric("Base Shear (V)", f"{V:.2f} kN")
            st.write(f"SDS: {sds:.3f}, SD1: {sd1:.3f}")

    # --- TAB 4: GEOTEKNIK ---
    with tabs[3]:
        st.subheader("Dinding Penahan & Pondasi")
        t_geo1, t_geo2 = st.tabs(["Talud (Retaining Wall)", "Footplate"])
        
        with t_geo1:
            c1, c2 = st.columns(2)
            with c1:
                H_talud = st.number_input("Tinggi Talud (m)", 2.0, 8.0, 3.0)
                bb = st.number_input("Lebar Bawah (m)", 1.0, 5.0, 1.5)
                ba = st.number_input("Lebar Atas (m)", 0.3, 1.0, 0.4)
            with c2:
                sf_gul, sf_ges = EnginexCore.hitung_talud(H_talud, ba, bb, data['gamma_tanah'], data['phi_tanah'], data['c_tanah'])
                st.write(f"SF Guling: {sf_gul:.2f} (Target > 1.5)")
                st.write(f"SF Geser: {sf_ges:.2f} (Target > 1.5)")
                if sf_gul > 1.5 and sf_ges > 1.5: st.success("Talud AMAN")
                else: st.error("Talud BAHAYA")
                
                # Download DXF Talud
                dxf_talud = EnginexCore.create_dxf_content("TALUD", {'bb': bb, 'ba': ba, 'H': H_talud})
                st.download_button("📥 DXF Talud", dxf_talud, "talud.dxf")

        with t_geo2:
            Pu_pond = st.number_input("Beban Aksial (kN)", 50.0, 1000.0, 150.0)
            B_pond = st.number_input("Lebar Pondasi (m)", 0.5, 3.0, 1.0)
            q_contact, stat_pond = EnginexCore.hitung_footplate(Pu_pond, B_pond, data['sigma_tanah'])
            st.metric("Tegangan Tanah", f"{q_contact:.1f} kN/m2", stat_pond)

    # --- TAB 5: RAB & REPORT ---
    with tabs[4]:
        st.subheader("RAB Cepat & Laporan")
        
        # Input Harga
        with st.expander("Update Harga Satuan"):
            c1, c2 = st.columns(2)
            prices = {}
            with c1:
                prices['semen'] = st.number_input("Harga Semen (/kg)", 1500)
                prices['pasir'] = st.number_input("Harga Pasir (/m3)", 250000)
                prices['batu'] = st.number_input("Harga Batu Kali (/m3)", 280000)
                prices['besi'] = st.number_input("Harga Besi (/kg)", 14000)
            with c2:
                prices['pekerja'] = st.number_input("Upah Pekerja (/hr)", 120000)
                prices['tukang'] = st.number_input("Upah Tukang (/hr)", 150000)
        
        # Hitung Volume Dummy (Bisa diambil dari hasil hitungan sebelumnya)
        vol_beton = 5.0 # m3
        vol_talud = 10.0 # m3
        
        hsp_beton = EnginexCore.hitung_ahsp("beton_k250", prices)
        hsp_talud = EnginexCore.hitung_ahsp("batu_kali", prices)
        
        df_rab = pd.DataFrame([
            {"Item": "Beton Struktur K-250", "Vol": vol_beton, "Hrg Sat": hsp_beton, "Total": vol_beton*hsp_beton},
            {"Item": "Talud Batu Kali", "Vol": vol_talud, "Hrg Sat": hsp_talud, "Total": vol_talud*hsp_talud}
        ])
        
        st.dataframe(df_rab, use_container_width=True)
        st.success(f"Total Estimasi: Rp {df_rab['Total'].sum():,.0f}")
        
        # GENERATE EXCEL REPORT
        if st.button("📊 Generate Laporan Excel"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet RAB
                df_rab.to_excel(writer, sheet_name='RAB', index=False)
                
                # Sheet Teknis
                df_tek = pd.DataFrame(data.items(), columns=['Parameter', 'Nilai'])
                df_tek.to_excel(writer, sheet_name='Data Teknis', index=False)
                
            val = output.getvalue()
            st.download_button("📥 Download Excel Lengkap", val, "Laporan_Titan.xlsx")

# ==========================================
# 7. MAIN ROUTING
# ==========================================
if app_mode == "🤖 AI Consultant":
    render_ai_consultant()
else:
    render_engineering_studio()

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #aaa; font-size: 12px;">
    ENGINEX TITAN SUITE v10.1 | AI Model Selector Enabled <br>
    Integrated by The Enginex Architect | © 2026
</div>
""", unsafe_allow_html=True)
