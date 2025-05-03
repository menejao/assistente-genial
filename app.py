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
import pdfplumber
import tempfile
from PIL import Image
import io

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

    return engine, Session


def configurar_ia():
    load_dotenv()
    chave = os.getenv("OPENAI_API_KEY")
    if not chave:
        st.error("A chave da API da OpenAI não foi encontrada. Por favor, defina OPENAI_API_KEY no arquivo .env.")
        st.stop()
    return ChatOpenAI(
        model_name="gpt-4-vision-preview",
        temperature=0.3,
        max_tokens=2048,
        openai_api_key=chave
    )

# =============================================
# DETECÇÃO DO TIPO DE DOCUMENTO
# =============================================
def detectar_tipo_documento(texto):
    if any(palavra in texto.lower() for palavra in ["resumo", "referencial teórico", "metodologia", "conclusão"]):
        return "TCC"
    elif any(palavra in texto.lower() for palavra in ["experiência profissional", "objetivo profissional", "formação acadêmica"]):
        return "currículo"
    elif any(palavra in texto.lower() for palavra in ["ativo", "passivo", "demonstrativo", "balanço patrimonial", "fluxo de caixa"]):
        return "financeiro"
    elif any(palavra in texto.lower() for palavra in ["tela", "fluxo de navegação", "wireframe", "layout", "ux", "ui"]):
        return "design"
    else:
        return "geral"

# =============================================
# PROMPT DE ANÁLISE
# =============================================
def criar_prompt_analise(tipo):
    if tipo == "design":
        return ChatPromptTemplate.from_template("""
Você é um analista UX/UI. Avalie este escopo de projeto de design com base na imagem apresentada:
- Identifique fluxos de tela, elementos principais e funcionalidades implícitas.
- Sugira melhorias técnicas e coerência para desenvolvedores.

## ANÁLISE DETALHADA DA TELA DO PROJETO UX/UI
Imagem: {escopo}
""")
    elif tipo == "TCC":
        return ChatPromptTemplate.from_template("""
Você é um especialista em avaliação de TCCs. Realize uma análise como um professor avaliaria:
- Avalie linguagem técnica.
- Julgue estrutura acadêmica.
- Detecte possíveis traços de plágio.

## ANÁLISE DETALHADA...
Texto: {escopo}
""")
    elif tipo == "currículo":
        return ChatPromptTemplate.from_template("""
Você é um especialista em RH. Avalie este currículo:
- Clareza, organização, impacto.
- Pontos fortes e fracos.
- Sugestões profissionais.

## ANÁLISE DETALHADA...
Texto: {escopo}
""")
    elif tipo == "financeiro":
        return ChatPromptTemplate.from_template("""
Você é um analista financeiro. Avalie tecnicamente este relatório:
- Correção de balanços.
- Inconsistências contábeis.
- Sugestões e riscos percebidos.

## ANÁLISE DETALHADA...
Texto: {escopo}
""")
    else:
        return ChatPromptTemplate.from_template("""
Você é um especialista em avaliação de documentos. Analise o conteúdo abaixo com criticidade, clareza e sugestões.

## ANÁLISE DETALHADA...
Texto: {escopo}
""")

