# streamlit_population_app.py
# Streamlit app using Plotly for visualization

import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="주민등록 인구·세대 시각화", layout="wide")

DEFAULT_PATH = "/mnt/data/202509_202509_주민등록인구및세대현황_월간 (2).csv"

@st.cache_data
def load_csv(path_or_buffer):
    encodings = ["utf-8", "euc-kr", "cp949", "latin1"]
    last_err = None
    for e in encodings:
        try:
            if hasattr(path_or_buffer, 'read'):
                path_or_buffer.seek(0)
                return pd.read_csv(path_or_buffer, encoding=e)
            return pd.read_csv(path_or_buffer, encoding=e)
        except Exception as ex:
            last_err = ex
    raise last_err


def clean_numeric(df, key_col='행정구역'):
    df = df.copy()
    for c in df.columns:
        if c == key_col:
            continue
        df[c] = df[c].astype(str).str.replace(r"[^0-9.-]", "", regex=True)
        df[c] = pd.to_numeric(df[c], errors='coerce')
    return df


def melt_monthly(df, key_col='행정구역'):
    other = [c for c in df.columns if c != key_col]
    rows = []
    for c in other:
        m = re.match(r"(\d{4}년\d{2}월)_(.*)$", c)
        if m:
            month = m.group(1)
            metric = m.group(2)
        else:
            month = 'snapshot'
            metric = c
        tmp = df[[key_col, c]].rename(columns={c: 'value'})
        tmp['month'] = month
        tmp['metric'] = metric
        rows.append(tmp)
    long = pd.concat(rows, ignore_index=True)
    long = long.pivot_table(index=[key_col, 'month'], columns='metric', values='value', aggfunc='first').reset_index()
    return long

st.title("📊 주민등록 인구·세대 시각화 (Plotly)")

uploaded = st.sidebar.file_uploader("CSV 업로드", type=['csv'])
use_default = st.sidebar.checkbox("기본 파일 사용", True)

if uploaded is None and use_default:
    path = DEFAULT_PATH
elif uploaded is not None:
    path = uploaded
else:
    st.stop()

try:
    df_raw = load_csv(path)
except Exception as e:
    st.error(f"CSV 로딩 실패: {e}")
    st.stop()

st.subheader("원본 데이터")
st.dataframe(df_raw.head())

# clean
df = clean_numeric(df_raw)
st.subheader("정리된 데이터")
st.dataframe(df.head())

# long format
long = melt_monthly(df)

# optional metric
if '총인구수' in long.columns and '세대수' in long.columns:
    long['평균가구원수'] = long['총인구수'] / long['세대수']

months = sorted(long['month'].unique())
regions = sorted(long['행정구역'].unique())

selected_month = st.sidebar.selectbox("기간 선택", months)
selected_regions = st.sidebar.multiselect("행정구역 선택", regions, default=regions[:10])
metric_options = [c for c in long.columns if c not in ['행정구역', 'month']]
selected_metric = st.sidebar.selectbox("지표 선택", metric_options)
N = st.sidebar.slider("Top N", 5, 50, 15)

filtered = long[(long['month']==selected_month) & (long['행정구역'].isin(selected_regions))]

# Bar chart
bar_df = filtered[['행정구역', selected_metric]].dropna().sort_values(selected_metric, ascending=False).head(N)
fig_bar = px.bar(bar_df, x=selected_metric, y='행정구역', orientation='h')
fig_bar.update_layout(height=600)
st.plotly_chart(fig_bar, use_container_width=True)

# Stacked gender
male = None
female = None
for c in long.columns:
    if '남' in c:
        male = c
    if '여' in c:
        female = c

if male and female and male in filtered.columns and female in filtered.columns:
    st.subheader("남/여 인구 비교")
    melt = filtered[['행정구역', male, female]].melt(id_vars='행정구역', var_name='성별', value_name='인구수')
    fig_stack = px.bar(melt, x='인구수', y='행정구역', color='성별', orientation='h')
    st.plotly_chart(fig_stack, use_container_width=True)

# Scatter
if '세대수' in filtered.columns and '총인구수' in filtered.columns:
    st.subheader("세대수 vs 총인구수")
    fig_scatter = px.scatter(filtered, x='세대수', y='총인구수', hover_name='행정구역')
    st.plotly_chart(fig_scatter, use_container_width=True)

# download
csv = long.to_csv(index=False).encode('utf-8-sig')
st.sidebar.download_button("정리된 데이터 다운로드", csv, "clean_population.csv")

st.write("---")
st.caption("Plotly + Streamlit 대시보드")
