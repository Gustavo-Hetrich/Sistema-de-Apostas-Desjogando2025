from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import asyncpg
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = "postgresql://desjogandosql_user:isUyPC80jvkVlcE5iA4YboRmFqJRPAtM@dpg-cuh4kd0gph6c73dknn10-a.oregon-postgres.render.com/desjogandosql"

# Servindo arquivos estáticos da pasta 'static'
app.mount("/static", StaticFiles(directory="static"), name="static")

# Adicionando o CORS para permitir chamadas de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectando ao PostgreSQL
async def connect_to_db():
    return await asyncpg.connect(DATABASE_URL)

# Modelo de dados para aposta
class Aposta(BaseModel):
    nome: str
    valor: int
    escolha: int  # 1 ou 2

@app.on_event("startup")
async def startup():
    conn = await connect_to_db()
    await conn.execute('''  
    CREATE TABLE IF NOT EXISTS usuarios (
        nome TEXT PRIMARY KEY,
        saldo INTEGER DEFAULT 100
    );
    ''')
    await conn.execute('''
    CREATE TABLE IF NOT EXISTS apostas (
        id SERIAL PRIMARY KEY,
        nome TEXT REFERENCES usuarios(nome),
        valor INTEGER NOT NULL,
        escolha INTEGER NOT NULL CHECK (escolha IN (1, 2))
    );
    ''')
    await conn.execute('''
    CREATE TABLE IF NOT EXISTS rodada (
        id SERIAL PRIMARY KEY,
        ativa BOOLEAN DEFAULT FALSE
    );
    ''')
    await conn.close()

@app.post("/apostar")
async def apostar(aposta: Aposta):
    conn = await connect_to_db()
    nome = aposta.nome.lower()

    # Verifica se há uma rodada ativa
    rodada = await conn.fetchrow('SELECT ativa FROM rodada ORDER BY id DESC LIMIT 1')
    if not rodada or not rodada["ativa"]:
        await conn.close()
        raise HTTPException(status_code=400, detail="Nenhuma aposta está em andamento no momento.")

    # Verifica se o usuário tem saldo suficiente
    saldo_atual = await conn.fetchval('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    if saldo_atual is None:
        await conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if aposta.valor > saldo_atual:
        await conn.close()
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    # Subtrai o valor apostado do saldo do usuário
    novo_saldo = saldo_atual - aposta.valor
    await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, nome)

    # Registra a aposta
    await conn.execute('INSERT INTO apostas (nome, valor, escolha) VALUES ($1, $2, $3)', nome, aposta.valor, aposta.escolha)

    await conn.close()
    return {"mensagem": "Aposta realizada com sucesso!", "novo_saldo": novo_saldo}
