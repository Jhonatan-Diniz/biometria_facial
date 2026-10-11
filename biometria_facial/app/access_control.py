"""
Regras de controle de acesso por nivel.

Regra unica do projeto:
    acesso liberado se  nivel_usuario >= nivel_recurso

Sobre isso, ha duas regras especificas:

- Nivel 1: NAO exige biometria. Qualquer um acessa. Mesmo assim o acesso
  e registrado na auditoria (a regra do trabalho e explicita nisso).

- Nivel 2 e 3: exigem biometria facial. Alem disso, no nivel 3 a tolerancia
  e menor (limiar mais rigido), porque um falso positivo ali expoe o dado
  mais sensivel.

Se o usuario nao tem nivel suficiente, o acesso e negado ANTES de gastar
tempo com biometria. Quem nao pode entrar na sala nao precisa que
o sistema reconheca o rosto dele.
"""

from app import audit
from app import config
from app import database
from app import matcher

PERMITIDO = "PERMITIDO"
NEGADO = "NEGADO"


def pode_acessar(nivel_usuario, nivel_recurso):
    """
    Regra pura de nivel, sem biometria.
    Devolve True/False.
    """
    return nivel_usuario >= nivel_recurso


def exige_biometria(nivel_recurso):
    """
    Nivel 1 e liberado a todos e nao exige reconhecimento facial.
    Os demais niveaux exigem biometria.
    """
    return nivel_recurso > config.NIVEL_TODOS


def avaliar_acesso(id_usuario, nivel_recurso, embedding_tentativa=None, origem=""):
    """
    Decide o acesso de UM usuario a UM recurso de UM nivel, e registra
    a auditoria em TODOS os casos (permitido ou negado).

    Parametros:
        id_usuario       -> id informado na tela de login (verificacao 1:1)
        nivel_recurso    -> nivel do recurso protegido (1, 2 ou 3)
        embedding_tentativa -> embedding do rosto apresentado (pode ser None
                               no nivel 1, que nao exige biometria)
        origem           -> "arquivo", "video", "webcam" ou None (login sem foto)

    Devolve um dicionario com o veredito e todos os detalhes, que a
    interface e a CLI usam para mostrar o resultado na tela.
    """
    recurso = config.caminho_recurso_exemplo(nivel_recurso)

    resultado = {
        "permitido": False,
        "motivo": "",
        "recurso": recurso,
        "nivel_recurso": nivel_recurso,
        "nivel_usuario": None,
        "distancia": None,
        "limiar": None,
        "amostras_avaliadas": 0,
        "amostras_com_match": 0,
        "resultado_registrado": NEGADO,
    }

    # ---- Procura o usuario ----
    usuario = database.buscar_usuario(id_usuario)
    if usuario is None:
        resultado["motivo"] = f"Usuario '{id_usuario}' nao cadastrado."
        audit.registrar(
            user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
            distancia=None, limiar=None, resultado=NEGADO,
            detalhe=resultado["motivo"], origem=origem,
        )
        return resultado

    nivel_usuario = usuario["nivel"]
    resultado["nivel_usuario"] = nivel_usuario

    # ---- Regra 1: nivel 1 nao exige biometria ----
    if not exige_biometria(nivel_recurso):
        resultado["permitido"] = True
        resultado["resultado_registrado"] = PERMITIDO
        resultado["motivo"] = "Recurso de nivel 1: acesso liberado sem autenticacao biometrica."
        audit.registrar(
            user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
            distancia=None, limiar=None, resultado=PERMITIDO,
            detalhe=resultado["motivo"], origem=origem,
        )
        return resultado

    # ---- Regra 2: nivel insuficiente? negar sem gastar biometria ----
    if not pode_acessar(nivel_usuario, nivel_recurso):
        resultado["motivo"] = (
            f"Nivel insuficiente: '{usuario['nome']}' e nivel {nivel_usuario} "
            f"e o recurso exige nivel {nivel_recurso}."
        )
        audit.registrar(
            user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
            distancia=None, limiar=matcher.limiar(nivel_recurso), resultado=NEGADO,
            detalhe=resultado["motivo"], origem=origem,
        )
        return resultado

    # ---- Regra 3: biometria ----
    if embedding_tentativa is None:
        resultado["motivo"] = "Recurso exige biometria, mas nenhuma imagem foi apresentada."
        audit.registrar(
            user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
            distancia=None, limiar=matcher.limiar(nivel_recurso), resultado=NEGADO,
            detalhe=resultado["motivo"], origem=origem,
        )
        return resultado

    amostras = database.embeddings_do_usuario(id_usuario)
    comparacao = matcher.comparar_com_amostras(
        embedding_tentativa, amostras, nivel_recurso
    )

    resultado["distancia"] = comparacao["distancia"]
    resultado["limiar"] = comparacao["limiar"]
    resultado["amostras_avaliadas"] = comparacao["amostras_avaliadas"]
    resultado["amostras_com_match"] = comparacao["amostras_com_match"]

    if comparacao["erro"]:
        resultado["motivo"] = comparacao["erro"]
        audit.registrar(
            user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
            distancia=None, limiar=comparacao["limiar"], resultado=NEGADO,
            detalhe=comparacao["erro"], origem=origem,
        )
        return resultado

    # ---- Veredito ----
    # Observacao sobre prova de vida (Fase 5): quando config.LIVENESS_ATIVO
    # for ligado, a verificacao de piscada entra AQUI, entre a comparacao
    # e o veredito. O gancho nao foi escrito agora de proposito: um liveness
    # que nega sem implementacao seria pior do que liveness ausente.
    resultado["permitido"] = bool(comparacao["match"])
    resultado["resultado_registrado"] = PERMITIDO if comparacao["match"] else NEGADO

    if comparacao["match"]:
        resultado["motivo"] = (
            f"Rosto reconhecido (distancia {comparacao['distancia']:.4f} "
            f"<= limiar {comparacao['limiar']:.4f})."
        )
    else:
        resultado["motivo"] = (
            f"Rosto NAO reconhecido (distancia {comparacao['distancia']:.4f} "
            f"> limiar {comparacao['limiar']:.4f})."
        )

    audit.registrar(
        user_id=id_usuario, recurso=recurso, nivel=nivel_recurso,
        distancia=comparacao["distancia"], limiar=comparacao["limiar"],
        resultado=resultado["resultado_registrado"],
        detalhe=resultado["motivo"], origem=origem,
    )

    return resultado
