from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import asyncpg

app = FastAPI()

# Configuração do banco de dados
DATABASE_URL = "postgresql://desjogandodb_user:BXbBkf9Rez43Nh4kbywfjVKgJisYX10w@dpg-cvkl6nd6ubrc73fqgosg-a/desjogandodb"

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

# Modelo de dados para finalizar aposta
class FinalizarAposta(BaseModel):
    vencedor: int

# Modelo de dados para fazer uma aposta
class Aposta(BaseModel):
    nome: str
    valor: int
    escolha: int

# Modelo de dados para adicionar pontos a um usuário
class AdicionarPontos(BaseModel):
    nome: str
    pontos: int

# Cria a tabela de usuários no banco de dados (se não existir)
@app.on_event("startup")
async def startup():
    conn = await connect_to_db()
    await conn.execute('''  
    CREATE TABLE IF NOT EXISTS usuarios (
        nome TEXT PRIMARY KEY,
        saldo INTEGER DEFAULT 5000
    );
    ''')
    await conn.execute('''
    CREATE TABLE IF NOT EXISTS saldo_apostas (
        id SERIAL PRIMARY KEY,
        saldo_total INTEGER DEFAULT 0
    );
    ''')
    await conn.execute('''
    CREATE TABLE IF NOT EXISTS apostas (
        id SERIAL PRIMARY KEY,
        nome TEXT,
        valor INTEGER,
        escolha INTEGER,
        ganhou BOOLEAN DEFAULT FALSE
    );
    ''')
    await conn.execute('''
    INSERT INTO saldo_apostas (id, saldo_total)
    VALUES (1, 0)
    ON CONFLICT (id) DO NOTHING;
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
        # Se o usuário não existir, cria o usuário com saldo inicial de 5000
        await conn.execute('INSERT INTO usuarios (nome, saldo) VALUES ($1, $2)', nome, 5000)
        saldo = 5000
    else:
        saldo = result["saldo"]
    
    await conn.close()
    return JSONResponse(content={"mensagem": f"Bem-vindo, {nome}!", "saldo": saldo})

# Rota para consultar o saldo do usuário
@app.get("/saldo/{nome}")
async def saldo(nome: str):
    conn = await connect_to_db()
    nome = nome.lower()
    
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        await conn.close()
        return JSONResponse(content={"erro": "Usuário não encontrado"})
    
    await conn.close()
    return JSONResponse(content={"nome": nome, "saldo": result["saldo"]})

# Nova rota para adicionar pontos a um usuário
@app.post("/adicionar-pontos")
async def adicionar_pontos(dados: AdicionarPontos):
    conn = await connect_to_db()
    nome = dados.nome.lower()
    pontos = dados.pontos
    
    # Verifica se o usuário existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    
    if result is None:
        # Se o usuário não existir, cria o usuário com o saldo sendo os pontos fornecidos
        await conn.execute('INSERT INTO usuarios (nome, saldo) VALUES ($1, $2)', nome, pontos)
        novo_saldo = pontos
        mensagem = f"Usuário {nome} criado com {pontos} pontos."
    else:
        # Se o usuário existir, adiciona os pontos ao saldo atual
        saldo_atual = result["saldo"]
        novo_saldo = saldo_atual + pontos
        await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, nome)
        mensagem = f"{pontos} pontos adicionados para {nome}."
    
    await conn.close()
    return JSONResponse(content={"sucesso": True, "mensagem": mensagem, "novo_saldo": novo_saldo})

# Rota para listar todos os usuários e seus saldos
@app.get("/usuarios")
async def listar_usuarios():
    conn = await connect_to_db()
    
    # Consulta para pegar todos os usuários e seus saldos, ordenados por saldo em ordem decrescente
    result = await conn.fetch('SELECT nome, saldo FROM usuarios ORDER BY saldo DESC')
    
    # Converte o resultado em uma lista de dicionários
    usuarios = [{"nome": row["nome"], "saldo": row["saldo"]} for row in result]
    
    await conn.close()
    
    # Retorna a lista de usuários
    return JSONResponse(content=usuarios)

# Variável global para controlar o estado da aposta
estado_aposta = 'não iniciada'

# Rota para iniciar uma aposta
@app.post("/aposta/iniciar")
async def iniciar_aposta():
    global estado_aposta, apostas_usuarios
    if estado_aposta == 'em andamento':
        return JSONResponse(content={"erro": "Aposta já está em andamento."})
    
    estado_aposta = 'em andamento'
    
    # Zera o saldo geral de apostas e limpa as apostas anteriores
    conn = await connect_to_db()
    await conn.execute('UPDATE saldo_apostas SET saldo_total = 0 WHERE id = 1')
    await conn.execute('DELETE FROM apostas')
    await conn.close()
    
    # Limpa as apostas dos usuários
    apostas_usuarios = {}
    
    return JSONResponse(content={"status": "Aposta iniciada com sucesso."})

# Rota para finalizar uma aposta
@app.post("/aposta/finalizar")
async def finalizar_aposta(finalizar_aposta: FinalizarAposta):
    global estado_aposta, apostas_usuarios
    if estado_aposta == 'não iniciada':
        return JSONResponse(content={"erro": "Nenhuma aposta em andamento."})
    
    estado_aposta = 'não iniciada'
    vencedor = finalizar_aposta.vencedor
    
    conn = await connect_to_db()
    
    # Pega o saldo total das apostas
    result = await conn.fetchrow('SELECT saldo_total FROM saldo_apostas WHERE id=1')
    saldo_total = result["saldo_total"]
    
    # Pega todas as apostas no vencedor
    apostas_vencedoras = await conn.fetch('SELECT nome, valor FROM apostas WHERE escolha=$1', vencedor)
    
    # Calcula o total apostado pelos vencedores
    total_apostado_pelos_vencedores = sum(aposta["valor"] for aposta in apostas_vencedoras)

    # Distribui proporcionalmente o saldo total entre os vencedores
    if total_apostado_pelos_vencedores > 0:
        for aposta in apostas_vencedoras:
            nome = aposta["nome"]
            valor_apostado = aposta["valor"]
            
            # Cálculo proporcional: (valor_apostado / total_apostado_pelos_vencedores) * saldo_total
            ganho = (valor_apostado / total_apostado_pelos_vencedores) * saldo_total

            saldo_atual = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
            novo_saldo = saldo_atual["saldo"] + int(ganho)  # Convertendo para inteiro para evitar valores fracionados
            
            # Atualiza o saldo do usuário
            await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, nome)
            await conn.execute('UPDATE apostas SET ganhou=TRUE WHERE nome=$1 AND escolha=$2', nome, vencedor)

    # Zera os totais apostados
    await conn.execute('DELETE FROM apostas')
    await conn.execute('UPDATE saldo_apostas SET saldo_total = 0 WHERE id = 1')
    
    await conn.close()
    
    # Reset apostas_usuarios dictionary
    apostas_usuarios = {}
    
    return JSONResponse(content={"status": "Aposta finalizada com sucesso."})

# Rota para verificar o status da aposta
@app.get("/aposta/status")
async def status_aposta():
    return JSONResponse(content={"status": estado_aposta})


# Variável global para armazenar as apostas dos usuários
apostas_usuarios = {}

# Rota para fazer uma aposta
@app.post("/apostar")
async def apostar(aposta: Aposta):
    global estado_aposta, apostas_usuarios

    if estado_aposta != 'em andamento':
        raise HTTPException(status_code=400, detail="Nenhuma aposta em andamento.")

    conn = await connect_to_db()
    nome = aposta.nome.lower()

    # Verifica se o usuário já fez uma aposta
    if nome in apostas_usuarios:
        await conn.close()
        raise HTTPException(status_code=400, detail="Você já fez uma aposta e não pode apostar novamente.")

    # Verifica se o usuário existe
    result = await conn.fetchrow('SELECT saldo FROM usuarios WHERE nome=$1', nome)
    if result is None:
        await conn.close()
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    saldo_atual = result["saldo"]

    # Verifica se o saldo é suficiente para a aposta
    if saldo_atual < aposta.valor:
        await conn.close()
        raise HTTPException(status_code=400, detail="Saldo insuficiente.")

    # Subtrai o valor apostado do saldo do usuário
    novo_saldo = saldo_atual - aposta.valor
    await conn.execute('UPDATE usuarios SET saldo=$1 WHERE nome=$2', novo_saldo, nome)

    # Adiciona o valor apostado ao saldo geral de apostas
    result = await conn.fetchrow('SELECT saldo_total FROM saldo_apostas WHERE id=1')
    saldo_total = result["saldo_total"] + aposta.valor
    await conn.execute('UPDATE saldo_apostas SET saldo_total=$1 WHERE id=1', saldo_total)

    # Salva a aposta do usuário
    await conn.execute('INSERT INTO apostas (nome, valor, escolha) VALUES ($1, $2, $3)', nome, aposta.valor, aposta.escolha)

    # Armazena a aposta do usuário na variável global
    apostas_usuarios[nome] = aposta.escolha

    await conn.close()

    return JSONResponse(content={"mensagem": f"Aposta de {aposta.valor} pontos realizada com sucesso.", "novo_saldo": novo_saldo})

# Rota para resetar o banco de dados e limpar as apostas dos usuários
@app.post("/reset")
async def reset_db():
    global apostas_usuarios, estado_aposta
    conn = await connect_to_db()
    await conn.execute('DELETE FROM apostas')
    await conn.execute('DELETE FROM usuarios')
    await conn.execute('DELETE FROM saldo_apostas')
    # Reinserir o registro inicial na tabela saldo_apostas
    await conn.execute('''
    INSERT INTO saldo_apostas (id, saldo_total)
    VALUES (1, 0)
    ON CONFLICT (id) DO NOTHING;
    ''')
    await conn.close()
    # Limpa as apostas dos usuários
    apostas_usuarios = {}
    estado_aposta = 'não iniciada'
    return JSONResponse(content={"mensagem": "Base de dados limpa com sucesso."})

# Rota para obter os totais apostados
@app.get("/totais_apostados")
async def obter_totais_apostados():
    conn = await connect_to_db()
    
    total_apostado1 = await conn.fetchval('SELECT COALESCE(SUM(valor), 0) FROM apostas WHERE escolha = 1')
    total_apostado2 = await conn.fetchval('SELECT COALESCE(SUM(valor), 0) FROM apostas WHERE escolha = 2')
    
    await conn.close()
    
    return JSONResponse(content={"totalApostado1": total_apostado1, "totalApostado2": total_apostado2})


# Rota para verificar se o usuário ganhou
@app.get("/verificar_ganhou")
async def verificar_ganhou(nome: str):
    conn = await connect_to_db()
    nome = nome.lower()
    
    # Verifica se o usuário ganhou
    result = await conn.fetchrow('SELECT valor FROM apostas WHERE nome=$1 AND ganhou=True', nome)
    
    if result:
        valor = result["valor"]
        await conn.close()
        return JSONResponse(content={"ganhou": True, "valor": valor})
    
    await conn.close()
    return JSONResponse(content={"ganhou": False})