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
            "  pip install opencv-contrib-python==4.12.0.88"
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
    Recebe uma imagem BGR (com um rosto) e devolve o embedding (numpy array).
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

    return embedding


def gerar_embedding_com_deteccao(imagem, exigir_qualidade=True):
    """
    Pipeline completo: detecta o melhor rosto, alinha e gera o embedding.

    Devolve sempre a tupla (embedding, detalhes).
    'embedding' e None quando nao deu para extrair;
    'detalhes["erro"]' traz a explicacao pronta para mostrar ao usuario.
    """
    detalhes = {
        "embedding": None,
        "bbox": None,
        "score": None,
        "erro": None,
    }

    rostos = detector.detectar_rostos(imagem, aplicar_filtro_qualidade=True)
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
