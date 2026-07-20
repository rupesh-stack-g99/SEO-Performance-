import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io

# Set up the Streamlit page
st.set_page_config(page_title="GSC & GA Performance Dashboard", layout="wide")
st.title("📈 3-Month Website Performance Dashboard")
st.subheader("Compare Google Search Console & Google Analytics Data Automatically")

st.markdown("---")

# Helper function to auto-skip Google Analytics metadata rows
def smart_read_csv(file_buffer):
    """
    Reads a CSV file, skipping top metadata rows dynamically by scanning 
    for common header rows or looking for the row with the most columns.
    """
    # Read all lines as plain text first
    content = file_buffer.read()
    # Handle byte streams from zip vs direct uploads
    if isinstance(content, bytes):
        lines = content.decode('utf-8', errors='ignore').splitlines()
    else:
        lines = content.splitlines()
        
    # Find the row that actually contains the header
    skip_rows = 0
    for idx, line in enumerate(lines[:30]):  # Scan up to the first 30 lines
        # Look for standard GA/GSC headers
        if "Page" in line or "Landing page" in line or "Date" in line or "Clicks" in line or "Sessions" in line:
            skip_rows = idx
            break
            
    # Reset pointer and read with pandas using the calculated offset
    file_buffer.seek(0)
    return pd.read_csv(file_buffer, skiprows=skip_rows)


# Sidebar for configuration and uploads
st.sidebar.header("📁 Upload Data Files")

# 1. GSC Zip Upload
gsc_zip_file = st.sidebar.file_uploader("1. Upload GSC Data (ZIP file)", type=["zip"])

gsc_report_type = st.sidebar.selectbox(
    "Select GSC Report Type inside ZIP:",
    ["Pages.csv", "Dates.csv", "Queries.csv", "Countries.csv"],
    index=0
)

# 2. GA CSV Upload
ga_csv_file = st.sidebar.file_uploader("2. Upload GA Data (CSV file)", type=["csv"])

st.sidebar.header("⚙️ Matching Configuration")
join_column = st.sidebar.text_input(
    "Common Column to Match On", 
    value="Page" if "Pages" in gsc_report_type else "Date"
)

df_gsc = None
df_ga = None

if gsc_zip_file and ga_csv_file:
    try:
        # --- STEP 1: Process GSC ZIP File ---
        with zipfile.ZipFile(gsc_zip_file) as z:
            file_list = z.namelist()
            matched_gsc_files = [f for f in file_list if gsc_report_type.lower() in f.lower()]
            
            if matched_gsc_files:
                with z.open(matched_gsc_files[0]) as f:
                    # Use smart reader in case GSC has extra lines too
                    df_gsc = smart_read_csv(f)
                st.sidebar.success(f"✅ Loaded GSC '{matched_gsc_files[0]}'")
            else:
                csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
                if csv_files:
                    with z.open(csv_files[0]) as f:
                        df_gsc = smart_read_csv(f)
                    st.sidebar.warning(f"⚠️ '{gsc_report_type}' not found. Loaded '{csv_files[0]}'.")
                else:
                    st.error("❌ No CSV files found inside the GSC ZIP archive.")

        # --- STEP 2: Process GA CSV File using Smart Reader ---
        df_ga = smart_read_csv(ga_csv_file)
        st.sidebar.success("✅ Loaded GA CSV data (Metadata skipped!)")

        # --- STEP 3: Merge and Analyze ---
        if df_gsc is not None and df_ga is not None:
            # Clean column names (strip whitespace)
            df_gsc.columns = df_gsc.columns.str.strip()
            df_ga.columns = df_ga.columns.str.strip()
            
            # Map standard variations of Google Analytics "Landing Page" to match GSC's "Page"
            if join_column == "Page":
                if "Landing page" in df_ga.columns and "Page" not in df_ga.columns:
                    df_ga.rename(columns={"Landing page": "Page"}, inplace=True)
                elif "Landing page + query string" in df_ga.columns and "Page" not in df_ga.columns:
                    df_ga.rename(columns={"Landing page + query string": "Page"}, inplace=True)

            # Sanitize numeric metrics
            for df in [df_gsc, df_ga]:
                for col in df.columns:
                    if col in ['Clicks', 'Impressions', 'Sessions', 'Conversions', 'Total users']:
                        if df[col].dtype == 'object':
                            df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df[col] = pd.to_numeric(df[col], errors='coerce')
                        df[col] = df[col].fillna(0)

            if join_column in df_gsc.columns and join_column in df_ga.columns:
                merged_df = pd.merge(df_gsc, df_ga, on=join_column, how="inner")
                
                if merged_df.empty:
                    st.warning(f"⚠️ Merge resulted in 0 rows. Please verify your common column headers. GSC columns: {list(df_gsc.columns)} | GA columns: {list(df_ga.columns)}")
                else:
                    st.success("🎉 Data successfully merged and cross-referenced!")
                    
                    # --- KPI METRICS ---
                    st.subheader("📊 Quick 3-Month Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    clicks = merged_df.get('Clicks', pd.Series([0])).sum()
                    impressions = merged_df.get('Impressions', pd.Series([0])).sum()
                    sessions = merged_df.get('Sessions', pd.Series([0])).sum()
                    conversions = merged_df.get('Conversions', merged_df.get('Transactions', pd.Series([0]))).sum()
                    
                    col1.metric("Total GSC Clicks", f"{int(clicks):,}")
                    col2.metric("Total GSC Impressions", f"{int(impressions):,}")
                    col3.metric("Total GA Sessions", f"{int(sessions):,}")
                    col4.metric("Total GA Conversions", f"{int(conversions):,}")
                    
                    st.markdown("---")
                    
                    # --- INTERACTIVE CHARTS ---
                    st.subheader("📉 Performance Visualization")
                    
                    if 'Clicks' in merged_df.columns and 'Sessions' in merged_df.columns:
                        fig1 = px.scatter(
                            merged_df, 
                            x='Clicks', 
                            y='Sessions', 
                            hover_name=join_column,
                            title="Correlation: GSC Search Clicks vs GA Sessions",
                            trendline="ols"
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    
                    st.subheader(f"🏆 Top Performing Items by {join_column}")
                    available_metrics = [c for c in ['Clicks', 'Impressions', 'Sessions', 'Conversions'] if c in merged_df.columns]
                    metric_to_plot = st.selectbox("Select metric to rank by:", available_metrics)
                    
                    top_data = merged_df.sort_values(by=metric_to_plot, ascending=False).head(15)
                    fig2 = px.bar(
                        top_data, 
                        x=join_column, 
                        y=metric_to_plot, 
                        title=f"Top 15 items by {metric_to_plot}",
                        color=metric_to_plot,
                        text_auto=True
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                    
                    # --- DATA TABLE ---
                    st.subheader("📋 Combined GSC + GA Dataset")
                    st.dataframe(merged_df, use_container_width=True)
                    
                    csv_data = merged_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Merged Data as CSV",
                        data=csv_data,
                        file_name="gsc_zip_ga_merged_report.csv",
                        mime="text/csv"
                    )
            else:
                st.error(f"❌ Matching Column Error: Could not find the column '{join_column}' in one or both files.")
                st.write("**GSC Columns:**", list(df_gsc.columns))
                st.write("**GA Columns:**", list(df_ga.columns))

    except Exception as e:
        st.error(f"An unexpected error occurred while parsing the data: {e}")
else:
    st.info("💡 Please upload the GSC ZIP file and GA CSV file in the sidebar to populate the dashboard.")
