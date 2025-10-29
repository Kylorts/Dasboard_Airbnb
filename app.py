import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import folium
from streamlit_folium import st_folium
import re
from html import unescape


st.set_page_config(page_title="Airbnb Jakarta Dashboard", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #FFEFEF; /* sidebar dengan sentuhan warna Airbnb */
}

div[data-testid="metric-container"] {
    background-color: #FFFFFF;
    border: 1px solid #FF5A5F30;  /* garis lembut warna Airbnb */
    padding: 20px;
    border-radius: 12px;
    box-shadow: 0 4px 8px rgba(255,90,95,0.15);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
div[data-testid="metric-container"]:hover {
    transform: scale(1.03);
    box-shadow: 0 6px 12px rgba(255,90,95,0.25);
}
div[data-testid="metric-container"] > div {
    font-size: 18px;
    font-weight: bold;
    color: #484848;
}
div[data-testid="metric-container"] > p {
    font-size: 24px;
    font-weight: bold;
    color: #FF5A5F;
}

blockquote {
  background: #FFF2F2;
  border-left: 5px solid #FF5A5F;
  margin: 1.5em 10px;
  padding: 0.8em 10px;
  quotes: "\\201C""\\201D""\\2018""\\2019";
}
blockquote p {
  display: inline;
  font-style: italic;
  color: #484848;
}


h1, h2, h3, h4 {
    color: #FF5A5F;
    font-weight: 700;
}
p, label, span {
    color: #484848;
}

</style>
""", unsafe_allow_html=True)


COLOR_RAUSCH = "#FF5A5F"
COLOR_BABU = "#00A699"
COLOR_TIROL = "#767676"
COLOR_ARCH = "#484848"

airbnb_color_scale = alt.Scale(
    domain=["Entire Home", "Private Room", "Shared Room", "Hotel Room"],
    range=[COLOR_RAUSCH, COLOR_BABU, COLOR_TIROL, COLOR_ARCH]
)
host_status_color_scale = alt.Scale(
    domain=["Superhost", "Regular Host"],
    range=[COLOR_RAUSCH, COLOR_TIROL]
)


@st.cache_data
def load_data():
    df = pd.read_csv("Airbnb_listing_jakarta.csv")
    # Pembersihan teks
    def clean_text(text):
        if pd.isna(text): return text
        text = str(text); text = unescape(text); text = ' '.join(text.split())
        return text
    
    text_columns = ['listing_name', 'host_name', 'amenities']
    for col in text_columns:
        if col in df.columns: df[col] = df[col].apply(clean_text)
    
    
    # Penangan nilai hilang
    numeric_fill_median = ['bedrooms', 'beds', 'baths', 'guests']
    for col in numeric_fill_median:
        if col in df.columns: df[col].fillna(df[col].median(), inplace=True)
    rating_cols = [col for col in df.columns if 'rating' in col.lower() or 'num_reviews' in col.lower()]
    for col in rating_cols: df[col].fillna(0, inplace=True)
    revenue_cols = [col for col in df.columns if ('revenue' in col.lower() or 'rate' in col.lower() or 'revpar' in col.lower()) and df[col].dtype in ['float64', 'int64']]
    for col in revenue_cols: df[col].fillna(0, inplace=True)
    
    
    # Penaganan tipe data
    boolean_cols = ['superhost', 'registration', 'instant_book', 'professional_management']
    for col in boolean_cols:
        if col in df.columns:
            if df[col].isnull().any(): df[col].fillna(False, inplace=True)
            df[col] = df[col].astype(bool)
    numeric_cols = ['guests', 'bedrooms', 'beds', 'baths', 'min_nights', 'cleaning_fee', 'extra_guest_fee', 'num_reviews', 'latitude', 'longitude', 'photos_count']
    for col in numeric_cols:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
    if 'listing_id' in df.columns: df['listing_id'] = df['listing_id'].astype(str)
    
    # Hapus duplikat
    df_before = len(df)
    df = df.drop_duplicates(subset=['listing_id'], keep='first')
    removed_duplicates = df_before - len(df)
    if removed_duplicates > 0: print(f"4. {removed_duplicates} duplikat dihapus.")

    # Metrik turunan
    if 'ttm_avg_rate_native' in df.columns and 'guests' in df.columns:
        df['guests_no_zero'] = df['guests'].replace(0, np.nan)
        df['price_per_guest'] = df['ttm_avg_rate_native'] / df['guests_no_zero']
        df['price_per_guest'].fillna(0, inplace=True)
        df = df.drop(columns=['guests_no_zero'])
    
    
    # Standardisasi 
    if 'ttm_occupancy' in df.columns: df["occupancy_percentage"] = df["ttm_occupancy"] * 100; df["occupancy_percentage"].fillna(0, inplace=True)
    if 'room_type' in df.columns: df['room_type_clean'] = df['room_type'].astype(str).str.replace("_", " ").str.title()
    if 'listing_type' in df.columns: df['listing_type'] = df['listing_type'].str.strip()
    
    
    # Hapus baris dengan data kritis hilang atau nilai tidak valid
    critical_cols = ['listing_id', 'latitude', 'longitude']
    df.dropna(subset=critical_cols, inplace=True)
    non_negative_cols = ['guests', 'bedrooms', 'beds', 'baths', 'num_reviews', 'cleaning_fee', 'min_nights']
    for col in non_negative_cols:
        if col in df.columns and df[col].dtype in ['float64', 'int64']: df = df[df[col] >= 0]
    df = df.reset_index(drop=True)
    return df

df = load_data()


st.sidebar.markdown("## Filter Dashboard")
st.sidebar.markdown("---")

room_types = sorted(df["room_type_clean"].dropna().unique())
selected_room_types = st.sidebar.multiselect(
    "Tipe Kamar",
    options=room_types,
    default=room_types,
)

min_price = int(np.floor(df["ttm_avg_rate_native"].min() / 100000) * 100000)
max_price = int(np.ceil(df["ttm_avg_rate_native"].max() / 100000) * 100000)


min_price_k = min_price // 1000
max_price_k = max_price // 1000

price_range_k = st.sidebar.slider(
    "Rentang Harga per Malam", 
    min_price_k, 
    max_price_k, 
    (min_price_k, max_price_k), 
    step=50,  
    format="Rp %dK"
)

price_range_full = (price_range_k[0] * 1000, price_range_k[1] * 1000)


host_status_filter = st.sidebar.radio(
    "Status Host",
    ["Semua", "Superhost Saja", "Regular Host Saja"],
    help="Tampilkan listing dari host dengan status tertentu."
)


st.sidebar.markdown("---")
df_filtered = df.copy()

df_filtered = df_filtered[
    (df_filtered["room_type_clean"].isin(selected_room_types)) &
    (df["ttm_avg_rate_native"].between(price_range_full[0], price_range_full[1]))
]

if host_status_filter == "Superhost Saja":
    df_filtered = df_filtered[df_filtered["superhost"] == True]
elif host_status_filter == "Regular Host Saja":
    df_filtered = df_filtered[df_filtered["superhost"] == False]


st.image("Airbnb_Logo_2.webp", width=200)
st.subheader("Dasboard Wilayah Jakarta")
st.markdown("""
Dashboard listing Airbnb Jakarta untuk mengidentifikasi tren pasar dan faktor penentu kesuksesan.
Dengan memvisualisasikan data sebaran geografis, harga, tingkat okupansi, dan performa host sehingga 
memperoleh insight yang dapat ditindaklanjuti (actionable) untuk strategi listing,
optimalisasi harga, dan peningkatan kualitas layanan bagi para host.
""")
st.divider()

if df_filtered.empty:
    st.warning("Tidak ada data yang sesuai dengan filter Anda.")
    st.stop()

st.subheader("Ringkasan Data")
col1, col2, col3 = st.columns(3, gap="large")
col1.metric("Total Listing", f"{df_filtered.shape[0]:,}")
col2.metric("Rata-rata harga per malam", f"Rp {df_filtered['ttm_avg_rate_native'].mean():,.0f}")
col3.metric("Rata-rata Okupansi", f"{df_filtered['occupancy_percentage'].mean():.1f}%")
st.divider()


st.subheader("Peta Sebaran Listing Airbnb di Jakarta")
with st.container(border=True):
    color_dict = {"Entire Home": COLOR_RAUSCH, "Private Room": COLOR_BABU, "Shared Room": COLOR_TIROL, "Hotel Room": "#FDB400"}
    center_lat = df_filtered["latitude"].mean(); center_lon = df_filtered["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB positron")
    for _, row in df_filtered.iterrows():
        color = color_dict.get(row["room_type_clean"], "gray")
        is_superhost = "<b>Superhost</b>" if row["superhost"] else "Host Biasa"
        popup_html = f"""<div style='font-family:sans-serif;font-size:13px;min-width:250px;'><b style='font-size:15px'>{row['listing_name']}</b><br>Host: {row['host_name']} ({is_superhost})<br>{row['room_type_clean']}<br>{int(row['guests'])} tamu | 🛏️ {int(row['bedrooms'])} kamar tidur<br>Rp {row['ttm_avg_rate_native']:,.0f} / malam<br>{row['rating_overall']}/5 ({row['num_reviews']} ulasan)</div>"""
        folium.CircleMarker(location=[row["latitude"], row["longitude"]], radius=5, color=color, fill=True, fill_color=color, fill_opacity=0.7, tooltip=row["listing_name"], popup=folium.Popup(popup_html, max_width=300)).add_to(m)
    st_folium(m, use_container_width=True, height=600)
    st.markdown(f"""<div style='display:flex;gap:15px;margin-top:10px; padding-left: 10px;'><div><span style='color:{COLOR_RAUSCH}'>⬤</span> Entire Home</div><div><span style='color:{COLOR_BABU}'>⬤</span> Private Room</div><div><span style='color:{COLOR_TIROL}'>⬤</span> Shared Room</div><div><span style='color:#FDB400'>⬤</span> Hotel Room</div></div>""", unsafe_allow_html=True)
st.divider()


st.subheader("Proporsi Tipe Kamar")
with st.container(border=True):
    pie_data = df_filtered["room_type_clean"].value_counts().reset_index()
    pie_data.columns = ["room_type_clean", "count"]
    pie_data["percentage"] = pie_data["count"] / pie_data["count"].sum()
    pie_chart = alt.Chart(pie_data).mark_arc(innerRadius=10).encode(
        theta=alt.Theta("count:Q", title="Jumlah Listing"),
        color=alt.Color("room_type_clean:N", scale=airbnb_color_scale, title="Tipe Kamar"),
        tooltip=["room_type_clean", "count", alt.Tooltip("percentage", title="Persentase", format=".1%")]
    )
    st.altair_chart(pie_chart.properties(title="Distribusi Tipe Kamar di Pasar", height=350), use_container_width=True)
st.divider()


st.subheader("Analisis Keuntungan per Tipe Kamar")
col1, col2 = st.columns(2, gap="large")
with col1:
    with st.container(border=True):
        data_rev = df_filtered.groupby("room_type_clean")["ttm_revenue_native"].mean().reset_index()
        chart_rev = alt.Chart(data_rev).mark_bar(size=100).encode(
            x=alt.X("room_type_clean:N", title="Tipe Kamar", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ttm_revenue_native:Q", title="Rata-rata Pendapatan Tahunan (IDR)"),
            color=alt.Color("room_type_clean:N", scale=airbnb_color_scale, title="Tipe Kamar"),
            tooltip=["room_type_clean", alt.Tooltip("ttm_revenue_native", title="Pendapatan Rata-rata", format=",.0f")]
        )
        st.altair_chart(chart_rev.properties(title="Pendapatan Rata-rata Tahunan per Tipe Kamar", height=350), use_container_width=True)
with col2:
    with st.container(border=True):
        data_occ = df_filtered.groupby("room_type_clean")["occupancy_percentage"].mean().reset_index()
        chart_occ = alt.Chart(data_occ).mark_bar(size=100).encode(
            x=alt.X("room_type_clean:N", title="Tipe Kamar", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("occupancy_percentage:Q", title="Rata-rata Okupansi (%)"),
            color=alt.Color("room_type_clean:N", scale=airbnb_color_scale, title="Tipe Kamar"),
            tooltip=["room_type_clean", alt.Tooltip("occupancy_percentage", title="Okupansi Rata-rata", format=".1f")]
        )
        st.altair_chart(chart_occ.properties(title="Okupansi Rata-rata per Tipe Kamar", height=350), use_container_width=True)
st.divider()


st.subheader("Analisis Status Superhost terhadap Kinerja")
df_super = df_filtered.copy()
df_super["host_status"] = df_super["superhost"].map({True: "Superhost", False: "Regular Host"})
col3, col4 = st.columns(2, gap="large")
with col3:
    with st.container(border=True):
        data_rev_host = df_super.groupby("host_status")["ttm_revenue_native"].mean().reset_index()
        chart_host_rev = alt.Chart(data_rev_host).mark_bar(size=200).encode(
            x=alt.X("host_status:N", title="Status Host", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ttm_revenue_native:Q", title="Rata-rata Pendapatan Tahunan (IDR)"),
            color=alt.Color("host_status:N", scale=host_status_color_scale, title="Status Host"),
            tooltip=["host_status", alt.Tooltip("ttm_revenue_native", title="Pendapatan Rata-rata", format=",.0f")]
        )
        st.altair_chart(chart_host_rev.properties(title="Pendapatan Rata-rata: Superhost vs Regular", height=350), use_container_width=True)
with col4:
    with st.container(border=True):
        data_rat_host = df_super.groupby("host_status")["rating_overall"].mean().reset_index()
        chart_host_rat = alt.Chart(data_rat_host).mark_bar(size=200).encode(
            x=alt.X("host_status:N", title="Status Host", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("rating_overall:Q", title="Rata-rata Rating (0-5)", scale=alt.Scale(domain=[0, 5])),
            color=alt.Color("host_status:N", scale=host_status_color_scale, title="Status Host"),
            tooltip=["host_status", alt.Tooltip("rating_overall", title="Rating Rata-rata", format=".2f")]
        )
        st.altair_chart(chart_host_rat.properties(title="Rating Rata-rata: Superhost vs Regular", height=350), use_container_width=True)

st.divider()

st.subheader("Analisis Harga per Tamu")
with st.container(border=True):
    data_value = df_filtered.groupby("room_type_clean")["price_per_guest"].mean().reset_index()
    data_value = data_value[data_value['price_per_guest'] > 0]
    chart_value = alt.Chart(data_value).mark_bar(size=200).encode(
        x=alt.X("room_type_clean:N", title="Tipe Kamar", axis=alt.Axis(labelAngle=0), sort='-y'),
        y=alt.Y("price_per_guest:Q", title="Rata-rata Harga per Tamu per Malam (IDR)"),
        color=alt.Color("room_type_clean:N", scale=airbnb_color_scale, title="Tipe Kamar"),
        tooltip=["room_type_clean", alt.Tooltip("price_per_guest", title="Avg Price/Guest", format=",.0f")]
    )
    st.altair_chart(chart_value.properties(title="Rata-rata Harga per Tamu per Tipe Kamar", height=350), use_container_width=True)


st.divider()


st.subheader("Korelasi antara Harga per Tamu dan Okupansi")
with st.container(border=True):
    chart_scatter = alt.Chart(df_filtered).mark_circle(size=80, opacity=0.7).encode(
        x=alt.X("price_per_guest:Q", title="Harga per Tamu per Malam (IDR)", scale=alt.Scale(zero=False)),
        y=alt.Y("occupancy_percentage:Q", title="Tingkat Okupansi (%)", scale=alt.Scale(zero=False)),
        color=alt.Color("room_type_clean:N", title="Tipe Kamar"),
        tooltip=[
            "listing_name:N",
            "room_type_clean:N",
            "price_per_guest:Q",
            "occupancy_percentage:Q",
            "num_reviews:Q"
        ]
    ).interactive()
    st.altair_chart(chart_scatter, use_container_width=True)
st.divider()

# Data mentah
with st.expander("📄 Lihat Data Mentah (Filtered)"):
    st.dataframe(df_filtered)