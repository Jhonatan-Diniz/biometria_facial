"""
Banco de dados SQLite e criptografia dos embeddings.

Duas garantias importantes deste modulo:

1. NUNCA guardamos fotos. Guardamos somente o embedding (vetor de 128
   numeros), que e a "identidade numerica" do rosto. A foto original e
   descartada assim que o embedding e extraido.

2. O embedding e gravado CRIPTOGRAFADO com Fernet (simetrica, da
   biblioteca `cryptography`). A chave fica em data/chave.key.
   Se alguem copiar o arquivo .db sem a chave, nao consegue ler
   os embeddings.
"""

import datetime
import os
import sqlite3

import numpy as np
from cryptography.fernet import Fernet, InvalidToken

from app import config

# Objeto de criptografia, criado uma unica vez
_FERNET = None


# ------------------------------------------------------------------
# Chave e criptografia
# ------------------------------------------------------------------

def _proteger_arquivo(caminho):
    """
    Tenta restringir o acesso ao arquivo da chave.
    Em Windows o chmod e limitado, entao ignoramos o erro de proposito:
    o objetivo aqui e apenas omelhorar a situacao no Linux/macOS.
    """
    try:
        os.chmod(caminho, 0o600)
    except OSError:
        pass


def carregar_chave():
    """
    Devolve a chave Fernet, gerando-a na primeira execução.
    Perder esse arquivo significa perder todos os embeddings gravados.
    """
    config.garantir_pastas()

    if not os.path.exists(config.KEY_PATH):
        chave = Fernet.generate_key()
        with open(config.KEY_PATH, "wb") as arquivo:
            arquivo.write(chave)
        _proteger_arquivo(config.KEY_PATH)
        print(f"[INFO] Chave de criptografia criada em: {config.KEY_PATH}")

    with open(config.KEY_PATH, "rb") as arquivo:
        return arquivo.read().strip()


def _fernet():
    """Instancia (uma vez) o objeto Fernet usado para cifrar e decifrar."""
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(carregar_chave())
    return _FERNET


def cifrar_embedding(embedding):
    """
    Transforma o embedding em bytes e criptografa.
    Devolve os bytes, prontos para gravar na coluna BLOB.
    """
    dados = np.asarray(embedding, dtype=np.float32).tobytes()
    return _fernet().encrypt(dados)


def decifrar_embedding(bytes_cifrados):
    """
    Descriptografa os bytes do banco e devolve o embedding como
    numpy array de shape (128,).

    Leva ValueError se a chave estiver errada ou os dados corrompidos.
    """
    try:
        dados = _fernet().decrypt(bytes_cifrados)
    except InvalidToken as erro:
        raise ValueError(
            "Nao foi possivel decifrar o embedding. "
            "Provavelmente a chave (data/chave.key) nao corresponde a este banco."
        ) from erro

    embedding = np.frombuffer(dados, dtype=np.float32)
    if embedding.size != config.EMBEDDING_SIZE:
        raise ValueError(
            f"Embedding com tamanho inesperado: {embedding.size} (esperado {config.EMBEDDING_SIZE})"
        )
    # frombuffer devolve um array somente-leitura; copiamos para poder usar
    return embedding.copy()


# ------------------------------------------------------------------
# Conexao e schema
# ------------------------------------------------------------------

def conectar():
    """Abre uma conexao com o banco, ja garantindo que o schema existe."""
    config.garantir_pastas()

    conexao = sqlite3.connect(config.DB_PATH)
    conexao.row_factory = sqlite3.Row
    conexao.execute("PRAGMA foreign_keys = ON")
    criar_schema(conexao)
    return conexao


