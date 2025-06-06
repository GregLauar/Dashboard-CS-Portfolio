"""
Dashboard interativo para monitoramento de portfólio de FIDCs.

Este script utiliza Streamlit e Plotly para criar visualizações dinâmicas
a partir dos dados processados pelo script principal.

COMO USAR:
1. Certifique-se de que o arquivo 'Portfolio_Data_Final.xlsx' está no caminho especificado abaixo.
2. Salve este código como um arquivo chamado 'dashboard.py'.
3. No terminal, rode o comando:
   streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# --- Configuração da Página ---
st.set_page_config(
    page_title="Portfolio Monitoring Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Caminho do Arquivo de Dados ---
DATA_FILE_PATH = "Portfolio_Data_Final.xlsx"

# --- Funções de Apoio ---
@st.cache_data
def load_data(file_path):
    """
    Carrega os dados da planilha Excel final e realiza cálculos adicionais.
    """
    if not os.path.exists(file_path):
        st.error(f"ERRO: O arquivo '{file_path}' não foi encontrado. "
                 "Verifique o caminho e execute o script principal primeiro para gerar a planilha.")
        return None
    
    try:
        df = pd.read_excel(file_path)
        df['data_referencia'] = pd.to_datetime(df['data_referencia'])

        # Recalcula o retorno acumulado da cota júnior
        df = df.sort_values(by=['fundo', 'data_referencia'])
        df['retorno_sub_taxa'] = pd.to_numeric(df['retorno_subordinada_1'], errors='coerce').fillna(0.0) / 100
        df['retorno_sub_acumulado'] = df.groupby('fundo')['retorno_sub_taxa'].transform(lambda x: (1 + x).cumprod() - 1)

        return df
    except Exception as e:
        st.error(f"Ocorreu um erro ao carregar ou processar o arquivo: {e}")
        return None

# --- Início do Dashboard ---

st.title("📈 Portfolio Monitoring Dashboard")
st.markdown("---")

with st.spinner('Carregando dados... Por favor, aguarde.'):
    df = load_data(DATA_FILE_PATH)

if df is not None:
    # --- Barra Lateral de Filtros ---
    st.sidebar.header("Filtros do Dashboard")
    fundos_disponiveis = sorted(df['fundo'].unique())
    selected_fund = st.sidebar.selectbox(
        'Selecione o Fundo (Deal):',
        options=fundos_disponiveis
    )

    df_fund = df[df['fundo'] == selected_fund].copy()
    
    if df_fund.empty:
        st.warning("Não há dados para o fundo selecionado.")
    else:
        latest_data = df_fund.iloc[-1]

        # --- KPIs e Status ---
        st.header(f"Análise do Fundo: {selected_fund}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Net Worth (PL)", f"R$ {latest_data['net_worth']/1e6:,.2f} M")
        col2.metric("PV of Credit Rights", f"R$ {latest_data['pv_credit_rights']/1e6:,.2f} M")
        col3.metric("PDD", f"R$ {latest_data['pdd']/1e6:,.2f} M")

        status_cols = sorted([col for col in df.columns if col.startswith('status_') and pd.notna(latest_data[col])])
        if status_cols:
            st.subheader("Status de Compliance (Mês Mais Recente)")
            status_latest = latest_data[status_cols]
            status_cols_display = st.columns(len(status_latest))
            for i, (index, value) in enumerate(status_latest.items()):
                label = index.replace('status_', '').replace('_', ' ').title()
                status_cols_display[i].metric(label, value)

        st.markdown("---")
        st.header("Análise Gráfica")
        graph_col1, graph_col2 = st.columns(2)

        # --- GRÁFICO 1: Net Worth vs PV vs PDD (CORRIGIDO com Eixo Duplo) ---
        with graph_col1:
            st.subheader("1. Net Worth, PV & PDD")
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            # Adiciona Net Worth e PV no eixo Y principal
            fig1.add_trace(go.Scatter(x=df_fund['data_referencia'], y=df_fund['net_worth'], name='Net Worth', mode='lines'), secondary_y=False)
            fig1.add_trace(go.Scatter(x=df_fund['data_referencia'], y=df_fund['pv_credit_rights'], name='PV of Credit Rights', mode='lines'), secondary_y=False)
            # Adiciona PDD no eixo Y secundário
            fig1.add_trace(go.Scatter(x=df_fund['data_referencia'], y=df_fund['pdd'], name='PDD', mode='lines', line=dict(dash='dot')), secondary_y=True)
            
            fig1.update_yaxes(title_text="Valor (R$) - Net Worth / PV", secondary_y=False)
            fig1.update_yaxes(title_text="Valor (R$) - PDD", secondary_y=True)
            st.plotly_chart(fig1, use_container_width=True)

        # --- GRÁFICO 2: Subordination (CORRIGIDO para ser Dinâmico) ---
        with graph_col2:
            st.subheader("2. Subordination vs. Threshold")
            # Identifica dinamicamente as colunas de subordinação e threshold relevantes
            sub_cols_to_plot = []
            for col_name in df_fund.columns:
                if 'subordination_' in col_name:
                    # Verifica se o threshold correspondente existe e não é nulo/vazio
                    threshold_col = col_name.replace('subordination', 'threshold')
                    if threshold_col in df_fund.columns and latest_data.get(threshold_col) is not None and pd.notna(latest_data.get(threshold_col)):
                        sub_cols_to_plot.append(col_name)
                        sub_cols_to_plot.append(threshold_col)

            if sub_cols_to_plot:
                df_melt2 = df_fund.melt(
                    id_vars='data_referencia',
                    value_vars=list(set(sub_cols_to_plot)), # Usa set para garantir valores únicos
                    var_name='Métrica', value_name='Ratio'
                )
                fig2 = px.line(df_melt2, x='data_referencia', y='Ratio', color='Métrica',
                               labels={"data_referencia": "Data", "Ratio": "Taxa de Subordinação"})
                fig2.update_yaxes(tickformat=".2%")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.warning("Não foram encontradas métricas de subordinação com thresholds definidos para este fundo.")

        # --- GRÁFICO 3: Junior Return ---
        with graph_col1:
            st.subheader("3. Junior Quota Cumulative Return")
            fig3 = px.area(df_fund, x='data_referencia', y='retorno_sub_acumulado',
                           labels={"data_referencia": "Data", "retorno_sub_acumulado": "Retorno Acumulado"})
            fig3.update_yaxes(tickformat=".2%")
            st.plotly_chart(fig3, use_container_width=True)

        # --- GRÁFICO 4: Delinquency by Range ---
        with graph_col2:
            st.subheader("4. Delinquency by Range (% of PV)")
            delinq_cols = sorted([col for col in df_fund.columns if col.startswith('delinq_ratio_')])
            if delinq_cols:
                df_melt4 = df_fund.melt(
                    id_vars='data_referencia', value_vars=delinq_cols,
                    var_name='Faixa de Atraso', value_name='Percentual do PV')
                df_melt4['Faixa de Atraso'] = df_melt4['Faixa de Atraso'].str.replace('delinq_ratio_', 'Atraso ')
                fig4 = px.bar(df_melt4, x='data_referencia', y='Percentual do PV', color='Faixa de Atraso',
                              barmode='stack', labels={"data_referencia": "Data", "Percentual do PV": "% do PV"})
                fig4.update_yaxes(tickformat=".2%")
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.warning("Não foram encontradas métricas de inadimplência para este fundo.")

        # --- GRÁFICO 5: Monthly Origination vs Net Allocation ---
        with graph_col1:
            st.subheader("5. Monthly Origination vs. Net Allocation")
            fig5 = make_subplots(specs=[[{"secondary_y": True}]])
            fig5.add_trace(go.Bar(x=df_fund['data_referencia'], y=df_fund['vl_dicred_aquis_mes'], name='Originação (R$)'), secondary_y=False)
            fig5.add_trace(go.Scatter(x=df_fund['data_referencia'], y=df_fund['net_allocation'], name='Net Allocation (%)', mode='lines'), secondary_y=True)
            fig5.update_yaxes(title_text="Valor Originação (R$)", secondary_y=False)
            fig5.update_yaxes(title_text="Net Allocation", secondary_y=True, tickformat=".2%")
            st.plotly_chart(fig5, use_container_width=True)
            
        # --- GRÁFICO 6: Receivables Curve ---
        with graph_col2:
            st.subheader("6. Receivables Curve (Aging)")
            prazo_cols = sorted([col for col in df_fund.columns if col.startswith('vl_prazo_venc_') and 'som' not in col])
            if prazo_cols:
                df_melt6 = df_fund.melt(
                    id_vars='data_referencia', value_vars=prazo_cols,
                    var_name='Prazo de Vencimento', value_name='Valor (R$)')
                df_melt6['Prazo de Vencimento'] = df_melt6['Prazo de Vencimento'].str.replace('vl_prazo_venc_', 'Prazo ')
                fig6 = px.bar(df_melt6, x='data_referencia', y='Valor (R$)', color='Prazo de Vencimento',
                              barmode='stack', labels={"data_referencia": "Data"})
                st.plotly_chart(fig6, use_container_width=True)
            else:
                st.warning("Não foram encontradas métricas de prazo de vencimento para este fundo.")

else:
    st.info("Aguardando o carregamento dos dados para exibir o dashboard.")
