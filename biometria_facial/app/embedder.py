"""
Geracao de embeddings (assinaturas biometricas) com SFace
(cv2.FaceRecognizerSF).

Um embedding e um vetor de 128 numeros floats que resume o rosto.
Duas fotos da MESMA pessoa tem embeddings muito proximos.
Duas pessoas diferentes tem embeddings distantes.

Importante: o embedding e a "identidade numerica" da pessoa. No sistema
ele e gravado criptografado e NUNCA as fotos sao armazenadas.
"""

import os

import cv2
import numpy as np

from app import config
from app import detector

# Cache do reconhecedor
_RECONHECEDOR = None


def _inicializar():
    """
    Cria (uma unica vez) o reconhecedor SFace.
    Falha com mensagem clara se faltar o OpenCV contrib ou o modelo.
    """
    global _RECONHECEDOR
    if _RECONHECEDOR is not None:
        return _RECONHECEDOR

    if not detector._tem_sface():
        raise RuntimeError(
            "cv2.FaceRecognizerSF nao existe nesta instalacao do OpenCV.\n"
            "Causa quase sempre: voce instalou 'opencv-python' em vez de "
            "'opencv-contrib-python'.\n"
            "Solucao:\n"
            "  pip uninstall -y opencv-python opencv-contrib-python\n"
            "  pip install opencv-contrib-python==4.10.0.84"
        )

    if not os.path.exists(config.SFACE_MODEL):
        raise RuntimeError(
            f"Modelo SFace nao encontrado em: {config.SFACE_MODEL}\n"
            "Rode:  python scripts/download_models.py"
        )

    _RECONHECEDOR = cv2.FaceRecognizerSF.create(config.SFACE_MODEL, "")
    return _RECONHECEDOR


def gerar_embedding_da_imagem(imagem):
    """
    Recebe uma imagem BGR (com um rosto) e devolve o embedding.

    IMPORTANTE: o SFace devolve o vetor no shape (1, 128), ou seja, uma
    linha dentro de uma matriz. A gente achata para (128,), porque o
    np.dot() usado na distancia cosseno exige vetores 1D. Sem isso,
    a comparacao quebra com "shapes not aligned".

    Devolve None se nao for possivel extrair o embedding.
    """
    if imagem is None:
        return None

    reconhecedor = _inicializar()

    # Gera o embedding do rosto alinhado
    try:
        embedding = reconhecedor.feature(imagem)
    except Exception as erro:  # noqa: BLE001
        print(f"[embedder] erro ao extrair embedding: {erro}")
        return None

    # Achata (1, 128) -> (128,)
    embedding = np.asarray(embedding).reshape(-1)

    if embedding.size != config.EMBEDDING_SIZE:
        print(
            f"[embedder] embedding com tamanho inesperado: "
            f"{embedding.size} (esperado {config.EMBEDDING_SIZE})"
        )
        return None

    return embedding


def gerar_embedding_com_deteccao(imagem, exigir_qualidade=True, nitidez_minima=None):
    """
    Pipeline completo: detecta o melhor rosto, alinha e gera o embedding.

    Devolve sempre a tupla (embedding, detalhes).
    'embedding' e None quando nao deu para extrair;
    'detalhes["erro"]' traz a explicacao pronta para mostrar ao usuario.

    exigir_qualidade: se False, aceita o rosto mesmo reprovado no filtro,
    desde que o YuNet tenha detectado algum.

    nitidez_minima: repassa o limiar de nitidez para o filtro. O cadastro
    usa config.MIN_SHARPNESS_CADASTRO, mais brando que a autenticacao.
    """
    detalhes = {
        "embedding": None,
        "bbox": None,
        "score": None,
        "erro": None,
        "aviso": None,
    }

    rostos = detector.detectar_rostos(
        imagem,
        aplicar_filtro_qualidade=True,
        nitidez_minima=nitidez_minima,
    )
    if not rostos:
        detalhes["erro"] = "Nenhum rosto foi detectado na imagem."
        return None, detalhes

    # Se houver varios rostos e estamos exigindo qualidade, escolhe o primeiro ok
    escolhido = None
    for rosto in rostos:
        if exigir_qualidade and not rosto["qualidade"][0]:
            continue
        escolhido = rosto
        break

    if escolhido is None:
        motivos = ", ".join(r["qualidade"][1] for r in rostos[:3])
        detalhes["erro"] = f"Os rostos detectados nao servem para biometria: {motivos}"
        return None, detalhes

    # Guardamos o motivo da reprovacao como aviso. O rosto ainda pode ser
    # usado se exigir_qualidade for False: e melhor cadastrar uma foto
    # mediana com aviso do que impedir a pessoa de se cadastrar.
    if not escolhido["qualidade"][0]:
        detalhes["aviso"] = escolhido["qualidade"][1]

    alinhado = detector.alinhar_rosto(imagem, escolhido)
    if alinhado is None or alinhado.size == 0:
        detalhes["erro"] = "Falha ao recortar o rosto da imagem."
        return None, detalhes

    embedding = gerar_embedding_da_imagem(alinhado)
    if embedding is None:
        detalhes["erro"] = "Falha ao gerar o embedding do rosto."
        return None, detalhes

    detalhes["embedding"] = embedding
    detalhes["bbox"] = escolhido["bbox"]
    detalhes["score"] = escolhido["score"]
    return embedding, detalhes
