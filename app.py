import streamlit as st
import pandas as pd
import json
import os

# 1. Konfigurasi Halaman Utama Streamlit (Wajib ditaruh di paling atas)
st.set_page_config(
    page_title="Corporate Shell & Tax Leakage Network Intelligence",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Perbaikan Error Python 3.14: Gunakan penulisan CSS murni tanpa gangguan parser markdown internal
css_style = """
<style>
    html, body, [data-testid="stSidebarCollapse"] { font-family: 'Segoe UI', sans-serif; }
    h1, h2, h3 { color: #ffffff !important; }
    .metric-card {
        background-color: #1a1c24;
        border: 1px solid #464855;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .metric-title { font-size: 13px; color: #a3a8b4; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-value { font-size: 24px; font-weight: bold; color: #ff4b4b; margin-top: 5px; }
</style>
"""
st.components.v1.html(css_style, height=0, width=0)

# 3. Narasi Analisis Eksekutif dalam Bahasa Inggris
st.title("Company Network Visualisation")
st.markdown("""
### Overview
This analytics workspace is purpose-built to map corporate structures, identify cross-border profit shifting, and flag **Shell Companies** or high-risk unregistered entities. Entities designated as **LN (Luar Negeri / Foreign)** or **Non NPWP (No Tax Registration Number)** represent strategic transfer-pricing risk surfaces where outbound capital, dividends, or ownership values can be obfuscated to achieve aggressive tax optimization or tax evasion.

**Analytic Focus:** Detecting Indonesian domestic corporate entities (`Badan`) that redirect substantial dividend streams or transfer heavy equity percentages into high-risk foreign jurisdictions or unregistered structures.
""")

# 4. Fungsi memuat data yang aman dari error Python 3.14
@st.cache_data
def load_network_data():
    if os.path.exists("nodes_masked.csv") and os.path.exists("edges_masked_part1_a.csv"):
        nodes = pd.read_csv("nodes_masked.csv")
        edges = pd.read_csv("edges_masked_part1_a.csv")
        return nodes, edges
    else:
        return None, None

nodes_df, edges_df = load_network_data()

if nodes_df is not None and edges_df is not None:
    # Pra-pemrosesan data teks jenis node
    nodes_df['jenis_node'] = nodes_df['jenis_node'].astype(str).str.strip()
    
    # Mapping pencarian cepat untuk ekosistem graf relasi
    node_name_map = dict(zip(nodes_df['id'], nodes_df['nama']))
    node_type_map = dict(zip(nodes_df['id'], nodes_df['jenis_node']))
    
    # Deteksi kelompok wajib pajak berisiko tinggi (Shell Companies / Tax Haven conduits)
    high_risk_types = ['LN', 'Non NPWP']
    high_risk_nodes = set(nodes_df[nodes_df['jenis_node'].isin(high_risk_types)]['id'])
    
    # Tandai transaksi/relasi kepemilikan yang mengalir ke entitas risiko tinggi
    edges_df['is_to_high_risk'] = edges_df['target'].isin(high_risk_nodes)
    
    # Hitung total akumulasi pengalihan dividen ke luar negeri/non-NPWP per perusahaan asal
    outbound_div = edges_df[edges_df['is_to_high_risk']].groupby('sumber')['dividen'].sum().to_dict()
    nodes_df['total_dividen_outbound'] = nodes_df['id'].map(outbound_div).fillna(0)

    # 5. Panel Kontrol Navigasi & Filter di Sidebar
    st.sidebar.header("Dynamic Network Filtering")
    
    analysis_mode = st.sidebar.radio(
        "Select Scope View:",
        ["High-Risk Cross-Border Network Only", "Full Taxpayer Ecosystem Network"]
    )
    
    min_dividend = st.sidebar.number_input(
        "Minimum Outbound Dividend Stream (Rp):", 
        min_value=0, value=0, step=500000000
    )
    
    min_percentage = st.sidebar.slider(
        "Minimum Equity Share Percentage (%):",
        0.0, 100.0, 0.0
    )

    # Operasi Penyaringan Menggunakan Pandas Dataframe
    filtered_edges = edges_df.copy()
    if analysis_mode == "High-Risk Cross-Border Network Only":
        filtered_edges = filtered_edges[
            filtered_edges['sumber'].isin(high_risk_nodes) | 
            filtered_edges['target'].isin(high_risk_nodes)
        ]
        
    filtered_edges = filtered_edges[
        (filtered_edges['dividen'] >= min_dividend) & 
        (filtered_edges['persentase'] >= min_percentage)
    ]
    
    active_node_ids = set(filtered_edges['sumber'].unique()).union(set(filtered_edges['target'].unique()))
    filtered_nodes = nodes_df[nodes_df['id'].isin(active_node_ids)]

    # 6. Pembuatan Komponen KPI Cards yang Aman Tanpa st.markdown HTML Kustom
    total_leakage = filtered_edges[filtered_edges['is_to_high_risk']]['dividen'].sum()
    high_risk_count = filtered_nodes[filtered_nodes['jenis_node'].isin(high_risk_types)]['id'].nunique()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="TOTAL FLAGGED OUTBOUND DIVIDENDS", value=f"Rp {total_leakage:,.2f}")
    with col2:
        st.metric(label="HIGH-RISK SHELL NODES (LN & NON-NPWP)", value=f"{high_risk_count} Entities")
    with col3:
        st.metric(label="TOTAL ACTIVE NETWORK TIES", value=f"{len(filtered_edges)} Links")

    # 7. Transformasi Objek Data Menjadi Format Node-Link JSON untuk D3.js
    d3_nodes = []
    for _, row in filtered_nodes.iterrows():
        d3_nodes.append({
            "id": int(row['id']),
            "nama": str(row['nama']),
            "jenis_node": str(row['jenis_node']),
            "total_dividen_outbound": float(row['total_dividen_outbound'])
        })
        
    d3_links = []
    for _, row in filtered_edges.iterrows():
        s_id = int(row['sumber'])
        t_id = int(row['target'])
        d3_links.append({
            "source": s_id,
            "target": t_id,
            "source_name": str(node_name_map.get(s_id, "Unknown")),
            "target_name": str(node_name_map.get(t_id, "Unknown")),
            "source_type": str(node_type_map.get(s_id, "Unknown")),
            "target_type": str(node_type_map.get(t_id, "Unknown")),
            "persentase": float(row['persentase']),
            "nilai": float(row['nilai']),
            "dividen": float(row['dividen']),
            "high_risk_connection": bool(row['is_to_high_risk'])
        })
        
    graph_payload = {"nodes": d3_nodes, "links": d3_links}

    # 8. Render Jaringan Jaringan Interaktif D3.js menggunakan Iframe Sandbox
    st.subheader("Interactive Relational Network")
    # st.info("💡 Interaction Tip: Drag nodes to rearrange. Hover over nodes or connection vectors to drill-down into detailed tax transaction attributes & dividend paths.")

    if os.path.exists("components/d3_network.html"):
        with open("components/d3_network.html", "r", encoding="utf-8") as html_f:
            html_template = html_f.read()
            
        # Menyisipkan data ke objek penampung JavaScript secara dinamis
        injected_html = html_template.replace(
            "// Run immediately if embedded directly with data injected into window payload",
            f"window.graphDataPayload = {json.dumps(graph_payload)};"
        )
        st.components.v1.html(injected_html, height=650, scrolling=False)
    else:
        st.error("Missing components/d3_network.html file!")

    # 9. Tabel Log Investigasi Forensik Pajak Berisiko Tinggi
    st.subheader("High-Risk Outbound Transfer Transaction Logs")
    risk_table = filtered_edges[filtered_edges['is_to_high_risk']].copy()
    if not risk_table.empty:
        risk_table['Source Corporate'] = risk_table['sumber'].map(node_name_map)
        risk_table['Target Risk Entity'] = risk_table['target'].map(node_name_map)
        risk_table['Target Type'] = risk_table['target'].map(node_type_map)
        
        display_cols = ['Source Corporate', 'Target Risk Entity', 'Target Type', 'persentase', 'nilai', 'dividen']
        formatted_table = risk_table[display_cols].rename(columns={
            'persentase': 'Share Ownership %',
            'nilai': 'Shares Capital (IDR)',
            'dividen': 'Dividends Paid (IDR)'
        }).sort_values(by='Dividends Paid (IDR)', ascending=False)
        
        st.dataframe(formatted_table, use_container_width=True)
    else:
        st.write("No transaction metrics match the current high-risk filter thresholds.")
else:
    st.error("Data files could not be initialized. Please make sure 'nodes_masked.csv' and 'edges_masked_part1_a.csv' are in the root directory.")
