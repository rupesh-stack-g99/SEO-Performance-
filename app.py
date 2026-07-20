import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

# Set up the Streamlit page
st.set_page_config(page_title="Website Performance Dashboard", layout="wide")
st.title("📈 3-Month Website Performance Dashboard")
st.subheader("Independent Analytics for Google Search Console & Google Analytics")

st.markdown("---")

def robust_read_csv(file_buffer):
    """
    Reads a CSV file line-by-line using Python's native csv engine.
    Filters out metadata blocks at the top and bottom by looking for the 
    dominant, widest structural table in the file.
    """
    content = file_buffer.read()
    if isinstance(content, bytes):
        text_content = content.decode('utf-8', errors='ignore')
    else:
        text_content = content
        
    lines = text_content.splitlines()
    reader = csv.reader(lines)
    all_rows = [row for row in reader if row]
    
    if not all_rows:
        return pd.DataFrame()
        
    max_cols = max(len(row) for row in all_rows)
    valid_rows = [row for row in all_rows if len(row) == max_cols]
    
    if not valid_rows:
        return pd.DataFrame()
        
    df = pd.DataFrame(valid_rows[1:], columns=valid_rows[0])
    return df

# Sidebar for file uploads
st.sidebar.header("📁 Upload Data Files")

# 1. GSC Zip Upload
gsc_zip_file = st.sidebar.file_uploader("1. Upload GSC Data (ZIP file)", type=["zip"])

gsc_report_type = st.sidebar.selectbox(
    "Select GSC Report Type inside ZIP to display:",
    ["Pages.csv", "Queries.csv", "Dates.csv", "Countries.csv"],
    index=0
)

# 2. GA CSV Upload
ga_csv_file = st.sidebar.file_uploader("2. Upload GA Data (CSV file)", type=["csv"])

df_gsc = None
df_ga = None

# Process data if at least one file is uploaded
if gsc_zip_file or ga_csv_file:
    
    # Create clean tabs for independent views
    tab1, tab2 = st.tabs(["🔍 Google Search Console (SEO)", "📊 Google Analytics (Traffic)"])
    
    # ----------------------------------------------------
    # TAB 1: GOOGLE SEARCH CONSOLE
    # ----------------------------------------------------
    with tab1:
        if gsc_zip_file:
            try:
                with zipfile.ZipFile(gsc_zip_file) as z:
                    file_list = z.namelist()
                    matched_gsc_files = [f for f in file_list if gsc_report_type.lower() in f.lower()]
                    
                    if matched_gsc_files:
                        with z.open(matched_gsc_files[0]) as f:
                            df_gsc = robust_read_csv(f)
                        st.success(f"Loaded GSC file: **{matched_gsc_files[0]}**")
                    else:
                        csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
                        if csv_files:
                            with z.open(csv_files[0]) as f:
                                df_gsc = robust_read_csv(f)
                            st.warning(f"Could not find '{gsc_report_type}'. Displaying alternative file: **{csv_files[0]}**")
                
                if df_gsc is not None and not df_gsc.empty:
                    df_gsc.columns = df_gsc.columns.str.strip()
                    
                    # Clean numeric values
                    for col in ['Clicks', 'Impressions', 'CTR', 'Position']:
                        if col in df_gsc.columns:
                            df_gsc[col] = df_gsc[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df_gsc[col] = pd.to_numeric(df_gsc[col], errors='coerce').fillna(0)
                    
                    # GSC KPIs
                    st.subheader("📋 GSC Key Performance Metrics")
                    kpi1, kpi2, kpi3 = st.columns(3)
                    
                    total_clicks = df_gsc.get('Clicks', pd.Series([0])).sum()
                    total_impressions = df_gsc.get('Impressions', pd.Series([0])).sum()
                    avg_position = df_gsc.get('Position', pd.Series([0])).mean() if 'Position' in df_gsc.columns else 0
                    
                    kpi1.metric("Total Clicks", f"{int(total_clicks):,}")
                    kpi2.metric("Total Impressions", f"{int(total_impressions):,}")
                    if avg_position > 0:
                        kpi3.metric("Average Position", f"{avg_position:.1f}")
                    
                    # Charting primary text dimension against Clicks
                    main_dim = df_gsc.columns[0] # Usually Page, Query, Date, etc.
                    if 'Clicks' in df_gsc.columns:
                        st.subheader(f"🏆 Top Performers by {main_dim}")
                        top_gsc = df_gsc.sort_values(by='Clicks', ascending=False).head(10)
                        fig_gsc = px.bar(top_gsc, x=main_dim, y='Clicks', color='Clicks', text_auto=True, title=f"Top 10 {main_dim} by Organic Clicks")
                        st.plotly_chart(fig_gsc, use_container_width=True)
                    
                    # Raw Table Preview
                    st.subheader("📁 Complete GSC Data Table")
                    st.dataframe(df_gsc, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading GSC ZIP file: {e}")
        else:
            st.info("Please upload a GSC ZIP file in the sidebar to populate this panel.")

    # ----------------------------------------------------
    # TAB 2: GOOGLE ANALYTICS
    # ----------------------------------------------------
    with tab2:
        if ga_csv_file:
            try:
                df_ga = robust_read_csv(ga_csv_file)
                if df_ga is not None and not df_ga.empty:
                    df_ga.columns = df_ga.columns.str.strip()
                    st.success("Loaded Google Analytics data sheet successfully.")
                    
                    # Clean numeric elements
                    metrics = ['sessions', 'conversions', 'users', 'views', 'bounce']
                    for col in df_ga.columns:
                        if any(m in col.lower() for m in metrics):
                            df_ga[col] = df_ga[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df_ga[col] = pd.to_numeric(df_ga[col], errors='coerce').fillna(0)
                    
                    # Find numerical columns for dynamic KPI rendering
                    numeric_cols = df_ga.select_dtypes(include=['number']).columns.tolist()
                    
                    # GA KPIs
                    st.subheader("📋 GA Key Performance Metrics")
                    if numeric_cols:
                        kpi_cols = st.columns(min(len(numeric_cols), 4))
                        for idx, col_name in enumerate(numeric_cols[:4]):
                            total_val = df_ga[col_name].sum()
                            # Use commas for counts, float decimals for rates/averages
                            val_format = f"{int(total_val):,}" if total_val.is_integer() else f"{total_val:,.2f}"
                            kpi_cols[idx].metric(col_name, val_format)
                            
                    # Graph Primary Attribute
                    ga_dim = df_ga.columns[0]
                    if numeric_cols:
                        metric_choice = st.selectbox("Select metric to map visual rankings:", numeric_cols)
                        st.subheader(f"🏆 Top GA Breakdown by {ga_dim}")
                        top_ga = df_ga.sort_values(by=metric_choice, ascending=False).head(10)
                        fig_ga = px.bar(top_ga, x=ga_dim, y=metric_choice, color=metric_choice, text_auto=True, title=f"Top 10 {ga_dim} by {metric_choice}")
                        st.plotly_chart(fig_ga, use_container_width=True)
                        
                    # Raw Table Preview
                    st.subheader("📁 Complete GA Data Table")
                    st.dataframe(df_ga, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading GA CSV file: {e}")
        else:
            st.info("Please upload a GA CSV file in the sidebar to populate this panel.")
            
else:
    st.info("💡 Please upload your files in the sidebar to populate the analytics dashboard panels.")
