from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import asyncpg
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import random

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = "postgresql://desjogandosql_user:isUyPC80jvkVlcE5iA4YboRmFqJRPAtM@dpg-cuh4kd0gph6c73dknn10-a.oregon-postgres.render.com/desjogandosql"

# Servindo arquivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Adicionando CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectar ao banco de dados
async def connect_to_db():
    return await asyncpg.connect(DATABASE_URL)

# Modelos de dados
class Usuario(BaseModel):
    nome: str

class Aposta(BaseModel):
    nome: str
    valor: int
    escolha: int  # 1 ou 2

# Criar tabelas no banco de dados ao iniciar a API
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

# Rota para login (cria usuário se não existir)
@app.post("/login")
async def login(usuario: Usuario):
    conn = await connect_to_db()
    nome = usuario.nome.lower()
    
    # Verifica se o usuário já existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        # Se o usuário não existir, cria com saldo inicial de 100
        await conn.execute('INSERT INTO usuarios (nome, saldo) VALUES ($1, $2)', nome, 100)
        saldo = 100
    else:
        saldo = result["saldo"]
    
    await conn.close()
    return {"mensagem": f"Bem-vindo, {nome}!", "saldo": saldo}

# Rota para iniciar uma rodada de apostas
@app.post("/aposta/iniciar")
async def iniciar_aposta():
    conn = await connect_to_db()
    
    # Verifica se já há uma rodada ativa
    rodada = await conn.fetchrow('SELECT ativa FROM rodada ORDER BY id DESC LIMIT 1')
    if rodada and rodada["ativa"]:
        await conn.close()
        return {"erro": "Já existe uma rodada ativa."}

    # Inicia uma nova rodada
    await conn.execute('INSERT INTO rodada (ativa) VALUES (TRUE)')
    
    await conn.close()
    return {"status": "Rodada de apostas iniciada."}

# Rota para fazer uma aposta
@app.post("/apostar")
async def apostar(aposta: Aposta):
    conn = await connect_to_db()
    nome = aposta.nome.lower()

    # Verifica se há uma rodada ativa
    rodada = await conn.fetchrow('SELECT ativa FROM rodada ORDER BY id DESC LIMIT 1')
    if not rodada or not rodada["ativa"]:
        await conn.close()
        raise HTTPException(status_code=400, detail="Nenhuma aposta está em andamento.")

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

# Rota para finalizar uma rodada e calcular os vencedores
@app.post("/aposta/finalizar")
async def finalizar_aposta():
    conn = await connect_to_db()

    # Verifica se há uma rodada ativa
    rodada = await conn.fetchrow('SELECT ativa FROM rodada ORDER BY id DESC LIMIT 1')
    if not rodada or not rodada["ativa"]:
        await conn.close()
        raise HTTPException(status_code=400, detail="Nenhuma aposta está em andamento.")

    # Gera um resultado aleatório (1 ou 2)
    resultado = random.choice([1, 2])

    # Busca todos os apostadores e valores
    apostas = await conn.fetch('SELECT nome, valor, escolha FROM apostas')
    
    # Lista de vencedores
    vencedores = [aposta for aposta in apostas if aposta["escolha"] == resultado]

    if vencedores:
        total_apostado = sum(aposta["valor"] for aposta in apostas)
        premio_por_vencedor = total_apostado // len(vencedores)

        for vencedor in vencedores:
            novo_saldo = await conn.fetchval('SELECT saldo FROM usuarios WHERE nome=$1', vencedor["nome"])
            novo_saldo += premio_por_vencedor
            await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, vencedor["nome"])

    # Limpa apostas e finaliza rodada
    await conn.execute('DELETE FROM apostas')
    await conn.execute('UPDATE rodada SET ativa=FALSE WHERE ativa=TRUE')

    await conn.close()
    return {
        "mensagem": "Aposta finalizada!",
        "resultado": resultado,
        "vencedores": [v["nome"] for v in vencedores] if vencedores else "Nenhum vencedor"
    }

# Rota para verificar o status da aposta
@app.get("/aposta/status")
async def status_aposta():
    conn = await connect_to_db()
    rodada = await conn.fetchrow('SELECT ativa FROM rodada ORDER BY id DESC LIMIT 1')
    await conn.close()
    
    status = "em andamento" if rodada and rodada["ativa"] else "não iniciada"
    return {"status": status}

# Rota para listar usuários e saldos
@app.get("/usuarios")
async def listar_usuarios():
    conn = await connect_to_db()
    users = await conn.fetch("SELECT nome, saldo FROM usuarios")
    await conn.close()
    
    return [{"nome": user["nome"], "saldo": user["saldo"]} for user in users]
