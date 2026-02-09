import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math

# ==========================================
# 1. KONFIGURASI SISTEM & VISUAL
# ==========================================
st.set_page_config(
    page_title="GEMS MASTER PRO V8",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling CSS "Grandmaster"
st.markdown("""
    <style>
    .main { background-color: #F0F2F6; }
    .stHeader { color: #0D47A1; }
    h1, h2, h3 { font-family: 'Segoe UI', sans-serif; color: #1A237E; font-weight: 700; }
    .metric-box {
        background-color: #FFFFFF; border-left: 5px solid #0D47A1;
        padding: 15px; border-radius: 5px; box-shadow: 2px 2px 8px rgba(0,0,0,0.1);
        margin-bottom: 10px;
    }
    .success-box { border-left: 5px solid #2E7D32; background-color: #E8F5E9; padding: 15px; }
    .warning-box { border-left: 5px solid #FF6F00; background-color: #FFF3E0; padding: 15px; }
    .stButton>button { background-color: #1565C0; color: white; width: 100%; border-radius: 6px; }
    .stButton>button:hover { background-color: #0D47A1; }
    </style>
""", unsafe_allow_html=True)

# Inisialisasi Session State (Database Sementara)
if 'project_data' not in st.session_state:
    st.session_state['project_data'] = {
        'nama_proyek': 'Gedung Serbaguna V8',
        'lokasi': 'Jakarta',
        'fc': 25,
        'fy': 400,
        'ss': 0.8,
        's1': 0.4
    }

# ==========================================
# 2. ENGINEX CORE (MESIN HITUNG TERPUSAT)
# ==========================================
class EnginexCore:
    """Jantung perhitungan teknik sipil (Library)."""
    
    @staticmethod
    def get_response_spectrum(Ss, S1, site_class):
        # Tabel Fa & Fv (SNI 1726:2019) - Simplified
        fa_table = {'SA': 0.8, 'SB': 1.0, 'SC': 1.2, 'SD': 1.6, 'SE': 2.5}
        fv_table = {'SA': 0.8, 'SB': 1.0, 'SC': 1.7, 'SD': 2.4, 'SE': 3.5}
        
        # Koreksi interpolasi sederhana untuk keamanan
        Fa = fa_table.get(site_class, 1.2)
        Fv = fv_table.get(site_class, 1.5)
        
        SMS = Fa * Ss
        SM1 = Fv * S1
        SDS = (2/3) * SMS
        SD1 = (2/3) * SM1
        
        Ts = SD1 / SDS if SDS > 0 else 0
        return SDS, SD1, Ts

    @staticmethod
    def calc_shear_beam(Vu, fc, bw, d, Nu=0):
        # SNI 2847:2019
        phi = 0.75
        lambda_val = 1.0
        # Vc dengan pengaruh aksial
        Vc = 0.17 * lambda_val * math.sqrt(fc) * bw * d
        if Nu > 0: Vc *= (1 + Nu/(14*bw*d)) # Approximation for compression
        
        phiVc = phi * Vc
        Vs_needed = (Vu*1000 - phiVc) / phi if Vu*1000 > phiVc else 0
        return Vc/1000, phiVc/1000, Vs_needed/1000

    @staticmethod
    def calc_column_capacity(b, h, fc, As_total, fy, Pu_input, Mu_input):
        # P-M Interaction Diagram Simplified Check
        Ag = b * h
        Po = 0.85 * fc * (Ag - As_total) + As_total * fy
        phi_Pn_max = 0.80 * 0.65 * Po # Tied column
        
        # Balance approximation
        ab = (600 / (600 + fy)) * (0.85 * h) # Depth of neutral axis balanced
        # Cek kasar saja untuk indikator
        status = "AMAN" if (Pu_input * 1000) < phi_Pn_max else "TIDAK AMAN (Axial Fail)"
        return phi_Pn_max/1000, status

    @staticmethod
    def calc_retaining_wall(H, gamma_soil, phi_soil, c_soil, q_surcharge):
        # Rankine Coefficient
        Ka = (1 - math.sin(math.radians(phi_soil))) / (1 + math.sin(math.radians(phi_soil)))
        Kp = (1 + math.sin(math.radians(phi_soil))) / (1 - math.sin(math.radians(phi_soil)))
        
        # Active Pressure
        Pa_soil = 0.5 * gamma_soil * (H**2) * Ka
        Pa_surcharge = q_surcharge * H * Ka
        Pa_total = Pa_soil + Pa_surcharge
        
        M_overturning = (Pa_soil * H/3) + (Pa_surcharge * H/2)
        return Ka, Pa_total, M_overturning

    @staticmethod
    def calc_pile_bearing(N_spt, Ap, As_skin, pile_type="Pancang"):
        # Meyerhof Formula (Classic but tuned)
        # Qu = 40.Nb.Ab + 0.2.N_avg.As
        # Safety Factor = 3.0 (SNI 8460)
        
        Nb = min(N_spt, 40) # Limit N to 40
        Q_end = 40 * Nb * Ap
        
        # Friction
        fs = 0.2 * (N_spt/2) # Simplified average N along shaft
        Q_skin = fs * As_skin
        
        Q_ult = Q_end + Q_skin
        SF = 2.5 if pile_type == "Bored Pile" else 3.0
        Q_all = Q_ult / SF
        return Q_ult, Q_all

# ==========================================
# 3. MODUL-MODUL APLIKASI (FOLDER VIRTUAL)
# ==========================================

def modul_dashboard():
    st.title("📊 Dashboard Proyek")
    st.write("Selamat Datang, **Grandmaster Engineer**. Berikut ringkasan proyek aktif.")
    
    col1, col2, col3 = st.columns(3)
    data = st.session_state['project_data']
    
    with col1:
        st.markdown(f"""
        <div class="metric-box">
            <h4>📋 Data Proyek</h4>
            <p><b>Nama:</b> {data['nama_proyek']}</p>
            <p><b>Lokasi:</b> {data['lokasi']}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-box">
            <h4>🏗️ Material Dasar</h4>
            <p><b>Beton (fc'):</b> {data['fc']} MPa</p>
            <p><b>Baja (fy):</b> {data['fy']} MPa</p>
        </div>
        """, unsafe_allow_html=True)
        
    with col3:
        st.markdown(f"""
        <div class="metric-box">
            <h4>🌋 Parameter Gempa</h4>
            <p><b>Ss:</b> {data['ss']} g</p>
            <p><b>S1:</b> {data['s1']} g</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.info("💡 **Tips:** Gunakan menu di sebelah kiri untuk mengakses modul detail (Balok, Kolom, Pondasi, dll). Data yang Anda input di 'Input Teknis' akan digunakan di seluruh modul.")

def modul_input_teknis():
    st.title("📝 Input Data Teknis")
    st.write("Definisikan parameter global proyek di sini.")
    
    with st.form("input_global"):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Informasi Umum")
            nama = st.text_input("Nama Proyek", st.session_state['project_data']['nama_proyek'])
            lokasi = st.text_input("Lokasi Proyek", st.session_state['project_data']['lokasi'])
            
            st.subheader("Material Struktur")
            fc = st.number_input("Mutu Beton (fc') - MPa", 15, 100, st.session_state['project_data']['fc'])
            fy = st.number_input("Mutu Baja Tulangan (fy) - MPa", 240, 550, st.session_state['project_data']['fy'])
            
        with c2:
            st.subheader("Parameter Gempa (SNI 1726:2019)")
            ss = st.number_input("Ss (Batuan Dasar)", 0.0, 3.0, st.session_state['project_data']['ss'])
            s1 = st.number_input("S1 (Batuan Dasar 1 Detik)", 0.0, 2.0, st.session_state['project_data']['s1'])
            
        submit = st.form_submit_button("💾 Simpan Data Proyek")
        
        if submit:
            st.session_state['project_data'].update({
                'nama_proyek': nama, 'lokasi': lokasi, 'fc': fc, 'fy': fy, 'ss': ss, 's1': s1
            })
            st.success("Data proyek berhasil diperbarui! Modul lain akan menggunakan data ini.")

def modul_analisa_gempa():
    st.title("🌋 Analisa Beban Gempa")
    st.markdown("Referensi: **SNI 1726:2019** (Menggantikan koefisien statik 0.045 lama)")
    
    data = st.session_state['project_data']
    st.write(f"Menggunakan data: Ss={data['ss']}, S1={data['s1']}")
    
    site_class = st.selectbox("Klasifikasi Situs Tanah", ["SA (Batuan Keras)", "SB (Batuan)", "SC (Tanah Keras)", "SD (Tanah Sedang)", "SE (Tanah Lunak)"])
    site_code = site_class.split()[0]
    
    sds, sd1, ts = EnginexCore.get_response_spectrum(data['ss'], data['s1'], site_code)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("SDS (Desain Pendek)", f"{sds:.3f} g")
    c2.metric("SD1 (Desain 1 Detik)", f"{sd1:.3f} g")
    c3.metric("Ts (Periode Transisi)", f"{ts:.3f} detik")
    
    st.subheader("📉 Grafik Respons Spektrum Desain")
    t_vals = np.linspace(0, 4, 100)
    sa_vals = []
    t0 = 0.2 * ts
    for t in t_vals:
        if t < t0: val = sds * (0.4 + 0.6*t/t0)
        elif t < ts: val = sds
        else: val = sd1/t if t > 0 else 0
        sa_vals.append(val)
        
    fig, ax = plt.subplots(figsize=(10,3))
    ax.plot(t_vals, sa_vals, color='#0D47A1', linewidth=2)
    ax.set_title(f"Respons Spektrum ({site_code})")
    ax.set_xlabel("Periode (T) [detik]")
    ax.set_ylabel("Percepatan (Sa) [g]")
    ax.grid(True, linestyle='--', alpha=0.5)
    st.pyplot(fig)

def modul_desain_balok():
    st.title("🏗️ Desain Struktur Balok")
    st.markdown("Validasi: Geser & Lentur (SNI 2847:2019)")
    
    data = st.session_state['project_data']
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Dimensi & Gaya")
        b = st.number_input("Lebar (b) mm", 200, 1000, 300)
        h = st.number_input("Tinggi (h) mm", 300, 2000, 600)
        d = h - 50 # decking
        Mu = st.number_input("Momen Ultimate (Mu) kNm", 0.0, 1000.0, 150.0)
        Vu = st.number_input("Geser Ultimate (Vu) kN", 0.0, 1000.0, 100.0)
    
    with c2:
        st.subheader("Hasil Analisis")
        # Hitung Tulangan Lentur (Simplified)
        phi_b = 0.9
        Rn = (Mu * 1e6) / (phi_b * b * d**2)
        rho_perlu = (0.85 * data['fc'] / data['fy']) * (1 - math.sqrt(1 - (2 * Rn) / (0.85 * data['fc'])))
        As_perlu = rho_perlu * b * d
        
        st.write(f"**As Perlu (Lentur):** {As_perlu:.2f} mm²")
        
        # Hitung Geser
        Vc, phiVc, Vs_need = EnginexCore.calc_shear_beam(Vu, data['fc'], b, d)
        
        st.write(f"**Kapasitas Geser Beton (φVc):** {phiVc:.2f} kN")
        if Vu > phiVc:
            st.error(f"PERLU SENGKANG! Vs = {Vs_need:.2f} kN")
            Av = 2 * 0.25 * 3.14 * 10**2 # 2 kaki D10
            s_req = (Av * data['fy'] * d) / (Vs_need * 1000)
            st.success(f"Rekomendasi: Sengkang D10-{int(s_req)} mm")
        else:
            st.success("Geser Aman (Gunakan Sengkang Praktis)")

def modul_desain_kolom():
    st.title("🏛️ Desain Struktur Kolom")
    data = st.session_state['project_data']
    
    col1, col2 = st.columns(2)
    with col1:
        b = st.number_input("Lebar Kolom (mm)", 300, 1500, 500)
        h = st.number_input("Panjang Kolom (mm)", 300, 1500, 500)
        Pu = st.number_input("Beban Aksial (Pu) kN", 0.0, 10000.0, 2000.0)
        
        # Input Tulangan
        n_tul = st.number_input("Jumlah Tulangan Total", 4, 40, 12)
        d_tul = st.selectbox("Diameter Tulangan", [16, 19, 22, 25, 29, 32])
        As_tot = n_tul * 0.25 * 3.14 * (d_tul**2)
        st.caption(f"As Total = {As_tot:.2f} mm²")

    with col2:
        st.subheader("Cek Kapasitas Aksial")
        Pn_max, status = EnginexCore.calc_column_capacity(b, h, data['fc'], As_tot, data['fy'], Pu, 0)
        
        st.metric("Kapasitas Aksial Maks (φPn)", f"{Pn_max:.2f} kN")
        if status == "AMAN":
            st.markdown(f'<div class="success-box">✅ {status}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="warning-box">⚠️ {status} - Perbesar Penampang!</div>', unsafe_allow_html=True)

def modul_pondasi():
    st.title("🏗️ Analisa Pondasi (Pancang & Bor)")
    st.markdown("Ref: CSV `tphiley.csv` & `Meyyerhof.csv` (Di-upgrade ke SNI 8460)")
    
    tipe_pondasi = st.radio("Pilih Tipe Pondasi", ["Tiang Pancang (Hiley/Kalendering)", "Bored Pile (Meyerhof/SPT)"])
    
    if tipe_pondasi == "Tiang Pancang (Hiley/Kalendering)":
        c1, c2 = st.columns(2)
        with c1:
            W = st.number_input("Berat Palu (Ton)", 1.0, 10.0, 2.5)
            H = st.number_input("Tinggi Jatuh (m)", 0.5, 5.0, 1.5)
            P = st.number_input("Berat Tiang (Ton)", 0.5, 10.0, 1.2)
            S = st.number_input("Set (cm)", 0.1, 10.0, 0.25)
            K = st.number_input("Rebound (cm)", 0.1, 5.0, 1.0)
            eff = 0.85 # Diesel Hammer
        
        # Hiley Modern Formula
        energy = eff * W * H * 100 # ton.cm
        R_ult = (energy / (S + K/2)) * (W + 0.5**2 * P)/(W+P)
        R_all = R_ult / 3.0
        
        st.metric("Daya Dukung Ijin (Qall)", f"{R_all:.2f} Ton")
        
    else:
        c1, c2 = st.columns(2)
        with c1:
            dia = st.number_input("Diameter Bor (cm)", 30, 200, 60)
            Nspt = st.number_input("N-SPT Ujung", 1, 60, 30)
            L = st.number_input("Panjang Tiang (m)", 5, 50, 15)
        
        Ap = 0.25 * 3.14 * (dia/100)**2
        As_skin = 3.14 * (dia/100) * L
        
        Qu, Qall = EnginexCore.calc_pile_bearing(Nspt, Ap, As_skin, "Bored Pile")
        st.metric("Daya Dukung Ijin (Qall)", f"{Qall:.2f} Ton")

def modul_dinding_penahan():
    st.title("🧱 Dinding Penahan Tanah (Retaining Wall)")
    st.markdown("Analisis Stabilitas Guling & Geser (Rankine)")
    
    col1, col2 = st.columns(2)
    with col1:
        H = st.number_input("Tinggi Dinding (m)", 1.0, 10.0, 4.0)
        gamma = st.number_input("Berat Jenis Tanah (kN/m3)", 10.0, 25.0, 18.0)
        phi = st.number_input("Sudut Geser Dalam (derajat)", 10.0, 45.0, 30.0)
        qs = st.number_input("Beban Merata (Surcharge) kN/m2", 0.0, 50.0, 10.0)
        
    Ka, Pa, M_over = EnginexCore.calc_retaining_wall(H, gamma, phi, 0, qs)
    
    with col2:
        st.write("### Hasil Analisis")
        st.write(f"Koefisien Tekanan Aktif (Ka): **{Ka:.3f}**")
        st.write(f"Total Tekanan Tanah (Pa): **{Pa:.2f} kN/m'**")
        st.metric("Momen Guling (Mo)", f"{M_over:.2f} kNm/m'")
        
        st.info("Pastikan Momen Penahan (Berat Sendiri x Lengan) > 2.0 x Mo")

def modul_plat_tangga():
    st.title("📶 Plat Lantai & Tangga")
    tab1, tab2 = st.tabs(["Plat Lantai (Tabel Koefisien)", "Tangga"])
    
    with tab1:
        st.write("Analisis Momen Plat Dua Arah (Metode Koefisien Momen)")
        lx = st.number_input("Bentang Pendek (Lx)", 1.0, 10.0, 3.0)
        ly = st.number_input("Bentang Panjang (Ly)", 1.0, 10.0, 4.0)
        q = st.number_input("Beban Total (qu) kN/m2", 1.0, 20.0, 8.0)
        
        ratio = ly/lx
        st.write(f"Rasio Ly/Lx = {ratio:.2f}")
        
        # Simplified Coefficient logic
        clx = 30 + (ratio * 10) # Dummy formula for demonstration
        cly = 20 + (ratio * 5)
        
        Mlx = 0.001 * q * lx**2 * clx
        Mly = 0.001 * q * lx**2 * cly
        
        c1, c2 = st.columns(2)
        c1.metric("Momen Lapangan X", f"{Mlx:.2f} kNm")
        c2.metric("Momen Lapangan Y", f"{Mly:.2f} kNm")
        
    with tab2:
        st.write("Desain Penulangan Tangga")
        t_plat = st.number_input("Tebal Plat Tangga (mm)", 100, 300, 150)
        optrecht = st.number_input("Tinggi Optrade (cm)", 10, 25, 17)
        antrede = st.number_input("Lebar Antrede (cm)", 20, 40, 30)
        sudut = math.degrees(math.atan(optrecht/antrede))
        st.write(f"Sudut Kemiringan: **{sudut:.2f}°**")

def modul_kolam():
    st.title("🏊 Struktur Khusus: Kolam Renang")
    st.markdown("Cek Uplift & Tekanan Hidrostatis")
    
    h_kolam = st.number_input("Kedalaman Kolam (m)", 1.0, 5.0, 2.5)
    muka_air_tanah = st.number_input("Tinggi Muka Air Tanah dari dasar (m)", 0.0, 5.0, 1.5)
    
    w_kolam_kosong = 500 # kN (asumsi berat sendiri struktur)
    uplift = muka_air_tanah * 10 * 50 # (gamma water * Area asumsi 50m2)
    
    st.write(f"Gaya Angkat (Uplift): **{uplift:.2f} kN**")
    st.write(f"Berat Struktur: **{w_kolam_kosong} kN**")
    
    if w_kolam_kosong > 1.25 * uplift:
        st.success("✅ AMAN TERHADAP GAYA ANGKAT (UPLIFT)")
    else:
        st.error("⚠️ BAHAYA! Kolam bisa terangkat saat kosong. Tambah berat sendiri atau pakai angkur tanah.")

# ==========================================
# 4. NAVIGASI UTAMA (SIDEBAR MENU)
# ==========================================
def main():
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/engineer.png", width=80)
        st.title("NAVIGASI MODUL")
        
        menu = st.radio("Pilih Kategori:", [
            "1. Dashboard Proyek",
            "2. Input Data Teknis",
            "3. Analisa Gempa (SNI 1726)",
            "4. Desain Balok",
            "5. Desain Kolom",
            "6. Pondasi (Pancang/Bor)",
            "7. Dinding Penahan Tanah",
            "8. Plat & Tangga",
            "9. Struktur Kolam"
        ])
        
        st.divider()
        st.caption("GEMS SmartStruktur V8")
        st.caption("Enginex Core Loaded")

    # Routing Menu
    if "1" in menu: modul_dashboard()
    elif "2" in menu: modul_input_teknis()
    elif "3" in menu: modul_analisa_gempa()
    elif "4" in menu: modul_desain_balok()
    elif "5" in menu: modul_desain_kolom()
    elif "6" in menu: modul_pondasi()
    elif "7" in menu: modul_dinding_penahan()
    elif "8" in menu: modul_plat_tangga()
    elif "9" in menu: modul_kolam()

if __name__ == "__main__":
    main()
