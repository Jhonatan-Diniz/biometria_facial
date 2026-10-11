"""
Auditoria de acessos.

Cada tentativa de acesso, LIBERADA ou NEGADA, gera duas coisas:

1. Uma linha no arquivo logs/auditoria.log (via modulo logging).
   Serve para depurar problemas e ver a sequencia de eventos.

2. Uma linha na tabela audit_log do SQLite (via app.database).
   Serve para consulta: "quem tentou acessar o painel do Ministro
   nas ultimas 24 horas?".

O arquivo guarda o historico mesmo se o banco for apagado, e o banco
permite consultar sem abrir editor de texto. Por isso os dois.
"""

import logging
import os

from app import config
from app import database

_LOGGER = None


def configurar():
    """
    Prepara o logging em arquivo. Chame uma vez, no inicio do programa.
    Criar o arquivo de log duas vezes deixa handlers duplicados e
    cada linha aparece repetida, entao o handler existente e removido.
    """
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    config.garantir_pastas()

    _LOGGER = logging.getLogger("biometria")
    _LOGGER.setLevel(logging.INFO)

    # Evita duplicar linhas caso configurar() seja chamada duas vezes
    for handler in list(_LOGGER.handlers):
        _LOGGER.removeHandler(handler)

    handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    _LOGGER.addHandler(handler)
    _LOGGER.propagate = False  # nao escreve no console

    return _LOGGER


def registrar(user_id, recurso, nivel, distancia, limiar, resultado,
              detalhe="", origem=""):
    """
    Registra UMA tentativa de acesso nos dois destinos.

    resultado: "PERMITIDO" ou "NEGADO".
    distancia e limiar podem ser None quando a comparacao nao chegou
    a ser feita (por exemplo, acesso negado so por nivel insuficiente).
    """
    logger = configurar()

    # 1) Arquivo de texto
    logger.info(
        "user=%s | recurso=%s | nivel=%s | distancia=%s | limiar=%s | %s | detalhe=%s",
        user_id,
        recurso,
        nivel,
        f"{distancia:.4f}" if distancia is not None else "n/a",
        f"{limiar:.4f}" if limiar is not None else "n/a",
        resultado,
        detalhe,
    )

    # 2) Banco SQLite
    try:
        database.registrar_auditoria(
            user_id=user_id,
            recurso=recurso,
            nivel=nivel,
            distancia=distancia,
            limiar=limiar,
            resultado=resultado,
            detalhe=detalhe,
            origem=origem,
        )
    except Exception as erro:  # noqa: BLE001
        # A auditoria nunca pode derrubar o acesso em si.
        # Se o banco falhar, pelo menos o arquivo de log tem o registro.
        logger.error("FALHA ao gravar auditoria no banco: %s", erro)


def mostrar_ultimos(limite=20):
    """
    Mostra no console os acessos mais recentes, lidos do banco.
    """
    registros = database.listar_auditoria(limite=limite)

    if not registros:
        print("Nenhum acesso registrado ainda.")
        return

    cabecalho = f"{'DATA/HORA':<20}{'USUARIO':<14}{'RECURSO':<30}{'DIST':<8}{'RESULTADO'}"
    print(cabecalho)
    print("-" * len(cabecalho))

    for registro in registros:
        distancia = (
            f"{registro['distancia']:.4f}"
            if registro["distancia"] is not None
            else "-"
        )
        print(
            f"{registro['data_hora']:<20}"
            f"{(registro['user_id'] or '-'):<14}"
            f"{(registro['recurso'] or '-'):<30}"
            f"{distancia:<8}"
            f"{registro['resultado']}"
        )
