import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

# Set up the Streamlit page
st.set_page_config(page_title="GSC & GA Performance Dashboard", layout="wide")
st.title("📈 3-Month Website Performance Dashboard")
st.subheader("Compare Google Search Console & Google Analytics Data Automatically")

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
    
    # Use native csv reader to safely parse rows regardless of varying column counts
    reader = csv.reader(lines)
    all_rows = [row for row in reader if row] # filter out completely empty rows
    
    if not all_rows:
        return pd.DataFrame()
        
    # Determine the maximum number of columns present in this file
    max_cols = max(len(row) for row in all_rows)
    
    # Extract only the main data table (rows matching the maximum column width)
    valid_rows = [row for row in all_rows if len(row) == max_cols]
    
    if not valid_rows:
        return pd.DataFrame()
        
    # Create DataFrame using the first wide row as headers
    df = pd.DataFrame(valid_rows[1:], columns=valid_rows[0])
    return df


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
user_join_column = st.sidebar.text_input(
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
                    df_gsc = robust_read_csv(f)
                st.sidebar.success(f"✅ Loaded GSC '{matched_gsc_files[0]}'")
            else:
                csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
                if csv_files:
                    with z.open(csv_files[0]) as f:
                        df_gsc = robust_read_csv(f)
                    st.sidebar.warning(f"⚠️ '{gsc_report_type}' not found. Loaded '{csv_files[0]}'.")
                else:
                    st.error("❌ No CSV files found inside the GSC ZIP archive.")

        # --- STEP 2: Process GA CSV File ---
        df_ga = robust_read_csv(ga_csv_file)
        st.sidebar.success("✅ Loaded GA CSV data")

        # --- DEBUG VISUALIZATIONS (Helps you inspect headers) ---
        if df_gsc is not None and df_ga is not None:
            # Clean column headers (strip whitespaces)
            df_gsc.columns = df_gsc.columns.str.strip()
            df_ga.columns = df_ga.columns.str.strip()
            
            st.info("🔍 **Detected File Headers:**")
            col_a, col_b = st.columns(2)
            col_a.write(f"**GSC Columns Found:** {list(df_gsc.columns)}")
            col_b.write(f"**GA Columns Found:** {list(df_ga.columns)}")

            # --- DEEP STRUCTURAL KEY SEARCH ---
            gsc_matched_col = None
            ga_matched_col = None
            
            target_mode = user_join_column.strip().lower()

            # 1. Search for GSC Matching Key
            if target_mode == "page":
                gsc_possibilities = ['page', 'top pages', 'url', 'landing page', 'link']
            else: 
                gsc_possibilities = ['date', 'day', 'time']

            # Exact match check first, then substring mapping fallback
            for col in df_gsc.columns:
                if col.lower() == target_mode:
                    gsc_matched_col = col
                    break
            if not gsc_matched_col:
                for col in df_gsc.columns:
                    if any(p in col.lower() for p in gsc_possibilities):
                        gsc_matched_col = col
                        break

            # 2. Search for GA Matching Key
            if target_mode == "page":
                ga_possibilities = ['landing page', 'page path', 'page', 'url', 'screen class', 'query string', 'link']
            else: 
                ga_possibilities = ['date', 'day', 'nth day', 'year month']

            for col in df_ga.columns:
                if col.lower() == target_mode:
                    ga_matched_col = col
                    break
            if not ga_matched_col:
                for col in df_ga.columns:
                    if any(p in col.lower() for p in ga_possibilities):
                        ga_matched_col = col
                        break

            # --- RENAME AND SYNC ---
            if gsc_matched_col and ga_matched_col:
                df_gsc.rename(columns={gsc_matched_col: user_join_column}, inplace=True)
                df_ga.rename(columns={ga_matched_col: user_join_column}, inplace=True)
                
                # Sanitize numeric metrics and metrics containing numbers
                metrics = ['clicks', 'impressions', 'sessions', 'conversions', 'users', 'views', 'ctr', 'active']
                for df in [df_gsc, df_ga]:
                    for col in df.columns:
                        if any(m in col.lower() for m in metrics):
                            df[col] = df[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # Merge the verified tables
                merged_df = pd.merge(df_gsc, df_ga, on=user_join_column, how="inner")
                
                if merged_df.empty:
                    st.warning(f"⚠️ Column mapping verified, but 0 matching elements match rows exactly. Check if one file uses full URLs and the other uses relative paths.")
                    st.write("**GSC Key Sample Data:**", df_gsc[[user_join_column]].head(5))
                    st.write("**GA Key Sample Data:**", df_ga[[user_join_column]].head(5))
                else:
                    st.success("🎉 GSC and GA matrices successfully synchronized!")
                    
                    # --- KPI METRICS ---
                    st.subheader("📊 Quick 3-Month Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    def get_metric_sum(df, target_names):
                        for name in target_names:
                            matched_col = [c for c in df.columns if name.lower() in c.lower()]
                            if matched_col:
                                return df[matched_col[0]].sum()
                        return 0

                    clicks = get_metric_sum(merged_df, ['clicks'])
                    impressions = get_metric_sum(merged_df, ['impressions'])
                    sessions = get_metric_sum(merged_df, ['sessions', 'visits'])
                    conversions = get_metric_sum(merged_df, ['conversions', 'transactions'])
                    
                    col1.metric("Total GSC Clicks", f"{int(clicks):,}")
                    col2.metric("Total GSC Impressions", f"{int(impressions):,}")
                    col3.metric("Total GA Sessions", f"{int(sessions):,}")
                    col4.metric("Total GA Conversions", f"{int(conversions):,}")
                    
                    st.markdown("---")
                    
                    # --- INTERACTIVE CHARTS ---
                    st.subheader("📉 Performance Visualization")
                    
                    x_col = [c for c in merged_df.columns if 'clicks' in c.lower()]
                    y_col = [c for c in merged_df.columns if 'sessions' in c.lower()]
                    
                    if x_col and y_col:
                        fig1 = px.scatter(
                            merged_df, 
                            x=x_col[0], 
                            y=y_col[0], 
                            hover_name=user_join_column,
                            title=f"Correlation: {x_col[0]} vs {y_col[0]}",
                            trendline="ols"
                        )
                        st.plotly_chart(fig1, use_container_width=True)
                    
                    st.subheader(f"🏆 Top Performing Items by {user_join_column}")
                    
                    numeric_cols = merged_df.select_dtypes(include=['number']).columns.tolist()
                    if numeric_cols:
                        metric_to_plot = st.selectbox("Select metric to rank by:", numeric_cols)
                        
                        top_data = merged_df.sort_values(by=metric_to_plot, ascending=False).head(15)
                        fig2 = px.bar(
                            top_data, 
                            x=user_join_column, 
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
                st.error(f"❌ Structural Match Failure: Could not auto-detect the matching column for '{user_join_column}'.")
        else:
            st.error("❌ Failed to parse data. One or both tables are empty after data normalization steps.")
            
    except Exception as e:
        st.error(f"An unexpected error occurred while parsing the data: {e}")
else:
    st.info("💡 Please upload the GSC ZIP file and GA CSV file in the sidebar to populate the dashboard.")
