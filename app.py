import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

# Set up the Streamlit page
st.set_page_config(page_title="Website Performance Dashboard", layout="wide")
st.title("📈 3-Month Performance Trend Dashboard")
st.subheader("Evaluate growth trends to see if performance is getting better or worse")

st.markdown("---")

def robust_read_csv(file_buffer):
    """Reads a CSV line-by-line, bypassing metadata rows dynamically."""
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

def try_parse_dates_and_add_month(df):
    """Attempts to find a date column and create a structural 'Month' column."""
    for col in df.columns:
        if 'date' in col.lower() or 'day' in col.lower():
            try:
                # Parse to datetime
                parsed_dates = pd.to_datetime(df[col], errors='coerce')
                if not parsed_dates.isna().all():
                    df['Month'] = parsed_dates.dt.strftime('%Y-%m (Month %b)')
                    return df, True
            except:
                pass
    return df, False

def display_trend_metrics(df, metric_list):
    """Calculates MoM percentage shifts and renders dynamic delta cards."""
    months = sorted(df['Month'].unique())
    if len(months) < 2:
        st.warning("⚠️ Need at least 2 distinct months of data to compute performance shifts.")
        return
        
    st.markdown(f"### 🗓️ Comparing Months: **{', '.join(months)}**")
    
    # Pivot matrix to calculate summaries per month
    monthly_summary = df.groupby('Month')[metric_list].sum().reset_index()
    
    cols = st.columns(len(metric_list))
    for idx, metric in enumerate(metric_list):
        with cols[idx]:
            # Get values for latest and previous month
            latest_val = monthly_summary.iloc[-1][metric]
            prev_val = monthly_summary.iloc[-2][metric]
            
            # Calculate absolute percentage swing
            if prev_val > 0:
                change_pct = ((latest_val - prev_val) / prev_val) * 100
                delta_str = f"{change_pct:+.1f}% vs Last Month"
            else:
                delta_str = "New Data"
                change_pct = 0
                
            # Determine status label
            status = "🟢 Improving" if change_pct >= 0 else "🔴 Declining"
            
            st.metric(
                label=f"{metric} ({status})", 
                value=f"{int(latest_val):,}", 
                delta=delta_str
            )
            
    # Draw Trend Line Plot
    fig = px.line(
        monthly_summary, 
        x='Month', 
        y=metric_list, 
        markers=True, 
        title="Performance Trajectory Over Last 3 Months"
    )
    st.plotly_chart(fig, use_container_width=True)

# Sidebar for file uploads
st.sidebar.header("📁 Upload Data Files")

# 1. GSC Zip Upload
gsc_zip_file = st.sidebar.file_uploader("1. Upload GSC Data (ZIP file)", type=["zip"])
gsc_report_type = st.sidebar.selectbox(
    "Select GSC Report Type inside ZIP to display:",
    ["Dates.csv", "Pages.csv", "Queries.csv", "Countries.csv"],
    index=0
)

# 2. GA CSV Upload
ga_csv_file = st.sidebar.file_uploader("2. Upload GA Data (CSV file)", type=["csv"])

# Optional manual month override if they upload single fixed total snapshot sheets
st.sidebar.markdown("---")
st.sidebar.header("🗓️ Manual Grouping Option")
st.sidebar.caption("If your files don't contain individual dates, use this selection to manually assign a month label to the uploaded file.")
manual_month_label = st.sidebar.text_input("Assign Month Label (e.g. 'Last Month', '2 Months Ago')", value="Current Period")

df_gsc = None
df_ga = None

if gsc_zip_file or ga_csv_file:
    tab1, tab2 = st.tabs(["🔍 Search Console Growth Trend", "📊 Google Analytics Growth Trend"])
    
    # ----------------------------------------------------
    # TAB 1: GOOGLE SEARCH CONSOLE TRENDS
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
                    else:
                        csv_files = [f for f in file_list if f.endswith('.csv') and not f.startswith('__MACOSX')]
                        if csv_files:
                            with z.open(csv_files[0]) as f:
                                df_gsc = robust_read_csv(f)
                
                if df_gsc is not None and not df_gsc.empty:
                    df_gsc.columns = df_gsc.columns.str.strip()
                    
                    # Clean numeric metrics
                    for col in ['Clicks', 'Impressions', 'CTR', 'Position']:
                        if col in df_gsc.columns:
                            df_gsc[col] = df_gsc[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df_gsc[col] = pd.to_numeric(df_gsc[col], errors='coerce').fillna(0)
                    
                    # Detect or assign time parameters
                    df_gsc, has_time = try_parse_dates_and_add_month(df_gsc)
                    if not has_time:
                        df_gsc['Month'] = manual_month_label
                        
                    st.subheader("📈 Search Console Directional Review")
                    available_gsc_metrics = [c for c in ['Clicks', 'Impressions'] if c in df_gsc.columns]
                    
                    if 'Month' in df_gsc.columns and len(df_gsc['Month'].unique()) >= 2:
                        display_trend_metrics(df_gsc, available_gsc_metrics)
                    else:
                        st.info("💡 The current GSC file shows a single historical block. To track month-over-month performance trends, ensure you select **'Dates.csv'** from the report selection box, or update your source export to include a daily timeline breakdown.")
                        
                    st.subheader("📋 Raw Data Output")
                    st.dataframe(df_gsc, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading GSC ZIP file: {e}")
        else:
            st.info("Upload GSC ZIP file to populate data panel.")

    # ----------------------------------------------------
    # TAB 2: GOOGLE ANALYTICS TRENDS
    # ----------------------------------------------------
    with tab2:
        if ga_csv_file:
            try:
                df_ga = robust_read_csv(ga_csv_file)
                if df_ga is not None and not df_ga.empty:
                    df_ga.columns = df_ga.columns.str.strip()
                    
                    # Clean numeric elements
                    metrics = ['sessions', 'conversions', 'users', 'views']
                    for col in df_ga.columns:
                        if any(m in col.lower() for m in metrics):
                            df_ga[col] = df_ga[col].astype(str).str.replace(',', '').str.replace('%', '')
                            df_ga[col] = pd.to_numeric(df_ga[col], errors='coerce').fillna(0)
                    
                    # Detect or assign time parameters
                    df_ga, has_time = try_parse_dates_and_add_month(df_ga)
                    if not has_time:
                        df_ga['Month'] = manual_month_label
                        
                    st.subheader("📈 Analytics Traffic Directional Review")
                    numeric_cols = df_ga.select_dtypes(include=['number']).columns.tolist()
                    
                    if 'Month' in df_ga.columns and len(df_ga['Month'].unique()) >= 2 and numeric_cols:
                        display_trend_metrics(df_ga, numeric_cols[:3])
                    else:
                        st.info("💡 Tracking trajectories over time requires a sequential format. Export your Google Analytics report grouped by **'Date'** rather than just a total page count overview to populate the automatic growth trajectory chart.")
                        
                    st.subheader("📋 Raw Data Output")
                    st.dataframe(df_ga, use_container_width=True)
            except Exception as e:
                st.error(f"Error reading GA CSV file: {e}")
        else:
            st.info("Upload GA CSV file to populate data panel.")
else:
    st.info("💡 Upload your historical metrics in the sidebar to populate the dynamic growth trend analytics engine.")
