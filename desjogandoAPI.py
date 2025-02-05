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

# Rota para servir o index.html
@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r") as f:
        content = f.read()
    return HTMLResponse(content=content)

# Adicionando o CORS para permitir chamadas de qualquer origem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permite todas as origens
    allow_credentials=True,
    allow_methods=["*"],  # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"],  # Permite todos os cabeçalhos
)

# Conectando ao PostgreSQL
async def connect_to_db():
    return await asyncpg.connect(DATABASE_URL)

# Modelo de dados do usuário
class Usuario(BaseModel):
    nome: str

# Cria a tabela de usuários no banco de dados (se não existir)
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
    CREATE TABLE IF NOT EXISTS saldo_apostas (
        id SERIAL PRIMARY KEY,
        saldo_total INTEGER DEFAULT 0
    );
    ''')
    await conn.close()

# Rota para login do usuário
@app.post("/login")
async def login(usuario: Usuario):
    conn = await connect_to_db()
    nome = usuario.nome.lower()
    
    # Verifica se o usuário já existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        # Se o usuário não existir, cria o usuário com saldo inicial de 100
        await conn.execute('INSERT INTO usuarios (nome, saldo) VALUES ($1, $2)', nome, 100)
        saldo = 100
    else:
        saldo = result["saldo"]
    
    await conn.close()
    return {"mensagem": f"Bem-vindo, {nome}!", "saldo": saldo}

# Rota para consultar o saldo do usuário
@app.get("/saldo/{nome}")
async def saldo(nome: str):
    conn = await connect_to_db()
    nome = nome.lower()
    
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        await conn.close()
        return {"erro": "Usuário não encontrado"}
    
    await conn.close()
    return {"nome": nome, "saldo": result["saldo"]}

# Rota para listar todos os usuários e seus saldos
@app.get("/usuarios")
async def listar_usuarios():
    conn = await connect_to_db()
    
    # Consulta para pegar todos os usuários e seus saldos
    result = await conn.fetch('SELECT nome, saldo FROM usuarios')
    
    # Converte o resultado em uma lista de dicionários
    usuarios = [{"nome": row["nome"], "saldo": row["saldo"]} for row in result]
    
    await conn.close()
    
    # Retorna a lista de usuários
    return usuarios

# Variável global para controlar o estado da aposta
estado_aposta = 'não iniciada'

# Rota para iniciar uma aposta
@app.post("/aposta/iniciar")
async def iniciar_aposta():
    global estado_aposta
    if estado_aposta == 'em andamento':
        return {"erro": "Aposta já está em andamento."}
    
    estado_aposta = 'em andamento'
    
    # Zera o saldo geral de apostas
    conn = await connect_to_db()
    await conn.execute('UPDATE saldo_apostas SET saldo_total = 0 WHERE id = 1')
    await conn.close()
    
    return {"status": "Aposta iniciada com sucesso."}

# Rota para finalizar uma aposta
@app.post("/aposta/finalizar")
async def finalizar_aposta():
    global estado_aposta
    if estado_aposta == 'não iniciada':
        return {"erro": "Nenhuma aposta em andamento."}
    
    estado_aposta = 'não iniciada'
    
    conn = await connect_to_db()
    
    # Pega o saldo total das apostas
    result = await conn.fetchrow('SELECT saldo_total FROM saldo_apostas WHERE id=1')
    saldo_total = result["saldo_total"]
    
    # Pega todos os usuários
    usuarios = await conn.fetch('SELECT nome, saldo FROM usuarios')
    
    # Divide o saldo total entre todos os usuários
    if usuarios:
        valor_por_usuario = saldo_total // len(usuarios)
        for usuario in usuarios:
            novo_saldo = usuario["saldo"] + valor_por_usuario
            await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, usuario["nome"])
    
    await conn.close()
    
    return {"status": "Aposta finalizada com sucesso."}

# Rota para verificar o status da aposta
@app.get("/aposta/status")
async def status_aposta():
    return {"status": estado_aposta}

# Rota para fazer uma aposta
@app.post("/apostar")
async def apostar(nome: str, valor: int, escolha: int):
    conn = await connect_to_db()
    nome = nome.lower()

    # Verifica se o usuário existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    if result is None:
        await conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    saldo_atual = result["saldo"]

    # Verifica se o saldo é suficiente para a aposta
    if saldo_atual < valor:
        await conn.close()
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    # Subtrai o valor apostado do saldo do usuário
    novo_saldo = saldo_atual - valor
    await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, nome)

    # Adiciona o valor apostado ao saldo geral de apostas
    result = await conn.fetchrow('SELECT saldo_total FROM saldo_apostas WHERE id=1')
    saldo_total = result["saldo_total"] + valor
    await conn.execute('UPDATE saldo_apostas SET saldo_total=$1 WHERE id=1', saldo_total)

    await conn.close()

    return {"mensagem": f"Aposta de {valor} pontos realizada com sucesso.", "novo_saldo": novo_saldo}

# Rota para listar todos os usuários e seus saldos (duplicada, removida)
# @app.get("/usuarios")
# async def listar_usuarios():
#     conn = await connect_to_db()
#     users = await conn.fetch("SELECT nome, saldo FROM usuarios")
#     await conn.close()
    
#     return [{"nome": user["nome"], "saldo": user["saldo"]} for user in users]