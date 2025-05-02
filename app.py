import streamlit as st
from dotenv import load_dotenv
from docx import Document
import os
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

# =============================================
# FOLHA DE ESTILO (CSS EXTERNO)
# =============================================
def carregar_estilos():
    with open("style.css", "r", encoding="utf-8") as f:
        css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# =============================================
# CONFIGURAÇÃO INICIAL
# =============================================
def configurar_pagina():
    st.set_page_config(
        page_title="Assistente Genial",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    carregar_estilos()

# =============================================
# MODELO DE BANCO DE DADOS
# =============================================
Base = declarative_base()

class Analise(Base):
    __tablename__ = 'analises'
    id = Column(Integer, primary_key=True)
    nome = Column(String(255))
    texto_original = Column(Text)
    resultado_ia = Column(Text)
    metricas = Column(Text)
    data_hora = Column(DateTime, default=datetime.now)

# =============================================
# CONFIGURAÇÕES
# =============================================
def configurar_banco_dados():
    engine = create_engine('sqlite:///analises.db')
    Session = sessionmaker(bind=engine)
    inspector = inspect(engine)

    if 'analises' not in inspector.get_table_names():
        Base.metadata.create_all(engine)
    else:
        colunas = [col['name'] for col in inspector.get_columns('analises')]
        if 'nome' not in colunas:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE analises ADD COLUMN nome TEXT'))
        if 'metricas' not in colunas:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE analises ADD COLUMN metricas TEXT'))

    return engine, Session

def configurar_ia():
    load_dotenv()
    return ChatOpenAI(
        model_name="mistralai/mistral-7b-instruct",
        temperature=0.3,
        max_tokens=1024,
        openai_api_base="https://openrouter.ai/api/v1",
        openai_api_key=os.getenv("OPENROUTER_API_KEY")
    )

# =============================================
# PROMPT DE ANÁLISE
# =============================================
def criar_prompt_analise():
    return ChatPromptTemplate.from_template("""
Você é um engenheiro experiente analisando documentos técnicos com profundidade. Forneça um relatório detalhado com os seguintes pontos:

# ANÁLISE TÉCNICA DETALHADA

## 1. CONTEXTUALIZAÇÃO
- Visão Geral do Escopo
- Objetivos-chave
- Partes Interessadas

## 2. AVALIAÇÃO POR CRITÉRIOS

### Clareza (x/5)
✅ Pontos fortes
✖️ Problemas
💡 Sugestões

### Viabilidade (x/5)
✅ Pontos fortes
✖️ Problemas
💡 Sugestões

### Organização e Coerência (x/5)
✅ Pontos fortes
✖️ Problemas
💡 Sugestões

### Impacto Ambiental e Societal (x/5)
✅ Pontos fortes
✖️ Problemas
💡 Sugestões

### Riscos e Desafios (x/5)
✅ Pontos fortes
✖️ Problemas
💡 Sugestões

## 3. RECOMENDAÇÕES

1. Ação Urgente
2. Segunda Prioridade
3. Terceira Recomendação

## 4. CONCLUSÃO FINAL
- Resumo Geral
- Impacto Geral
- Próximos Passos

Texto: {escopo}
""")

# =============================================
# GERAÇÃO DE PDF COM FORMATO OFICIAL
# =============================================
def gerar_pdf_com_layout_oficial(texto, titulo="Relatório Oficial"):
    doc = SimpleDocTemplate(
        "relatorio_oficial.pdf",
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'Title',
        fontName='Times-Roman',
        fontSize=16,
        textColor=colors.HexColor("#003366"),
        alignment=1,
        spaceAfter=20,
        leading=24
    )

    body_style = ParagraphStyle(
        'BodyText',
        fontName='Times-Roman',
        fontSize=12,
        leading=14,
        alignment=4,
        spaceAfter=12
    )

    footer_style = ParagraphStyle(
        'Footer',
        fontName='Times-Roman',
        fontSize=10,
        alignment=2,
        spaceBefore=12,
        spaceAfter=12,
    )

    content = [Paragraph(titulo, title_style), Spacer(1, 12)]

    for par in texto.split('\n'):
        if par.strip():
            content.append(Paragraph(par.strip(), body_style))
            content.append(Spacer(1, 12))

    content.append(Spacer(1, 18))
    content.append(Paragraph("Página", footer_style))

    doc.build(content)
    return "relatorio_oficial.pdf"

# =============================================
# INTERFACE DO USUÁRIO
# =============================================
def mostrar_analise(resultado):
    st.subheader("Resultado da Análise")
    cols = st.columns(4)
    with cols[0]: st.metric("Clareza", "4.2/5", "+0.8")
    with cols[1]: st.metric("Viabilidade", "3.8/5", "-0.2")
    with cols[2]: st.metric("Organização", "4.5/5", "+1.1")
    with cols[3]: st.metric("Riscos", "2.9/5", "-0.5")
    st.markdown(f"<div class='resultado'>{resultado['analise_completa']}</div>", unsafe_allow_html=True)

def main():
    configurar_pagina()
    engine, Sessao = configurar_banco_dados()
    ia = configurar_ia()

    st.markdown("<h1 style='text-align: left;'>Assistente Genial</h1>", unsafe_allow_html=True)
    st.markdown("Obtenha análises técnicas detalhadas de documentos com apoio de IA.")

    abas = st.tabs(["Nova Análise", "Histórico"])
    aba_analise, aba_historico = abas

    with aba_analise:
        with st.form("formulario_analise"):
            st.markdown("### Preencha os campos abaixo para gerar sua análise técnica")

            col1, col2 = st.columns(2)
            with col1:
                arquivo = st.file_uploader("Envie um documento (.docx)", type=["docx"])
            with col2:
                nome_usuario = st.text_input("Seu nome para histórico", placeholder="Ex: João Silva")

            texto = st.text_area("Ou cole o conteúdo diretamente:", height=250)

            executar = st.form_submit_button("Executar Análise")

        if executar:
            if not (arquivo or texto.strip()) or not nome_usuario.strip():
                st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                with st.spinner("Executando análise..."):
                    try:
                        if arquivo:
                            doc = Document(arquivo)
                            texto = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

                        prompt = criar_prompt_analise()
                        prompt_str = prompt.format(escopo=texto)
                        conteudo_final = ia.invoke(prompt_str)

                        resultado = {
                            'analise_completa': conteudo_final.content,
                            'metricas': {'clareza': 4.2, 'viabilidade': 3.8}
                        }

                        with Sessao() as sessao:
                            sessao.add(Analise(
                                nome=nome_usuario,
                                texto_original=texto,
                                resultado_ia=resultado['analise_completa'],
                                metricas=json.dumps(resultado['metricas'])
                            ))
                            sessao.commit()

                        mostrar_analise(resultado)

                        pdf_path = gerar_pdf_com_layout_oficial(resultado['analise_completa'])
                        with open(pdf_path, "rb") as f:
                            st.download_button("Baixar PDF", f, file_name="analise_tecnica.pdf")

                    except Exception as e:
                        st.error(f"Erro na análise: {str(e)}")

    with aba_historico:
        nome_hist = st.text_input("Digite seu nome para visualizar o histórico")
        if nome_hist:
            with Sessao() as sessao:
                analises = sessao.query(Analise).filter_by(nome=nome_hist).order_by(Analise.data_hora.desc()).all()
                if not analises:
                    st.info("Nenhuma análise encontrada para este nome.")
                else:
                    for item in analises:
                        with st.expander(f"Análise em {item.data_hora.strftime('%d/%m/%Y')}"):
                            st.markdown(item.resultado_ia, unsafe_allow_html=True)
                            if st.button(f"Baixar PDF #{item.id}", key=f"btn_{item.id}"):
                                caminho_pdf = gerar_pdf_com_layout_oficial(item.resultado_ia)
                                with open(caminho_pdf, "rb") as f:
                                    st.download_button("Baixar PDF", f, file_name=f"analise_{item.id}.pdf")

if __name__ == "__main__":
    main()
