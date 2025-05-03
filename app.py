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
import PyPDF2

# =============================================
# CSS
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
# BANCO DE DADOS
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

# =============================================
# IA
# =============================================
def configurar_ia():
    load_dotenv()
    return ChatOpenAI(
        model_name="gpt-4",
        temperature=0.3,
        max_tokens=2048,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )

def detectar_tipo_documento(texto):
    prompt_tipo = ChatPromptTemplate.from_template("""
Classifique o seguinte texto como um dos seguintes tipos: TCC, currículo, relatório financeiro, escopo de projeto de design. Responda apenas com o tipo.
Texto:
{texto}
""")
    ia = configurar_ia()
    return ia.predict(prompt_tipo.format(texto=texto)).strip().lower()

def criar_prompt_analise(tipo):
    if "tcc" in tipo:
        return ChatPromptTemplate.from_template("""
Você é um avaliador acadêmico. Analise o seguinte TCC quanto à linguagem técnica, estrutura, possíveis plágios, e forneça sugestões como um professor avaliador.
Texto: {escopo}
""")
    elif "curr" in tipo:
        return ChatPromptTemplate.from_template("""
Você é um especialista em RH. Avalie o seguinte currículo quanto à clareza, estrutura, impacto e apresente sugestões de melhorias.
Texto: {escopo}
""")
    elif "financeiro" in tipo:
        return ChatPromptTemplate.from_template("""
Você é um especialista financeiro. Avalie tecnicamente o seguinte relatório ou balanço, verificando coerência de dados, estrutura e erros comuns.
Texto: {escopo}
""")
    elif "design" in tipo:
        return ChatPromptTemplate.from_template("""
Você é um UX designer sênior. Analise este escopo de projeto de design com foco em clareza, organização de telas, navegação e fluxo. Sugira melhorias técnicas para ser enviado a desenvolvedores.
Texto: {escopo}
""")
    else:
        return ChatPromptTemplate.from_template("""
Analise tecnicamente o seguinte documento quanto a clareza, estrutura, linguagem técnica e possíveis erros.
Texto: {escopo}
""")

# =============================================
# PDF
# =============================================
def gerar_pdf_com_layout_oficial(texto, titulo="Relatório Oficial"):
    doc = SimpleDocTemplate("relatorio_oficial.pdf", pagesize=letter)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', fontName='Times-Roman', fontSize=16, textColor=colors.HexColor("#003366"), alignment=1, spaceAfter=20, leading=24)
    body_style = ParagraphStyle('BodyText', fontName='Times-Roman', fontSize=12, leading=14, alignment=4, spaceAfter=12)
    content = [Paragraph(titulo, title_style), Spacer(1, 12)]
    for par in texto.split('\n'):
        if par.strip():
            content.append(Paragraph(par.strip(), body_style))
            content.append(Spacer(1, 12))
    doc.build(content)
    return "relatorio_oficial.pdf"

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

def extrair_texto_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    texto = ""
    for page in pdf_reader.pages:
        texto += page.extract_text() + "\n"
    return texto

def main():
    configurar_pagina()
    engine, Sessao = configurar_banco_dados()
    ia = configurar_ia()

    st.title("Assistente Genial")
    st.markdown("Obtenha análises técnicas detalhadas de documentos com apoio de IA.")

    abas = st.tabs(["Nova Análise", "Histórico"])
    aba_analise, aba_historico = abas

    with aba_analise:
        with st.form("formulario_analise"):
            st.markdown("### Envie seu documento para análise")

            col1, col2 = st.columns(2)
            with col1:
                arquivo = st.file_uploader("Arquivo (.docx ou .pdf)", type=["docx", "pdf"])
            with col2:
                nome = st.text_input("Seu nome para salvar no histórico")

            texto = st.text_area("Ou cole o texto diretamente:", height=250)
            executar = st.form_submit_button("Executar Análise")

        if executar:
            if not (arquivo or texto.strip()) or not nome.strip():
                st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                with st.spinner("Executando análise..."):
                    try:
                        if arquivo:
                            if arquivo.name.endswith(".docx"):
                                doc = Document(arquivo)
                                texto = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                            elif arquivo.name.endswith(".pdf"):
                                texto = extrair_texto_pdf(arquivo)

                        tipo = detectar_tipo_documento(texto)
                        prompt = criar_prompt_analise(tipo).format(escopo=texto)
                        conteudo_final = ia.predict(prompt)

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
        nome_hist = st.text_input("Digite seu nome para ver o histórico")
        if nome_hist:
            with Sessao() as sessao:
                analises = sessao.query(Analise).filter_by(nome=nome_hist).order_by(Analise.data_hora.desc()).all()
                if not analises:
                    st.info("Nenhuma análise encontrada para este nome.")
                else:
                    for item in analises:
                        with st.expander(f"Análise em {item.data_hora.strftime('%d/%m/%Y %H:%M')}"):
                            st.markdown(item.resultado_ia)
                            if st.button(f"Baixar PDF #{item.id}", key=f"btn_{item.id}"):
                                caminho_pdf = gerar_pdf_com_layout_oficial(item.resultado_ia)
                                with open(caminho_pdf, "rb") as f:
                                    st.download_button("Download PDF", f, file_name=f"analise_{item.id}.pdf")

if __name__ == "__main__":
    main()
