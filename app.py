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
from langchain.schema import HumanMessage
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import pdfplumber
import tempfile
from PIL import Image
import io
import base64

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
        page_title="Joana",
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
    tipo = Column(String(50))
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
        if 'tipo' not in colunas:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE analises ADD COLUMN tipo TEXT'))
        if 'nome' not in colunas:
            with engine.connect() as conn:
                conn.execute(text('ALTER TABLE analises ADD COLUMN nome TEXT'))

    return engine, Session

def configurar_ia():
    load_dotenv()
    chave = os.getenv("OPENROUTER_API_KEY")
    if not chave:
        st.error("A chave da API do OpenRouter não foi encontrada. Por favor, defina OPENROUTER_API_KEY no arquivo .env.")
        st.stop()
    return ChatOpenAI(
        model_name="mistralai/mistral-7b-instruct",
        temperature=0.3,
        max_tokens=2048,
        openai_api_key=chave,
        base_url="https://openrouter.ai/api/v1"
    )

# =============================================
# PROMPT DE ANÁLISE
# =============================================
def criar_prompt_analise(tipo):
    if tipo == "escopo":
        return ChatPromptTemplate.from_template("""
        Você é um consultor técnico sênior em gestão de projetos. Analise o escopo fornecido de forma criteriosa, considerando os seguintes aspectos:
        - Clareza e objetividade dos objetivos
        - Coerência entre entregas, prazos e recursos
        - Identificação de riscos, premissas e restrições
        - Conformidade com boas práticas de planejamento
        - Sugerir melhorias técnicas e operacionais

        ESCOPO: {texto}
        """)
    elif tipo == "design":
        return ChatPromptTemplate.from_template("""
        Você é um analista UX/UI. Avalie esta imagem de projeto:
        - Fluxo de telas
        - Elementos visuais
        - Sugestões de melhorias
        """)
    elif tipo == "TCC":
        return ChatPromptTemplate.from_template("""
        Você é um especialista em TCC. Analise:
        - Linguagem técnica
        - Estrutura acadêmica
        - Possíveis plágios

        TEXTO: {texto}
        """)
    elif tipo == "currículo":
        return ChatPromptTemplate.from_template("""
        Você é um especialista em RH. Avalie este currículo:
        - Clareza e organização
        - Pontos fortes/fracos
        - Sugestões profissionais

        TEXTO: {texto}
        """)
    elif tipo == "financeiro":
        return ChatPromptTemplate.from_template("""
        Você é um analista financeiro. Avalie:
        - Correção de balanços
        - Riscos contábeis
        - Sugestões

        TEXTO: {texto}
        """)
    else:
        return ChatPromptTemplate.from_template("""
        Analise este documento criticamente:
        - Pontos-chave
        - Problemas detectados
        - Recomendações

        TEXTO: {texto}
        """)

# =====================================
def analyze_content(conteudo, tipo, ia):
    if tipo == "design":
        prompt = criar_prompt_analise("design")
        mensagens = prompt.format_messages()
        mensagens.insert(0, HumanMessage(content="Imagem enviada"))
    else:
        prompt = criar_prompt_analise(tipo.lower())
        mensagens = prompt.format_messages(texto=conteudo)

    resposta = ia(mensagens)
    return resposta.content

# =============================================
# GERAÇÃO DE PDF
# =============================================
def gerar_pdf_com_layout_oficial(texto, titulo="Relatório"):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40,
        title=titulo
    )

    styles = getSampleStyleSheet()
    estilo_titulo = styles['Heading1']
    estilo_titulo.alignment = 1  # Centralizado
    estilo_paragrafo = styles['Normal']
    estilo_paragrafo.fontSize = 11
    estilo_paragrafo.leading = 16

    conteudo = []

    # Título
    conteudo.append(Paragraph(titulo, estilo_titulo))
    conteudo.append(Spacer(1, 20))

    # Corpo do texto, quebrado por parágrafos
    for paragrafo in texto.strip().split('\n'):
        if paragrafo.strip():
            conteudo.append(Paragraph(paragrafo.strip(), estilo_paragrafo))
            conteudo.append(Spacer(1, 10))

    doc.build(conteudo)
    buffer.seek(0)
    return buffer

