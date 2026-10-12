"""
Comparacao de embeddings: distancia cosseno e aplicacao de limiares.

A distancia cosseno entre dois embeddings normalizados e:
    distancia = 1 - (A . B) / (|A| * |B|)

Com embeddings normalizados (norma 1), isso equivale a 1 - produto escalar.
Interpretacao pratica:
    distancia pequena  ->  rostos parecidos (mesma pessoa)
    distancia grande   ->  rostos diferentes

Como verificar (1:1) exige menos comparacoes, usamos apenas o limiar.
"""

import numpy as np

from app import config


def normalizar(embedding):
    """
    Normaliza o embedding para norma 1.
    Se o vetor for nulo (impossivel na pratica), devolve o proprio vetor.
    """
    # reshape(-1) garante vetor 1D mesmo que venha no shape (1, 128),
    # que e como o SFace devolve. Sem isso o np.dot falha com
    # "shapes not aligned".
    embedding = np.asarray(embedding, dtype=np.float64).reshape(-1)
    norma = np.linalg.norm(embedding)
    if norma == 0:
        return embedding
    return embedding / norma


def distancia_cosseno(embedding_a, embedding_b):
    """
    Devolve a distancia cosseno entre dois embeddings.
    Resultado entre 0 (identicos) e 2 (opostos). Na pratica, rostos ficam
    entre 0.1 (mesma pessoa) e 0.9 (pessoas diferentes).
    """
    a = normalizar(embedding_a)
    b = normalizar(embedding_b)

    # Sanidade: se os dois vetores nao tiverem a mesma dimensao,
    # ha bug em quem gerou o embedding. Falhar aqui e melhor do que
    # propagar um erro de shape la no np.dot.
    if a.shape != b.shape:
        raise ValueError(
            f"Embeddings com dimensao diferente: {a.shape} vs {b.shape}. "
            "Isso indica bug na geração dos embeddings, não nas fotos."
        )

    produto = float(np.dot(a, b))
    # Evita erro de ponto flutuante: produto pode ser 1.0000000001
    produto = max(-1.0, min(1.0, produto))
    return 1.0 - produto


def limiar(nivel_recurso):
    """
    Devolve o limiar de distancia para um nivel de recurso.
    Nivel menor (mais baixo o risco) tolera maior distancia;
    nivel maior (mais alto o risco, mais rigido) tolera menos.
    """
    return config.LIMIAR_DISTANCIA.get(nivel_recurso, config.LIMIAR_DISTANCIA[config.NIVEL_MINISTRO])


def comparar(embedding_a, embedding_b, nivel_recurso):
    """
    Verificacao 1:1 simples. O usuario informa o ID; comparamos o rosto
    APENAS com o embedding dele.

    Devolve um dicionario com o veredito e a distancia, para ir para o log.
    """
    distancia = distancia_cosseno(embedding_a, embedding_b)
    limite = limiar(nivel_recurso)
    return {
        "distancia": distancia,
        "limiar": limite,
        "match": distancia <= limite,
    }


def comparar_com_amostras(embedding_tentativa, amostras, nivel_recurso):
    """
    Verificacao 1:1 com usuario que tem VARIAS fotos de cadastro.

    Cada foto de cadastro vira um embedding. O rosto informado e comparado
    com todos eles e vence o MENOR distancia. Esse e o padrao em biometria
    multi-template: uma pose desfavoravel na hora da captura nao reprova
    o acesso sozinha, porque outra das fotos do mesmo rosto vai estar perto.

    Devolve um dicionario com a melhor distancia, o limite, o veredito e
    uma contagem de quantas amostras casaram (util para o relatorio da APS).
    """
    if not amostras:
        return {
            "distancia": None,
            "limiar": limiar(nivel_recurso),
            "match": False,
            "amostras_avaliadas": 0,
            "amostras_com_match": 0,
            "erro": "usuario nao possui nenhuma amostra de rosto cadastrada",
        }

    limite = limiar(nivel_recurso)
    distancias = [distancia_cosseno(embedding_tentativa, amostra) for amostra in amostras]
    melhor = min(distancias)
    casaram = sum(1 for distancia in distancias if distancia <= limite)

    return {
        "distancia": melhor,
        "limiar": limite,
        "match": melhor <= limite,
        "amostras_avaliadas": len(distancias),
        "amostras_com_match": casaram,
        "erro": None,
    }
