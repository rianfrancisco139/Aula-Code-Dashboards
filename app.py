# app.py — Dashboard de RH (versão ajustada com tratamento de erros visível)
# Como rodar:
# 1) Ative a venv  ->  .venv\Scripts\Activate.ps1   (Windows)  |  source .venv/bin/activate  (Mac/Linux)
# 2) Instale deps  ->  pip install streamlit pandas numpy plotly openpyxl python-dateutil
# 3) Rode          ->  streamlit run app.py

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date

# --------------------- Configuração básica ---------------------
st.set_page_config(page_title="Dashboard de RH", layout="wide")
st.title("Dashboard de RH")

# Se o arquivo estiver na mesma pasta do app.py, pode deixar assim.
# Ajuste para o caminho local caso esteja em outra pasta (ex.: r"C:\...\BaseFuncionarios.xlsx")
DEFAULT_EXCEL_PATH = "BaseFuncionarios.xlsx"
DATE_COLS = ["Data de Nascimento", "Data de Contratacao", "Data de Demissao"]

# --------------------- Funções utilitárias ---------------------
def brl(x: float) -> str:
    try:
        return f"R$ {x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    # Padroniza textos
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()

    # Datas
    for c in DATE_COLS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")

    # Padroniza Sexo
    if "Sexo" in df.columns:
        df["Sexo"] = (
            df["Sexo"].str.upper()
            .replace({"MASCULINO": "M", "FEMININO": "F"})
        )

    # Garante numéricos
    for col in ["Salario Base", "Impostos", "Beneficios", "VT", "VR"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Colunas derivadas
    today = pd.Timestamp(date.today())

    if "Data de Nascimento" in df.columns:
        df["Idade"] = ((today - df["Data de Nascimento"]).dt.days // 365).clip(lower=0)

    if "Data de Contratacao" in df.columns:
        meses = (today.year - df["Data de Contratacao"].dt.year) * 12 + \
                (today.month - df["Data de Contratacao"].dt.month)
        df["Tempo de Casa (meses)"] = meses.clip(lower=0)

    if "Data de Demissao" in df.columns:
        df["Status"] = np.where(df["Data de Demissao"].notna(), "Desligado", "Ativo")
    else:
        df["Status"] = "Ativo"

    df["Custo Total Mensal"] = df[["Salario Base", "Impostos", "Beneficios", "VT", "VR"]].sum(axis=1)
    return df

@st.cache_data
def load_from_path(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

@st.cache_data
def load_from_bytes(uploaded_bytes) -> pd.DataFrame:
    df = pd.read_excel(uploaded_bytes, sheet_name=0, engine="openpyxl")
    return prepare_df(df)

# --------------------- Sidebar: fonte de dados ---------------------
with st.sidebar:
    st.header("Fonte de dados")
    st.caption("Use **Upload** ou informe o caminho do arquivo .xlsx")
    up = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    caminho_manual = st.text_input("Ou caminho do Excel", value=DEFAULT_EXCEL_PATH)
    st.divider()
    if up is None:
        existe = os.path.exists(caminho_manual)
        st.write(f"Arquivo em caminho: **{caminho_manual}**")
        st.write("Existe: ", "✅ Sim" if existe else "❌ Não")

# --------------------- Carregamento com erros visíveis ---------------------
df = None
fonte = None
if up is not None:
    try:
        df = load_from_bytes(up)
        fonte = "Upload"
    except Exception as e:
        st.error(f"Erro ao ler Excel (Upload): {e}")
        st.stop()
else:
    try:
        if not os.path.exists(caminho_manual):
            st.error(f"Arquivo não encontrado em: {caminho_manual}")
            st.info("Dica: coloque o .xlsx na mesma pasta do app.py ou ajuste o caminho acima.")
            st.stop()
        df = load_from_path(caminho_manual)
        fonte = "Caminho"
    except Exception as e:
        st.error(f"Erro ao ler Excel (Caminho): {e}")
        st.stop()

st.caption(f"Dados carregados via **{fonte}**. Linhas: {len(df)} | Colunas: {len(df.columns)}")

# Mostra colunas detectadas (ajuda no debug)
with st.expander("Ver colunas detectadas"):
    st.write(list(df.columns))

# --------------------- Filtros ---------------------
st.sidebar.header("Filtros")

def msel(col_name: str):
    if col_name in df.columns:
        vals = sorted([v for v in df[col_name].dropna().unique()])
        return st.sidebar.multiselect(col_name, vals)
    return []

area_sel   = msel("Área")
nivel_sel  = msel("Nível")
cargo_sel  = msel("Cargo")
sexo_sel   = msel("Sexo")
status_sel = msel("Status")
nome_busca = st.sidebar.text_input("Buscar por Nome Completo")

# Períodos
def date_bounds(series: pd.Series):
    s = series.dropna()
    if s.empty:
        return None
    return (s.min().date(), s.max().date())

contr_bounds = date_bounds(df["Data de Contratacao"]) if "Data de Contratacao" in df.columns else None
demis_bounds = date_bounds(df["Data de Demissao"]) if "Data de Demissao" in df.columns else None

if contr_bounds:
    d1, d2 = st.sidebar.date_input("Período de Contratação", value=contr_bounds)
else:
    d1, d2 = None, None

if demis_bounds:
    d3, d4 = st.sidebar.date_input("Período de Demissão", value=demis_bounds)
else:
    d3, d4 = None, None

# Sliders (idade e salário)
if "Idade" in df.columns and not df["Idade"].dropna().empty:
    ida_min, ida_max = int(df["Idade"].min()), int(df["Idade"].max())
    faixa_idade = st.sidebar.slider("Faixa Etária", ida_min, ida_max, (ida_min, ida_max))
else:
    faixa_idade = None

if "Salario Base" in df.columns and not df["Salario Base"].dropna().empty:
    sal_min, sal_max = float(df["Salario Base"].min()), float(df["Salario Base"].max())
    faixa_sal = st.sidebar.slider("Faixa de Salário Base", float(sal_min), float(sal_max), (float(sal_min), float(sal_max)))
else:
    faixa_sal = None

# Aplica filtros
df_f = df.copy()

def apply_in(df_, col, values):
    if values and col in df_.columns:
        return df_[df_[col].isin(values)]
    return df_

df_f = apply_in(df_f, "Área", area_sel)
df_f = apply_in(df_f, "Nível", nivel_sel)
df_f = apply_in(df_f, "Cargo", cargo_sel)
df_f = apply_in(df_f, "Sexo", sexo_sel)
df_f = apply_in(df_f, "Status", status_sel)

if nome_busca and "Nome Completo" in df_f.columns:
    df_f = df_f[df_f["Nome Completo"].str.contains(nome_busca, case=False, na=False)]

if faixa_idade and "Idade" in df_f.columns:
    df_f = df_f[(df_f["Idade"] >= faixa_idade[0]) & (df_f["Idade"] <= faixa_idade[1])]

if faixa_sal and "Salario Base" in df_f.columns:
    df_f = df_f[(df_f["Salario Base"] >= faixa_sal[0]) & (df_f["Salario Base"] <= faixa_sal[1])]

if d1 and d2 and "Data de Contratacao" in df_f.columns:
    df_f = df_f[(df_f["Data de Contratacao"].isna()) |
                ((df_f["Data de Contratacao"] >= pd.to_datetime(d1)) &
                 (df_f["Data de Contratacao"] <= pd.to_datetime(d2)))]

if d3 and d4 and "Data de Demissao" in df_f.columns:
    df_f = df_f[(df_f["Data de Demissao"].isna()) |
                ((df_f["Data de Demissao"] >= pd.to_datetime(d3)) &
                 (df_f["Data de Demissao"] <= pd.to_datetime(d4)))]

# --------------------- Definições das funções KPI ---------------------
def k_headcount_ativo(df):
    return df[df["Status"] == "Ativo"].shape[0]

def k_desligados(df):
    return df[df["Status"] == "Desligado"].shape[0]

def k_folha(df):
    return df[df["Status"] == "Ativo"]["Salario Base"].sum()

def k_custo_total(df):
    return df[df["Status"] == "Ativo"]["Custo Total Mensal"].sum()

def k_idade_media(df):
    return df[df["Status"] == "Ativo"]["Idade"].mean()

def k_avaliacao_media(df):
    # Ajuste o nome da coluna 'Avaliacao' conforme o seu dataset
    if "Avaliacao" in df.columns:
        return df["Avaliacao"].mean()
    return 0.0

# --------------------- KPIs ---------------------
def kpi_card(title, value, bg_color="#CF2626", text_color="#FFFFFF"):
    return f"""
    <div style="
        background-color: {bg_color};
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        text-align: center;
        color: {text_color};
        font-family: 'Segoe UI', sans-serif;
        margin-bottom: 15px;
    ">
        <div style="font-size: 14px; margin-top: 5px;">{title}</div>
        <div style="font-size: 22px; font-weight: bold;">{value}</div>
    </div>
    """

st.markdown("### 📊 Resumo Executivo de RH")

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(kpi_card("Headcount Ativo", f"{k_headcount_ativo(df_f)} colaboradores", bg_color="#E60303", text_color="#004d00"), unsafe_allow_html=True)
    st.markdown(kpi_card("Desligados", f"{k_desligados(df_f)} colaboradores", bg_color="#98FF98", text_color="#004d00"), unsafe_allow_html=True)

with col2:
    st.markdown(kpi_card("Folha Salarial", brl(k_folha(df_f)), bg_color="#98FF98", text_color="#004d00"), unsafe_allow_html=True)
    st.markdown(kpi_card("Custo Total", brl(k_custo_total(df_f)), bg_color="#98FF98", text_color="#004d00"), unsafe_allow_html=True)

with col3:
    st.markdown(kpi_card("Idade Média", f"{k_idade_media(df_f):.1f} anos", bg_color="#98FF98", text_color="#004d00"), unsafe_allow_html=True)
    
    media_aval = k_avaliacao_media(df_f)
    cor_seta = "⬆️" if media_aval >= 7 else "⬇️"
    cor_texto = "#004d00"  # Verde escuro para manter coerência
    st.markdown(kpi_card("Avaliação Média", f"{media_aval:.2f} {cor_seta}", bg_color="#98FF98", text_color=cor_texto), unsafe_allow_html=True)

st.divider()

# --------------------- Gráficos ---------------------
colA, colB = st.columns(2)
with colA:
    if "Área" in df_f.columns:
        d = df_f.groupby("Área").size().reset_index(name="Headcount")
        if not d.empty:
            fig = px.bar(d, x="Área", y="Headcount", title="Headcount por Área")
            st.plotly_chart(fig, use_container_width=True)

with colB:
    if "Cargo" in df_f.columns and "Salario Base" in df_f.columns:
        d = df_f.groupby("Cargo", as_index=False)["Salario Base"].mean().sort_values("Salario Base", ascending=False)
        if not d.empty:
            fig = px.bar(d, x="Cargo", y="Salario Base", title="Salário Médio por Cargo")
            st.plotly_chart(fig, use_container_width=True)

colC, colD = st.columns(2)
with colC:
    if "Idade" in df_f.columns and not df_f["Idade"].dropna().empty:
        fig = px.histogram(df_f, x="Idade", nbins=20, title="Distribuição de Idade")
        st.plotly_chart(fig, use_container_width=True)

with colD:
    if "Sexo" in df_f.columns:
        d = df_f["Sexo"].value_counts().reset_index()
        d.columns = ["Sexo", "Contagem"]
        if not d.empty:
            fig = px.pie(d, values="Contagem", names="Sexo", title="Distribuição por Sexo")
            st.plotly_chart(fig, use_container_width=True)

st.divider()

# --------------------- Tabela e Downloads ---------------------
st.subheader("Tabela (dados filtrados)")
st.dataframe(df_f, use_container_width=True)

csv_bytes = df_f.to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar CSV filtrado",
    data=csv_bytes,
    file_name="funcionarios_filtrado.csv",
    mime="text/csv"
)

# Exportar Excel filtrado (opcional)
to_excel = st.toggle("Gerar Excel filtrado para download")
if to_excel:
    from io import BytesIO
    buff = BytesIO()
    with pd.ExcelWriter(buff, engine="openpyxl") as writer:
        df_f.to_excel(writer, index=False, sheet_name="Filtrado")
    st.download_button(
        "Baixar Excel filtrado",
        data=buff.getvalue(),
        file_name="funcionarios_filtrado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
