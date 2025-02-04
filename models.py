from sqlalchemy import Column, Integer, String
from database import Base

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True)
    saldo = Column(Integer, default=100)  # Novo usuário começa com 100 pontos