def criar_schema(conexao):
    """Cria as tabelas se ainda nao existirem. Idempotente."""
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id        TEXT PRIMARY KEY,
            nome      TEXT NOT NULL,
            nivel     INTEGER NOT NULL CHECK (nivel IN (1, 2, 3)),
            criado_em TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS embeddings (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id   TEXT NOT NULL,
            embedding BLOB NOT NULL,
            criado_em TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora   TEXT NOT NULL,
            user_id    TEXT,
            recurso    TEXT,
            nivel      INTEGER,
            distancia  REAL,
            limiar     REAL,
            resultado  TEXT NOT NULL,
            detalhe    TEXT,
            origem     TEXT
        );

        CREATE TABLE IF NOT EXISTS rural_properties (
            codigo                  TEXT PRIMARY KEY,
            nome                    TEXT NOT NULL,
            municipio               TEXT NOT NULL,
            estado                  TEXT NOT NULL,
            substancia              TEXT NOT NULL,
            periodo_uso             TEXT NOT NULL,
            situacao_monitoramento  TEXT NOT NULL,
            prioridade              TEXT NOT NULL,
            poco                    TEXT NOT NULL,
            profundidade_poco_m     REAL NOT NULL,
            concentracao_ug_l       REAL NOT NULL,
            referencia_ug_l         REAL NOT NULL,
            amostra_em              TEXT NOT NULL,
            medida_resposta         TEXT NOT NULL,
            nota_tecnica             TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_embeddings_user ON embeddings(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_data ON audit_log(data_hora);
        """
    )
    criar_dados_ficticios(conexao)
    conexao.commit()


def criar_dados_ficticios(conexao):
    """Insere casos ambientais explicitamente fictícios, sem duplicá-los."""
    propriedades = (
        (
            "SIM-001", "Fazenda Horizonte Verde", "Santa Aurora", "GO",
            "Agroclor PX-17 (fictício)", "2021-2023",
            "Sinal hipotético detectado", "Alta", "PO-SIM-01", 18.0, 0.42, 0.10,
            "2026-08-12", "Poço isolado para avaliação",
            "Cenário didático: possível infiltração após chuvas intensas.",
        ),
        (
            "SIM-002", "Sítio Água Clara", "Vale das Nascentes", "MG",
            "Herbiol Z-4 (fictício)", "2020-2022",
            "Sinal hipotético detectado", "Média", "PO-SIM-02", 24.0, 0.18, 0.08,
            "2026-08-18", "Nova coleta programada",
            "Cenário didático: resultado requer repetição em laboratório.",
        ),
        (
            "SIM-003", "Estância Ipê Roxo", "Campo Sereno", "MS",
            "Inseticida Delta-Q (fictício)", "2019-2021",
            "Monitoramento preventivo", "Baixa", "PO-SIM-03", 31.0, 0.04, 0.10,
            "2026-08-21", "Monitoramento trimestral",
            "Cenário didático: amostra abaixo do parâmetro de referência fictício.",
        ),
        (
            "SIM-004", "Fazenda Três Riachos", "Santa Aurora", "GO",
            "Agroclor PX-17 (fictício)", "2022-2024",
            "Sinal hipotético detectado", "Alta", "PO-SIM-04", 16.0, 0.61, 0.10,
            "2026-09-02", "Investigação prioritária",
            "Cenário didático: poço próximo à área de aplicação simulada.",
        ),
        (
            "SIM-005", "Chácara Boa Esperança", "Rio das Pedras", "PR",
            "Herbiol Z-4 (fictício)", "2018-2020",
            "Sem sinal na última coleta", "Baixa", "PO-SIM-05", 28.0, 0.02, 0.08,
            "2026-09-05", "Acompanhamento de rotina",
            "Cenário didático: manter coleta sazonal para comparação.",
        ),
        (
            "SIM-006", "Sítio Pedra Branca", "Campo Sereno", "MS",
            "Fungicida N-Delta (fictício)", "2021-2022",
            "Sinal hipotético detectado", "Média", "PO-SIM-06", 22.0, 0.13, 0.09,
            "2026-09-11", "Plano de contenção em análise",
            "Cenário didático: investigar drenagem entre lavoura e captação.",
        ),
        (
            "SIM-007", "Fazenda Lagoa Serena", "Vale das Nascentes", "MG",
            "Inseticida Delta-Q (fictício)", "2017-2019",
            "Monitoramento preventivo", "Baixa", "PO-SIM-07", 35.0, 0.03, 0.10,
            "2026-09-16", "Monitoramento semestral",
            "Cenário didático: coleta sem indício acima da referência fictícia.",
        ),
        (
            "SIM-008", "Estância Campo Novo", "Rio das Pedras", "PR",
            "Fungicida N-Delta (fictício)", "2023-2025",
            "Sinal hipotético detectado", "Alta", "PO-SIM-08", 19.0, 0.37, 0.09,
            "2026-09-23", "Avaliação de fonte alternativa",
            "Cenário didático: avaliar captação alternativa durante investigação.",
        ),
    )
    conexao.executemany(
        """
        INSERT OR IGNORE INTO rural_properties (
            codigo, nome, municipio, estado, substancia, periodo_uso,
            situacao_monitoramento, prioridade, poco, profundidade_poco_m,
            concentracao_ug_l, referencia_ug_l, amostra_em,
            medida_resposta, nota_tecnica
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        propriedades,
    )


def resumo_propriedades():
    """Devolve apenas indicadores agregados para o painel público de nível 1."""
    conexao = conectar()
    try:
        linha = conexao.execute(
            """
            SELECT COUNT(*) AS total,
                   COUNT(DISTINCT municipio || ', ' || estado) AS municipios,
                   SUM(CASE
                       WHEN situacao_monitoramento = 'Sinal hipotético detectado'
                       THEN 1 ELSE 0
                   END) AS sinais_detectados
            FROM rural_properties
            """
        ).fetchone()
    finally:
        conexao.close()
    return dict(linha)


def listar_propriedades(nivel):
    """Lista apenas os campos autorizados para o nível solicitado (2 ou 3)."""
    if nivel == config.NIVEL_DIRETOR:
        colunas = (
            "codigo, nome, municipio, estado, substancia, periodo_uso, "
            "situacao_monitoramento, prioridade, amostra_em"
        )
    elif nivel == config.NIVEL_MINISTRO:
        colunas = (
            "codigo, nome, municipio, estado, substancia, periodo_uso, "
            "situacao_monitoramento, prioridade, poco, profundidade_poco_m, "
            "concentracao_ug_l, referencia_ug_l, amostra_em, medida_resposta, nota_tecnica"
        )
    else:
        raise ValueError("A listagem detalhada exige nível 2 ou 3.")

    conexao = conectar()
    try:
        linhas = conexao.execute(
            f"""
            SELECT {colunas}
            FROM rural_properties
            ORDER BY CASE prioridade
                WHEN 'Alta' THEN 1
                WHEN 'Média' THEN 2
                ELSE 3
            END, codigo
            """
        ).fetchall()
    finally:
        conexao.close()
    return [dict(linha) for linha in linhas]


def agora():
    """Data/hora atual em texto ISO, usada em todas as tabelas."""
    return datetime.datetime.now().isoformat(timespec="seconds")


# ------------------------------------------------------------------
# Usuarios
# ------------------------------------------------------------------

def normalizar_id(texto):
    """
    Normaliza o ID do usuario: minusculas, sem espacos e sem acentos
    comuns. Assim 'Ana Souza' e 'ana souza' viram o mesmo id 'ana'.
    """
    import unicodedata

    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.strip().lower()
    return texto.replace(" ", "_")


def cadastrar_usuario(id_usuario, nome, nivel):
    """
    Cria ou atualiza um usuario.
    Devolve (sucesso, mensagem).
    """
    id_usuario = normalizar_id(id_usuario)

    if nivel not in (config.NIVEL_TODOS, config.NIVEL_DIRETOR, config.NIVEL_MINISTRO):
        return False, f"Nivel invalido: {nivel}. Use 1, 2 ou 3."

    if not id_usuario:
        return False, "ID do usuario nao pode ser vazio."

    conexao = conectar()
    try:
        conexao.execute(
            """
            INSERT INTO users (id, nome, nivel, criado_em)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, nivel = excluded.nivel
            """,
            (id_usuario, nome, nivel, agora()),
        )
        conexao.commit()
    finally:
        conexao.close()

    return True, f"Usuario '{id_usuario}' salvo com nivel {nivel}."


def buscar_usuario(id_usuario):
    """
    Devolve os dados do usuario como dicionario, ou None se nao existir.
    """
    id_usuario = normalizar_id(id_usuario)

    conexao = conectar()
    try:
        linha = conexao.execute(
            "SELECT id, nome, nivel, criado_em FROM users WHERE id = ?",
            (id_usuario,),
        ).fetchone()
    finally:
        conexao.close()

    return dict(linha) if linha else None


def alterar_nivel_usuario(id_usuario, nivel):
    """Atualiza o nível de acesso de um usuário cadastrado."""
    id_usuario = normalizar_id(id_usuario)
    if nivel not in (config.NIVEL_TODOS, config.NIVEL_DIRETOR, config.NIVEL_MINISTRO):
        return False, f"Nivel invalido: {nivel}. Use 1, 2 ou 3."

    conexao = conectar()
    try:
        cursor = conexao.execute(
            "UPDATE users SET nivel = ? WHERE id = ?",
            (nivel, id_usuario),
        )
        if cursor.rowcount == 0:
            return False, f"Usuario '{id_usuario}' nao encontrado."
        conexao.commit()
    finally:
        conexao.close()

    return True, f"Nivel do usuario '{id_usuario}' atualizado para {nivel}."


def listar_usuarios():
    """
    Devolve a lista de usuarios, com a contagem de embeddings de cada um.
    """
    conexao = conectar()
    try:
        linhas = conexao.execute(
            """
            SELECT u.id, u.nome, u.nivel, u.criado_em,
                   COUNT(e.id) AS qtd_embeddings
            FROM users u
            LEFT JOIN embeddings e ON e.user_id = u.id
            GROUP BY u.id
            ORDER BY u.nivel DESC, u.id
            """
        ).fetchall()
    finally:
        conexao.close()

    return [dict(linha) for linha in linhas]


# ------------------------------------------------------------------
# Embeddings
# ------------------------------------------------------------------

def adicionar_embedding(id_usuario, embedding):
    """
    Grava UM embedding criptografado para o usuario.
    Devolve (sucesso, mensagem).
    """
    id_usuario = normalizar_id(id_usuario)

    if buscar_usuario(id_usuario) is None:
        return False, f"Usuario '{id_usuario}' nao esta cadastrado."

    try:
        bytes_cifrados = cifrar_embedding(embedding)
    except Exception as erro:  # noqa: BLE001
        return False, f"Falha ao cifrar o embedding: {erro}"

    conexao = conectar()
    try:
        conexao.execute(
            "INSERT INTO embeddings (user_id, embedding, criado_em) VALUES (?, ?, ?)",
            (id_usuario, bytes_cifrados, agora()),
        )
        conexao.commit()
    finally:
        conexao.close()

    return True, "Embedding gravado."


def embeddings_do_usuario(id_usuario):
    """
    Devolve todos os embeddings de um usuario, ja decifrados.
    A lista pode vir vazia se o cadastro foi feito sem nenhuma foto.
    """
    id_usuario = normalizar_id(id_usuario)

    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT embedding FROM embeddings WHERE user_id = ? ORDER BY id",
            (id_usuario,),
        ).fetchall()
    finally:
        conexao.close()

    embeddings = []
    for linha in linhas:
        try:
            embeddings.append(decifrar_embedding(linha["embedding"]))
        except ValueError as erro:
            # Um embedding corrompido nao impede o login pelo resto
            print(f"[AVISO] {id_usuario}: embedding ignorado ({erro})")
    return embeddings


def contar_embeddings(id_usuario):
    """Quantas amostras de rosto o usuario tem gravadas."""
    return len(embeddings_do_usuario(id_usuario))


def apagar_usuario(id_usuario):
    """
    Remove o usuario e todos os seus embeddings.
    O registro de auditoria NAO e apagado (rastro de seguranca).
    """
    id_usuario = normalizar_id(id_usuario)

    conexao = conectar()
    try:
        conexao.execute("DELETE FROM users WHERE id = ?", (id_usuario,))
        conexao.commit()
    finally:
        conexao.close()

    return True, f"Usuario '{id_usuario}' removido."


# ------------------------------------------------------------------
# Auditoria
# ------------------------------------------------------------------

def registrar_auditoria(user_id, recurso, nivel, distancia, limiar,
                        resultado, detalhe="", origem=""):
    """
    Grava um acesso na tabela audit_log.
    Chame SEMPRE, tanto para acesso liberado quanto negado.
    """
    conexao = conectar()
    try:
        conexao.execute(
            """
            INSERT INTO audit_log
                (data_hora, user_id, recurso, nivel, distancia, limiar, resultado, detalhe, origem)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (agora(), user_id, recurso, nivel, distancia, limiar, resultado, detalhe, origem),
        )
        conexao.commit()
    finally:
        conexao.close()


def listar_auditoria(limite=20):
    """
    Devolve os acessos mais recentes, do mais novo para o mais antigo.
    """
    conexao = conectar()
    try:
        linhas = conexao.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    finally:
        conexao.close()

    return [dict(linha) for linha in linhas]