# =============================================
# EXTRAÇÃO DE TEXTO
# =============================================
def extrair_texto(arquivo, nome_arquivo):
    nome = nome_arquivo.lower()
    if nome.endswith(".docx"):
        doc = Document(arquivo)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
    elif nome.endswith(".pdf"):
        with pdfplumber.open(arquivo) as pdf:
            return "\n".join(page.extract_text() or '' for page in pdf.pages)
    else:
        return ""

# =============================================
# MAIN
# =============================================
def main():
    configurar_pagina()
    engine, Sessao = configurar_banco_dados()
    ia = configurar_ia()

    st.title("Joana")
    st.markdown("Obtenha análises técnicas detalhadas de documentos variados com apoio de IA.")

    abas = st.tabs(["Nova Análise", "Histórico"])
    aba_analise, aba_historico = abas

    with aba_analise:
        st.header("Enviar novo documento")

        col1, col2 = st.columns(2)
        with col1:
            uploaded_file = st.file_uploader("Carregar arquivo", type=['pdf', 'docx', 'png', 'jpg'])
        with col2:
            user_name = st.text_input("Seu nome", max_chars=50)

        doc_type = st.selectbox("Tipo de documento", [
            "Escopo", "TCC", "Currículo", "Financeiro", "Design", "Outro"
        ])

        manual_text = st.text_area("Ou cole o texto aqui", height=150)

        if st.button("Analisar", type="primary"):
            if not (uploaded_file or manual_text.strip()) or not user_name.strip():
                st.error("Preencha todos os campos obrigatórios")
            else:
                with st.spinner("Processando..."):
                    try:
                        if uploaded_file:
                            file_content = uploaded_file.read()
                            if uploaded_file.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                                file_type = 'imagem'
                                content_to_analyze = file_content
                            else:
                                file_type = 'texto'
                                content_to_analyze = extrair_texto(uploaded_file, uploaded_file.name)
                        else:
                            file_type = 'texto'
                            content_to_analyze = manual_text
                        
                        analysis_result = analyze_content(content_to_analyze, doc_type, ia)
                        
                        with Sessao() as session:
                            session.add(Analise(
                                nome=user_name,
                                tipo=doc_type,
                                texto_original=content_to_analyze[:10000],
                                resultado_ia=analysis_result
                            ))
                            session.commit()
                        
                        st.success("Análise concluída!")
                        st.markdown(f"**Resultado:**\n\n{analysis_result}")
                        
                        buffer = gerar_pdf_com_layout_oficial(analysis_result)
                        st.download_button("📄 Baixar PDF", data=buffer, file_name="relatorio.pdf", mime="application/pdf", key="download_nova_analise")
                    
                    except Exception as e:
                        st.error(f"Erro: {str(e)}")

    with aba_historico:
        nome_hist = st.text_input("Digite seu nome para ver o histórico", max_chars=30)
        tipo_filtro = st.selectbox("Filtrar por tipo de documento", ["Todos", "Escopo", "TCC", "Currículo", "Financeiro", "Design", "Outro"])
        st.caption(f"{len(nome_hist)}/30 caracteres")

        if nome_hist:
            with Sessao() as sessao:
                analises = sessao.query(Analise).filter_by(nome=nome_hist).order_by(Analise.data_hora.desc()).all()
                if tipo_filtro != "Todos":
                    analises = [a for a in analises if a.tipo.lower() == tipo_filtro.lower()]

                if not analises:
                    st.info("Nenhuma análise encontrada para este nome e filtro.")
                else:
                    for item in analises:
                        with st.expander(f"Análise em {item.data_hora.strftime('%d/%m/%Y %H:%M')}"):
                            st.markdown(item.resultado_ia)

                            buffer = gerar_pdf_com_layout_oficial(item.resultado_ia, titulo="Relatório de Análise")
                            st.download_button(
                                label="📄 Baixar PDF",
                                data=buffer,
                                file_name="relatorio.pdf",
                                mime="application/pdf",
                                key=f"download_pdf_{item.id}"
                            )

if __name__ == "__main__":
    main()
