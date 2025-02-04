from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Adicionando o CORS para permitir chamadas de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite requisições de qualquer origem
    allow_credentials=True,
    allow_methods=["*"],  # Permite qualquer método (GET, POST, etc.)
    allow_headers=["*"],  # Permite qualquer cabeçalho
)

# Simulando um banco de dados em memória
usuarios: Dict[str, int] = {}

class Usuario(BaseModel):
    nome: str

@app.post("/login")
async def login(usuario: Usuario):
    nome = usuario.nome.lower()
    
    if nome not in usuarios:
        usuarios[nome] = 100  # Usuário novo começa com 100 pontos
    
    return {"mensagem": f"Bem-vindo, {nome}!", "saldo": usuarios[nome]}

@app.get("/saldo/{nome}")
async def saldo(nome: str):
    nome = nome.lower()
    
    if nome not in usuarios:
        return {"erro": "Usuário não encontrado"}
    
    return {"nome": nome, "saldo": usuarios[nome]}
