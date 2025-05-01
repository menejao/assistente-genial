
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class Analise(Base):
    __tablename__ = 'analises'
    id = Column(Integer, primary_key=True)
    email = Column(String, nullable=False)
    texto_original = Column(Text, nullable=False)
    resultado_ia = Column(Text, nullable=False)
    data_hora = Column(DateTime, default=datetime.now)

engine = create_engine('sqlite:///analises.db')
Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)
