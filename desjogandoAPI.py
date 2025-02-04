from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

# Servindo arquivos estáticos da pasta 'static'
app.mount("/static", StaticFiles(directory="static"), name="static")

# Rota para servir o arquivo index.html
@app.get("/")
async def read_index():
    index_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    
    # Verificar se o arquivo existe antes de tentar servi-lo
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            return f.read()
    else:
        return {"detail": "index.html não encontrado"}

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
