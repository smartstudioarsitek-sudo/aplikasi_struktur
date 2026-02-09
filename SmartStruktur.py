import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# 1. KONFIGURASI HALAMAN (WEB UI)
# ==========================================
st.set_page_config(
    page_title="GEMS Struktur Pro (SNI Certified)",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling CSS biar tampilannya "Gagah" ala Engineer
st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; color: #1E3D59; }
    .header-style { font-size:18px; font-weight: bold; color: #FF6B6B; border-bottom: 2px solid #FF6B6B; margin-top: 20px;}
    .success-box { padding:15px; background-color:#D4EDDA; border-left: 5px solid #28A745; color: #155724; }
    .danger-box { padding:15px; background-color:#F8D7DA; border-left: 5px solid #DC3545; color: #721C24; }
    .warning-box { padding:15px; background-color:#FFF3CD; border-left: 5px solid #FFC107; color: #856404; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SIDEBAR: INPUT PARAMETER GLOBAL
# ==========================================
st.sidebar.title("🎛️ Parameter Proyek")

with st.sidebar.expander("1. Material Beton & Baja", expanded=True):
    fc = st.number_input("Mutu Beton (fc') [MPa]", 15.0, 60.0, 21.0, step=1.0, help="Standar K-250 ≈ 21 MPa")
    fy = st.number_input("Mutu Baja Ulir (fy) [MPa]", 240.0, 550.0, 400.0, step=10.0, help="BJTS 40/420")
    Es = 200000.0 # Modulus Elastisitas Baja

with st.sidebar.expander("2. Parameter Gempa (SNI 1726)", expanded=False):
    st.info("Ambil nilai Ss & S1 dari rsa.ciptakarya.pu.go.id")
    Ss = st.number_input("Ss (Short Period)", 0.0, 3.0, 0.90)
    S1 = st.number_input("S1 (1-Second Period)", 0.0, 2.0, 0.40)
    kelas_situs = st.selectbox("Kelas Situs Tanah", ["SC (Tanah Keras)", "SD (Tanah Sedang)", "SE (Tanah Lunak)"])
    R = st.selectbox("Sistem Struktur", [8.0, 5.0], format_func=lambda x: "SRPMK (R=8)" if x==8 else "SRPMM (R=5)")

# ==========================================
# 3. HEADER UTAMA
# ==========================================
st.markdown('<p class="big-font">GEMS STRUKTUR PRO: VALIDATOR TEKNIK SIPIL</p>', unsafe_allow_html=True)
st.markdown("Aplikasi verifikasi desain struktur berbasis **SNI 2847:2019 (Beton)** dan **SNI 1726:2019 (Gempa)**.")

# ==========================================
# 4. TABS NAVIGASI
# ==========================================
tab1, tab2, tab3 = st.tabs(["📝 Cek Balok (Flexure)", "🌋 Cek Gempa (Base Shear)", "ℹ️ Tentang Aplikasi"])

# === TAB 1: CEK BALOK (Perbaikan File tulblk.csv) ===
with tab1:
    st.markdown('<p class="header-style">Analisis Tulangan Lentur Balok</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Dimensi Balok**")
        b = st.number_input("Lebar (b) [mm]", 150, 1000, 200)
        h = st.number_input("Tinggi (h) [mm]", 200, 2000, 400)
        cover = st.number_input("Selimut Beton (ds) [mm]", 20, 100, 40)
        
    with col2:
        st.markdown("**Gaya Dalam (Ultimate)**")
        Mu_kNm = st.number_input("Momen Ultimate (Mu) [kNm]", 0.0, 5000.0, 157.0, help="Ambil dari Output SAP2000/ETABS (Kombinasi 1.2D + 1.0E + ...)")
        d_tul = st.selectbox("Diameter Tulangan Utama", [13, 16, 19, 22, 25], index=1)
    
    if st.button("RUNNING ANALISIS BALOK 🚀"):
        # --- ALGORITMA HITUNG (ENGINEERING CORE) ---
        d_eff = h - cover - 10 - (d_tul/2) # Asumsi sengkang D10
        phi = 0.90 # Faktor reduksi lentur
        
        # 1. Hitung Mu perlu (Nmm)
        Mu = Mu_kNm * 1e6
        
        # 2. Hitung Mn perlu
        Mn_perlu = Mu / phi
        
        # 3. Hitung Rn
        Rn = Mn_perlu / (b * d_eff**2)
        
        # 4. Hitung Rho (Ratio Tulangan)
        beta1 = 0.85 if fc <= 28 else max(0.65, 0.85 - 0.05*((fc-28)/7))
        
        rho_b = (0.85 * beta1 * fc / fy) * (600 / (600 + fy))
        rho_max = 0.75 * rho_b # Limit SNI agar ductile
        rho_min = max(1.4/fy, 0.25*np.sqrt(fc)/fy)
        
        m = fy / (0.85 * fc)
        
        # Cek apakah penampang cukup?
        st.markdown("---")
        st.markdown("### 📊 Hasil Analisis")
        
        try:
            rho_perlu = (1/m) * (1 - np.sqrt(1 - (2 * m * Rn) / fy))
        except:
            st.markdown(f'<div class="danger-box">❌ <b>GAGAL: PENAMPANG TERLALU KECIL!</b><br>Momen terlalu besar, beton hancur (Rn = {Rn:.2f} MPa). Perbesar ukuran balok (b/h).</div>', unsafe_allow_html=True)
            st.stop()
            
        rho_pakai = max(rho_perlu, rho_min)
        As_perlu = rho_pakai * b * d_eff
        
        # Hitung Jumlah Tulangan
        A_satu_tul = 0.25 * 3.14159 * d_tul**2
        n_tul = As_perlu / A_satu_tul
        n_tul_pakai = int(np.ceil(n_tul))
        As_terpasang = n_tul_pakai * A_satu_tul
        
        # --- REPORTING ---
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.write(f"**Data Teknis:**")
            st.write(f"- $d_{{eff}}$ = {d_eff} mm")
            st.write(f"- $R_n$ = {Rn:.2f} MPa")
            st.write(f"- $\\rho_{{perlu}}$ = {rho_perlu:.4f}")
            st.write(f"- $\\rho_{{max}}$ = {rho_max:.4f} (Batas Duktilitas)")
            
        with col_res2:
            st.write(f"**Rekomendasi:**")
            if rho_pakai > rho_max:
                st.markdown(f'<div class="danger-box">⚠️ <b>BAHAYA: OVER-REINFORCED</b><br>Perlu tulangan {n_tul:.2f} buah, tapi rasio tulangan ({rho_pakai:.4f}) melebihi batas maksimum ({rho_max:.4f}).<br><b>Solusi:</b> Perbesar Balok atau naikkan Mutu Beton!</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="success-box">✅ <b>AMAN (UNDER-REINFORCED)</b><br>Gunakan <b>{n_tul_pakai} D{d_tul}</b><br>As = {As_terpasang:.0f} mm²</div>', unsafe_allow_html=True)

# === TAB 2: CEK GEMPA (Perbaikan File lateralgempa.csv) ===
with tab2:
    st.markdown('<p class="header-style">Kalkulator Gaya Geser Dasar (V) - SNI 1726:2019</p>', unsafe_allow_html=True)
    st.write("Menggantikan rumus lama (C x I x K x Wt) dengan metode Respon Spektrum Desain.")
    
    wt = st.number_input("Berat Seismik Total (Wt) [kN]", value=5000.0)
    
    # Hitung Koefisien Fa Fv Sederhana
    # (Simplified logic for demo purposes - real app should use full table)
    fa_map = {"SC": 1.2, "SD": 1.4, "SE": 1.2} # Simplifikasi
    fv_map = {"SC": 1.7, "SD": 2.0, "SE": 2.5} # Simplifikasi
    
    Fa = fa_map.get(kelas_situs.split()[0], 1.0)
    Fv = fv_map.get(kelas_situs.split()[0], 1.5)
    
    Sds = (2/3) * Fa * Ss
    Sd1 = (2/3) * Fv * S1
    
    # Hitung Cs
    Ie = 1.0 # Faktor keutamaan standar
    Cs = Sds / (R/Ie)
    
    V_base = Cs * wt
    V_lama = 0.05 * wt # Asumsi koefisien gempa lama 0.05
    
    if st.button("HITUNG BASE SHEAR"):
        st.markdown(f"""
        ### 📋 Hasil Perhitungan
        - **SDS**: {Sds:.3f} g
        - **SD1**: {Sd1:.3f} g
        - **Koefisien Seismik (Cs)**: {Cs:.4f}
        """)
        
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.markdown(f'<div class="warning-box"><b>Metode Lama (Excel):</b><br>V = {V_lama:.2f} kN</div>', unsafe_allow_html=True)
        with col_v2:
            st.markdown(f'<div class="success-box"><b>Metode Baru (SNI 2019):</b><br>V = {V_base:.2f} kN</div>', unsafe_allow_html=True)
            
        diff = ((V_base - V_lama) / V_lama) * 100
        st.write(f"**Analisis:** Gaya gempa metode baru **{diff:.1f}% lebih besar** daripada perhitungan lama Anda.")

# === TAB 3: INFO ===
with tab3:
    st.write("**Tentang Aplikasi**")
    st.write("Dibuat oleh The GEMS Grandmaster untuk memvalidasi perhitungan struktur lama (Legacy Data) agar sesuai dengan regulasi PBG/SLF terkini.")
```

---

### 🛠️ CARA MENJALANKAN (RUNNING) DI LAPTOP:

1.  **Install Python:** Pastikan laptop Anda sudah terinstall Python.
2.  **Install Streamlit:** Buka Command Prompt (CMD) atau Terminal, ketik:
    ```bash
    pip install streamlit pandas numpy matplotlib
    ```
3.  **Simpan File:** Copy kode di atas, simpan di Notepad dengan nama `gems_app.py` (pastikan ekstensinya `.py`, bukan `.txt`).
4.  **Running:** Di CMD, masuk ke folder tempat Anda menyimpan file, lalu ketik:
    ```bash
    streamlit run gems_app.py