# =============================================
# GERAÇÃO DE PDF
# =============================================
def gerar_pdf_com_layout_oficial(texto, titulo="Relatório Oficial"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", dir="/tmp") as temp_pdf:
        caminho_pdf = temp_pdf.name

    doc = SimpleDocTemplate(caminho_pdf, pagesize=letter,
                            rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontName='Times-Roman', fontSize=16,
                                 textColor=colors.HexColor("#003366"), alignment=1, spaceAfter=20, leading=24)
    body_style = ParagraphStyle('BodyText', fontName='Times-Roman', fontSize=12,
                                leading=14, alignment=4, spaceAfter=12)
    content = [Paragraph(titulo, title_style), Spacer(1, 12)]
    for par in texto.split('\n'):
        if par.strip():
            content.append(Paragraph(par.strip(), body_style))
            content.append(Spacer(1, 12))
    doc.build(content)
    return caminho_pdf

# =============================================
# INTERFACE
# =============================================
def mostrar_analise(resultado):
    st.subheader("Resultado da Análise")
    st.markdown(f"""
<div class='resultado'>
{resultado['analise_completa']}
</div>
""", unsafe_allow_html=True)

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

    st.title("Assistente Genial")
    st.markdown("Obtenha análises técnicas detalhadas de documentos variados com apoio de IA.")

    abas = st.tabs(["Nova Análise", "Histórico"])
    aba_analise, aba_historico = abas

    with aba_analise:
        st.markdown("### Envie seu documento ou imagem para análise")

        col1, col2 = st.columns(2)
        with col1:
            arquivo = st.file_uploader("Arquivo (.docx, .pdf ou imagem .png/.jpg)", type=["docx", "pdf", "png", "jpg", "jpeg"])
        with col2:
            nome = st.text_input("Seu nome para salvar no histórico", max_chars=30)
            st.caption(f"{len(nome)}/30 caracteres")

        with st.form("formulario_analise"):
            st.info("Aceita documentos e também imagens de projetos UX/UI.")
            texto = st.text_area("Ou cole o texto do documento:", height=250)
            executar = st.form_submit_button("Executar Análise")

        if executar:
            if not (arquivo or texto.strip()) or not nome.strip():
                st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                with st.spinner("Executando análise..."):
                    try:
                        if arquivo:
                            nome_arquivo = arquivo.name.lower()
                            conteudo = arquivo.read()
                            arquivo.seek(0)

                            if nome_arquivo.endswith(('.png', '.jpg', '.jpeg')):
                                imagem = Image.open(io.BytesIO(conteudo))
                                tipo = "design"
                                prompt_template = criar_prompt_analise(tipo)
                                prompt = prompt_template.format(escopo="[imagem de interface UX/UI enviada]")
                                conteudo_final = ia.predict(prompt.to_messages())
                                texto = "Imagem analisada. Resultado abaixo."
                            else:
                                texto = extrair_texto(arquivo, nome_arquivo)
                                tipo = detectar_tipo_documento(texto)
                                prompt_template = criar_prompt_analise(tipo)
                                prompt = prompt_template.format(escopo=texto)
                                conteudo_final = ia.predict(prompt.to_messages())

                        elif texto:
                            tipo = detectar_tipo_documento(texto)
                            prompt_template = criar_prompt_analise(tipo)
                            prompt = prompt_template.format(escopo=texto)
                            conteudo_final = ia.predict(prompt.to_messages())

                        resultado = {
                            'analise_completa': conteudo_final,
                            'metricas': {
                                'clareza': 4.2,
                                'linguagem': 4.5,
                                'estrutura': 4.1,
                                'originalidade': 4.0
                            }
                        }

                        with Sessao() as sessao:
                            sessao.add(Analise(
                                nome=nome,
                                texto_original=texto,
                                resultado_ia=conteudo_final,
                                metricas=json.dumps(resultado['metricas'])
                            ))
                            sessao.commit()

                        mostrar_analise(resultado)

                        pdf_path = gerar_pdf_com_layout_oficial(conteudo_final)
                        with open(pdf_path, "rb") as f:
                            st.download_button("Baixar PDF", f, file_name="analise_documento.pdf")

                    except Exception as e:
                        st.error(f"Erro na análise: {str(e)}")

    with aba_historico:
        nome_hist = st.text_input("Digite seu nome para ver o histórico", max_chars=30)
        tipo_filtro = st.selectbox("Filtrar por tipo de documento", ["Todos", "TCC", "currículo", "financeiro", "design", "geral"])
        st.caption(f"{len(nome_hist)}/30 caracteres")

        if nome_hist:
            with Sessao() as sessao:
                analises = sessao.query(Analise).filter_by(nome=nome_hist).order_by(Analise.data_hora.desc()).all()
                if tipo_filtro != "Todos":
                    analises = [a for a in analises if detectar_tipo_documento(a.texto_original) == tipo_filtro]

                if not analises:
                    st.info("Nenhuma análise encontrada para este nome e filtro.")
                else:
                    for item in analises:
                        with st.expander(f"Análise em {item.data_hora.strftime('%d/%m/%Y %H:%M')}"):
                            st.markdown(item.resultado_ia)
                            caminho_pdf = gerar_pdf_com_layout_oficial(item.resultado_ia, titulo="Relatório de Análise")
                            with open(caminho_pdf, "rb") as f:
                                st.download_button(
                                    label="Download PDF",
                                    data=f,
                                    file_name=f"analise_{item.id}.pdf",
                                    mime="application/pdf",
                                    key=f"download_{item.id}"
                                )

if __name__ == "__main__":
    main()
