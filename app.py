import streamlit as st
import pandas as pd
import plotly.express as px
import zipfile
import io
import csv

# Set up the Streamlit page
st.set_page_config(page_title="Single-File Project Score Dashboard", layout="wide")
st.title("🏆 Website Performance & Project Health Dashboard")
st.subheader("Upload standard comparison exports from GSC & GA to generate an Overall Project Score")

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

def clean_and_sum(df, col_name):
    """Safely converts a target column to float data and returns its total sum."""
    if col_name in df.columns:
        series = df[col_name].astype(str).str.replace(',', '').str.replace('%', '')
        return pd.to_numeric(series, errors='coerce').fillna(0).sum()
    return 0

# Sidebar setup for just TWO native comparison files
st.sidebar.header("📁 Upload Comparison Reports")
st.sidebar.caption("Generate these by selecting the 'Compare' date range option directly within Google dashboards before exporting.")

gsc_file = st.sidebar.file_uploader("1. GSC Comparison Export (ZIP or CSV)", type=["zip", "csv"])
ga_file = st.sidebar.file_uploader("2. GA4 Comparison Export (CSV)", type=["csv"])

if gsc_file and ga_file:
    try:
        # --- STEP 1: PARSE GSC COMPARISON FILE ---
        df_gsc = None
        if gsc_file.name.endswith('.zip'):
            with zipfile.ZipFile(gsc_file) as z:
                # Default to the first valid csv inside the zip (usually Dates or Pages)
                csv_files = [f for f in z.namelist() if f.endswith('.csv') and not f.startswith('__MACOSX')]
                if csv_files:
                    # Priority check for Dates or Pages
                    target_file = next((f for f in csv_files if "dates" in f.lower() or "pages" in f.lower()), csv_files[0])
                    with z.open(target_file) as f:
                        df_gsc = robust_read_csv(f)
        else:
            df_gsc = robust_read_csv(gsc_file)
            
        # --- STEP 2: PARSE GA4 COMPARISON FILE ---
        df_ga = robust_read_csv(ga_file)

        if df_gsc is not None and df_ga is not None:
            df_gsc.columns = df_gsc.columns.str.strip()
            df_ga.columns = df_ga.columns.str.strip()
            
            # --- EXTRACT METRICS FROM GSC COMPARE FORMAT ---
            # GSC uses strings like: "Clicks: Last 3 months" vs "Clicks: Previous 3 months"
            gsc_curr_clicks_col = next((c for c in df_gsc.columns if 'clicks' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_clicks_col = next((c for c in df_gsc.columns if 'clicks' in c.lower() and 'prev' in c.lower()), None)
            
            gsc_curr_impr_col = next((c for c in df_gsc.columns if 'impressions' in c.lower() and ('last' in c.lower() or 'current' in c.lower())), None)
            gsc_prev_impr_col = next((c for c in df_gsc.columns if 'impressions' in c.lower() and 'prev' in c.lower()), None)

            # Fallback to standard tracking if they uploaded standard headers
            curr_clicks = clean_and_sum(df_gsc, gsc_curr_clicks_col) if gsc_curr_clicks_col else clean_and_sum(df_gsc, 'Clicks')
            prev_clicks = clean_and_sum(df_gsc, gsc_prev_clicks_col) if gsc_prev_clicks_col else 0
            
            curr_impr = clean_and_sum(df_gsc, gsc_curr_impr_col) if gsc_curr_impr_col else clean_and_sum(df_gsc, 'Impressions')
            prev_impr = clean_and_sum(df_gsc, gsc_prev_impr_col) if gsc_prev_impr_col else 0

            # --- EXTRACT METRICS FROM GA4 COMPARE FORMAT ---
            # GA4 comparison outputs either custom columns or lists blocks with date text identifiers
            ga_curr_sess_col = next((c for c in df_ga.columns if 'sessions' in c.lower() and ('last' in c.lower() or 'current' in c.lower() or 'active' in c.lower())), None)
            ga_prev_sess_col = next((c for c in df_ga.columns if 'sessions' in c.lower() and 'prev' in c.lower()), None)
            
            if not ga_curr_sess_col: # Fallback to standard positional matching
                ga_curr_sess_col = next((c for c in df_ga.columns if 'sessions' in c.lower()), None)

            curr_sessions = clean_and_sum(df_ga, ga_curr_sess_col) if ga_curr_sess_col else 0
            prev_sessions = clean_and_sum(df_ga, ga_prev_sess_col) if ga_prev_sess_col else 0

            # If GA structure put comparison in data rows rather than header columns, parse it:
            if prev_sessions == 0 and 'date' in df_ga.columns[0].lower():
                # Attempt structural row grouping breakdown fallback
                try:
                    df_ga['Clean_Sess'] = pd.to_numeric(df_ga[ga_curr_sess_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                    halfway = len(df_ga) // 2
                    curr_sessions = df_ga['Clean_Sess'].iloc[:halfway].sum()
                    prev_sessions = df_ga['Clean_Sess'].iloc[halfway:].sum()
                except:
                    pass

            # --- CALC DELTAS & SCORE ENGINE ---
            def calc_growth(curr, prev):
                if prev <= 0: return 0.0
                return ((curr - prev) / prev) * 100

            impr_growth = calc_growth(curr_impr, prev_impr)
            sessions_growth = calc_growth(curr_sessions, prev_sessions)
            clicks_growth = calc_growth(curr_clicks, prev_clicks)

            # Health Grading Calculation Framework
            # Growth targets inject up to 30 points per core metric index group into baseline score (70)
            score_comp1 = min(max(impr_growth * 0.35, -20), 15)
            score_comp2 = min(max(sessions_growth * 0.35, -20), 15)
            score_comp3 = min(max(clicks_growth * 0.30, -20), 10)
            
            # If no historical baseline column was detected in the file, calculate score purely on active presence
            if prev_impr == 0 and prev_sessions == 0:
                final_score = 75 if curr_clicks > 0 else 50
                is_comparison_valid = False
            else:
                final_score = int(70 + score_comp1 + score_comp2 + score_comp3)
                final_score = min(max(final_score, 0), 100)
                is_comparison_valid = True

            # --- DISPLAY RESULTS INTERFACE ---
            st.subheader("🎯 Calculated Project Health Score")
            sc_col1, sc_col2 = st.columns([1, 2])
            
            with sc_col1:
                st.metric("Project Growth Health Score", f"{final_score} / 100")
                if final_score >= 75:
                    st.success("🔥 **Doing Great!** The files indicate an upward baseline vector across search signals.")
                elif final_score >= 60:
                    st.info("📈 **Maintaining Stability.** Performance remains steady against historical baselines.")
                else:
                    st.warning("⚠️ **Decline Vector Detected.** Performance drops visible compared to your past period.")
            
            with sc_col2:
                if is_comparison_valid:
                    growth_df = pd.DataFrame({
                        'Core Metrics': ['Search Impressions', 'Website Traffic', 'Organic Clicks'],
                        'Growth Dynamic %': [impr_growth, sessions_growth, clicks_growth]
                    })
                    fig = px.bar(growth_df, x='Growth Dynamic %', y='Core Metrics', orientation='h', 
                                 text_auto='.1f', color='Growth Dynamic %', 
                                 color_continuous_scale=px.colors.diverging.RdYlGn)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("ℹ️ Single snapshot detected. For dynamic growth charting, export data using the 'Compare' option in GSC/GA4.")

            # Summary layout matrix grid
            st.markdown("---")
            st.subheader("📊 Performance Matrix Breakdown")
            
            if is_comparison_valid:
                summary_data = pd.DataFrame({
                    'Metric Dimension': ['GSC Search Impressions', 'GA Traffic Sessions', 'GSC Organic Clicks'],
                    'Previous 3M Period': [f"{int(prev_impr):,}", f"{int(prev_sessions):,}", f"{int(prev_clicks):,}"],
                    'Current 3M Period': [f"{int(curr_impr):,}", f"{int(curr_sessions):,}", f"{int(curr_clicks):,}"],
                    'Net Shift Change': [f"{impr_growth:+.1f}%", f"{sessions_growth:+.1f}%", f"{clicks_growth:+.1f}%"]
                })
                st.table(summary_data)
            else:
                summary_data = pd.DataFrame({
                    'Metric Dimension': ['GSC Search Impressions', 'GA Traffic Sessions', 'GSC Organic Clicks'],
                    'Current Volume Summary': [f"{int(curr_impr):,}", f"{int(curr_sessions):,}", f"{int(curr_clicks):,}"]
                })
                st.table(summary_data)

        else:
            st.error("❌ Mismatch detected processing rows. Please recheck your uploaded files format structural validation.")
    except Exception as e:
        st.error(f"Processing error: {e}. Check if you selected the 'Compare' checkbox parameter inside GSC/GA interface prior to download.")
else:
    st.info("💡 **One-Step Dashboard Ready:** Drop your GSC comparison sheet and your GA comparison sheet here to review performance changes instantly.")
