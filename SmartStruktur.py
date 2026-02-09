import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math

# ==========================================
# 1. KONFIGURASI HALAMAN & GAYA (UI/UX)
# ==========================================
st.set_page_config(
    page_title="GEMS SmartStruktur V7",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS untuk tampilan "Gagah" ala Grandmaster
st.markdown("""
    <style>
    .main { background-color: #F8F9FA; }
    h1 { color: #0D47A1; font-weight: 800; }
    h2, h3 { color: #1565C0; }
    .stButton>button {
        background-color: #0D47A1; color: white; 
        border-radius: 8px; font-weight: bold; width: 100%;
    }
    .stButton>button:hover { background-color: #FF6F00; color: white; }
    .metric-card {
        background-color: white; padding: 20px; border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1); border-left: 5px solid #0D47A1;
    }
    .warning-box {
        background-color: #FFEBEE; padding: 15px; border-radius: 5px;
        border: 1px solid #EF9A9A; color: #C62828;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LIBRARY LOGIKA TEKNIK (ENGINEERING BRAIN)
# ==========================================

class SeismicCalculator:
    """Modul Perhitungan Gempa SNI 1726:2019 (Menggantikan lateralgempa.csv)"""
    
    @staticmethod
    def get_fa(Ss, site_class):
        # Tabel 6 SNI 1726:2019 (Interpolasi Linear)
        data = {
            'SA': {0.25: 0.8, 0.5: 0.8, 0.75: 0.8, 1.0: 0.8, 1.25: 0.8},
            'SB': {0.25: 1.0, 0.5: 1.0, 0.75: 1.0, 1.0: 1.0, 1.25: 1.0},
            'SC': {0.25: 1.2, 0.5: 1.2, 0.75: 1.1, 1.0: 1.0, 1.25: 1.0},
            'SD': {0.25: 1.6, 0.5: 1.4, 0.75: 1.2, 1.0: 1.1, 1.25: 1.0},
            'SE': {0.25: 2.5, 0.5: 1.7, 0.75: 1.2, 1.0: 0.9, 1.25: 0.9}
        }
        if site_class == 'SF': return None # Perlu analisis spesifik
        
        vals = data[site_class]
        ss_keys = sorted(vals.keys())
        
        # Logika Interpolasi
        if Ss <= ss_keys[0]: return vals[ss_keys[0]]
        if Ss >= ss_keys[-1]: return vals[ss_keys[-1]]
        
        for i in range(len(ss_keys)-1):
            if ss_keys[i] <= Ss <= ss_keys[i+1]:
                x0, x1 = ss_keys[i], ss_keys[i+1]
                y0, y1 = vals[x0], vals[x1]
                return y0 + (Ss - x0) * (y1 - y0) / (x1 - x0)
        return 1.0

    @staticmethod
    def get_fv(S1, site_class):
        # Tabel 7 SNI 1726:2019
        data = {
            'SA': {0.1: 0.8, 0.2: 0.8, 0.3: 0.8, 0.4: 0.8, 0.5: 0.8},
            'SB': {0.1: 1.0, 0.2: 1.0, 0.3: 1.0, 0.4: 1.0, 0.5: 1.0},
            'SC': {0.1: 1.7, 0.2: 1.6, 0.3: 1.5, 0.4: 1.4, 0.5: 1.3},
            'SD': {0.1: 2.4, 0.2: 2.0, 0.3: 1.8, 0.4: 1.6, 0.5: 1.5},
            'SE': {0.1: 3.5, 0.2: 3.2, 0.3: 2.8, 0.4: 2.4, 0.5: 2.4}
        }
        if site_class == 'SF': return None
        
        vals = data[site_class]
        s1_keys = sorted(vals.keys())
        
        if S1 <= s1_keys[0]: return vals[s1_keys[0]]
        if S1 >= s1_keys[-1]: return vals[s1_keys[-1]]
        
        for i in range(len(s1_keys)-1):
            if s1_keys[i] <= S1 <= s1_keys[i+1]:
                x0, x1 = s1_keys[i], s1_keys[i+1]
                y0, y1 = vals[x0], vals[x1]
                return y0 + (S1 - x0) * (y1 - y0) / (x1 - x0)
        return 1.0

class ConcreteCalculator:
    """Modul Beton SNI 2847:2019 (Menggantikan geser balok.csv)"""
    
    @staticmethod
    def calc_shear(Vu_kN, fc_mpa, bw_mm, d_mm, Nu_kN=0):
        # Konstanta SNI 2847:2019
        PHI_SHEAR = 0.75  # KOREKSI DARI 0.6 (LAMA) KE 0.75 (BARU)
        
        Vu_N = Vu_kN * 1000
        Nu_N = Nu_kN * 1000
        Ag = bw_mm * d_mm # Simplifikasi area efektif
        
        # Rumus Vc Sederhana (Tabel 22.5.5.1) dengan efek aksial
        # Vc = (0.17 * lambda * sqrt(fc) + Nu/6Ag) * bw * d
        lambda_conc = 1.0 # (beton normal)
        
        term1 = 0.17 * 1.0 * math.sqrt(fc_mpa)
        term2 = Nu_N / (6 * Ag) if Ag > 0 else 0
        
        Vc_N = (term1 + term2) * bw_mm * d_mm
        phiVc_N = PHI_SHEAR * Vc_N
        
        status = "AMAN"
        Vs_perlu_N = 0
        
        if Vu_N > phiVc_N:
            status = "PERLU TULANGAN GESER"
            # Vu <= phi(Vc + Vs) -> Vs >= (Vu/phi) - Vc
            Vs_perlu_N = (Vu_N / PHI_SHEAR) - Vc_N
            
        return {
            "Vc_kN": Vc_N / 1000,
            "phiVc_kN": phiVc_N / 1000,
            "Vs_perlu_kN": Vs_perlu_N / 1000,
            "Status": status
        }

class GeotechCalculator:
    """Modul Pondasi (Menggantikan tphiley.csv)"""
    
    @staticmethod
    def calc_hiley(weight_hammer, height_drop, set_s, elastic_c, weight_pile, efficiency):
        # R = (ef . W . H) / (S + C/2) * (W + n^2.P)/(W+P) -> Simplifikasi Hiley Modern
        # e_f: Efisiensi (Drop=0.75, Diesel=0.8-0.9)
        
        W = weight_hammer # ton
        H = height_drop * 100 # convert m to cm
        S = set_s # cm/blow (final set)
        C = elastic_c # cm (total elastic compression)
        P = weight_pile # ton
        n = 0.5 # koef restitusi beton (typical)
        
        energy = efficiency * W * H
        loss_impact = (W + (n**2)*P) / (W + P)
        
        R_ultimate = (energy / (S + (C/2))) * loss_impact
        R_safe = R_ultimate / 3.0 # SF = 3 (SNI 8460)
        
        return R_ultimate, R_safe

# ==========================================
# 3. ANTARMUKA APLIKASI (STREAMLIT UI)
# ==========================================

def main():
    st.sidebar.title("💎 GEMS SMARTSTRUKTUR V7")
    st.sidebar.caption("Powered by Enginex Core | SNI Compliant")
    
    menu = st.sidebar.radio("Pilih Modul:", 
        ["1. Gempa (SNI 1726:2019)", 
         "2. Geser Balok (SNI 2847:2019)", 
         "3. Pondasi Pancang (Modern Hiley)"])

    # --- MODUL 1: GEMPA ---
    if menu == "1. Gempa (SNI 1726:2019)":
        st.header("🌋 Analisis Beban Gempa (Respons Spektrum)")
        st.markdown("Validasi: Menggantikan logika statik `C=0.045` dengan Peta Gempa & Kelas Situs.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Input Parameter")
            ss = st.number_input("Ss (Percepatan Batuan Dasar Periode Pendek - g)", 0.0, 3.0, 0.8, 0.01)
            s1 = st.number_input("S1 (Percepatan Batuan Dasar Periode 1 Detik - g)", 0.0, 2.0, 0.4, 0.01)
            site_class = st.selectbox("Kelas Situs Tanah (SNI 1726:2019)", ["SA", "SB", "SC", "SD", "SE"])
            
        # Hitung Logic
        fa = SeismicCalculator.get_fa(ss, site_class)
        fv = SeismicCalculator.get_fv(s1, site_class)
        
        if fa is not None and fv is not None:
            sms = fa * ss
            sm1 = fv * s1
            sds = (2/3) * sms
            sd1 = (2/3) * sm1
            
            # Cegah pembagian dengan nol jika sds sangat kecil
            if sds > 0:
                t0 = 0.2 * (sd1/sds)
                ts = sd1 / sds
            else:
                t0 = 0
                ts = 0
            
            with col2:
                st.subheader("Hasil Perhitungan")
                res_data = {
                    "Fa (Amplifikasi Pendek)": fa,
                    "Fv (Amplifikasi 1-dtk)": fv,
                    "SMS (g)": sms,
                    "SM1 (g)": sm1,
                    "SDS (Desain Pendek)": sds,
                    "SD1 (Desain 1-dtk)": sd1
                }
                st.dataframe(pd.DataFrame(res_data.items(), columns=["Parameter", "Nilai"]).set_index("Parameter"))
            
            # Plot Response Spectrum
            st.subheader("📈 Kurva Respons Spektrum Desain (Sa vs T)")
            t_vals = np.linspace(0, 4.0, 100)
            sa_vals = []
            for t in t_vals:
                if t < t0: val = sds * (0.4 + 0.6*(t/t0)) if t0 > 0 else 0
                elif t < ts: val = sds
                else: val = sd1 / t if t > 0 else 0
                sa_vals.append(val)
                
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.plot(t_vals, sa_vals, color='#0D47A1', linewidth=2)
            ax.set_xlabel("Periode Getar, T (detik)")
            ax.set_ylabel("Percepatan Respons Spektral, Sa (g)")
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.axvline(ts, color='orange', linestyle='--', label=f'Ts = {ts:.2f}s')
            ax.legend()
            st.pyplot(fig)
            
            st.info(f"💡 **Insight Engineering:** Untuk T < Ts ({ts:.2f}s), struktur dikontrol oleh percepatan (SDS={sds:.3f}). Untuk T > Ts, dikontrol oleh kecepatan (SD1/T).")

    # --- MODUL 2: BETON ---
    elif menu == "2. Geser Balok (SNI 2847:2019)":
        st.header("🏗️ Analisis Geser Balok Beton Bertulang")
        st.markdown("Validasi: Menggunakan $\phi = 0.75$ (bukan 0.6) dan rumus $V_c$ terbaru.")
        
        col1, col2 = st.columns(2)
        with col1:
            fc = st.number_input("Mutu Beton (fc') - MPa", 15, 60, 25)
            bw = st.number_input("Lebar Balok (bw) - mm", 100, 1000, 300)
            d = st.number_input("Tinggi Efektif (d) - mm", 100, 2000, 550)
            vu = st.number_input("Gaya Geser Terfaktor (Vu) - kN", 0.0, 5000.0, 150.0)
            nu = st.number_input("Gaya Aksial (Nu) - kN (Tekan +, Tarik -)", -1000.0, 5000.0, 0.0)
            
        res = ConcreteCalculator.calc_shear(vu, fc, bw, d, nu)
        
        with col2:
            st.subheader("Hasil Analisis")
            
            # Display Metrics
            c1, c2, c3 = st.columns(3)
            c1.metric("Kuat Geser Beton (Vc)", f"{res['Vc_kN']:.2f} kN")
            c2.metric("Kapasitas Rencana (φVc)", f"{res['phiVc_kN']:.2f} kN", help="Menggunakan Phi=0.75")
            c3.metric("Status", res['Status'], delta_color="normal" if res['Status']=="AMAN" else "inverse")
            
            if res['Vs_perlu_kN'] > 0:
                st.warning(f"⚠️ **PERLU TULANGAN GESER (SENGKANG)**\n\nKuat geser tulangan (Vs) yang diperlukan: **{res['Vs_perlu_kN']:.2f} kN**")
                
                # Simple Stirrup Designer
                fy = st.number_input("Mutu Baja Tulangan (fy) - MPa", 240, 550, 420)
                n_kaki = st.selectbox("Jumlah Kaki Sengkang", [2, 3, 4])
                dia_sengkang = st.selectbox("Diameter Sengkang (mm)", [8, 10, 12, 13, 16])
                
                Av = n_kaki * 0.25 * math.pi * (dia_sengkang**2)
                # s = (Av * fy * d) / Vs
                if res['Vs_perlu_kN'] > 0:
                    s_calc = (Av * fy * d) / (res['Vs_perlu_kN'] * 1000)
                    st.success(f"✅ Rekomendasi: Pasang Sengkang **D{dia_sengkang}-{int(s_calc)}** mm")

    # --- MODUL 3: PONDASI ---
    elif menu == "3. Pondasi Pancang (Modern Hiley)":
        st.header("🏗️ Kapasitas Tiang Pancang (Kalendering)")
        st.markdown("Validasi: Menggunakan efisiensi palu dinamis (bukan fixed 0.6).")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Data Pemancangan")
            W_hammer = st.number_input("Berat Palu (Ton)", 0.5, 10.0, 2.5)
            H_drop = st.number_input("Tinggi Jatuh (m)", 0.5, 5.0, 1.5)
            W_pile = st.number_input("Berat Tiang + Topi (Ton)", 0.1, 20.0, 1.2)
            
            st.subheader("Data Lapangan")
            S_set = st.number_input("Final Set (S) - cm/pukulan", 0.0, 10.0, 0.25)
            C_elastic = st.number_input("Rebound Elastis Total (K/C) - cm", 0.0, 5.0, 1.5)
            
            tipe_alat = st.selectbox("Tipe Alat Pancang", ["Drop Hammer (Manual)", "Diesel Hammer", "Hydraulic Hammer"])
            eff_map = {"Drop Hammer (Manual)": 0.60, "Diesel Hammer": 0.85, "Hydraulic Hammer": 0.95}
            eff = eff_map[tipe_alat]
            
        R_ult, R_all = GeotechCalculator.calc_hiley(W_hammer, H_drop, S_set, C_elastic, W_pile, eff)
        
        with col2:
            st.subheader("Kapasitas Dukung")
            st.write(f"**Efisiensi Alat ({tipe_alat}):** {eff}")
            
            st.markdown(f"""
            <div class="metric-card">
                <h3>Daya Dukung Ultimit (Qu)</h3>
                <h1>{R_ult:.2f} Ton</h1>
            </div>
            <br>
            <div class="metric-card" style="border-left: 5px solid #2E7D32;">
                <h3>Daya Dukung Izin (Qall)</h3>
                <h1>{R_all:.2f} Ton</h1>
                <p>Safety Factor = 3.0</p>
            </div>
            """, unsafe_allow_html=True)
            
            if R_all < 20:
                st.warning("⚠️ Kapasitas tiang relatif kecil. Cek ulang data kalendering atau pertimbangkan tiang bor.")

if __name__ == "__main__":
    main()
