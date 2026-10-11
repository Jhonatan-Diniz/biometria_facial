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

        CREATE INDEX IF NOT EXISTS idx_embeddings_user ON embeddings(user_id);
        CREATE INDEX IF NOT EXISTS idx_audit_data ON audit_log(data_hora);
        """
    )
    conexao.commit()


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
