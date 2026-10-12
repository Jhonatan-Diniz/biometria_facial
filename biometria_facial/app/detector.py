"""
Deteccao e alinhamento de rostos com YuNet (cv2.FaceDetectorYN).

O YuNet devolve, alem da caixa do rosto, cinco pontos de referencia
(olhos, nariz, boca). Esses pontos sao usados para alinhar o rosto antes
de gerar o embedding, o que melhora muito a taxa de reconhecimento.
"""

import os

import cv2
import numpy as np

from app import config

# Cache do detector: criar o modelo e caro, entao guardamos em memoria
_DETECTOR = None


def _tem_yunet():
    """Confere se esta build do OpenCV tem o modulo YuNet."""
    return hasattr(cv2, "FaceDetectorYN")


def _tem_sface():
    """Confere se esta build do OpenCV tem o modulo SFace."""
    return hasattr(cv2, "FaceRecognizerSF")


def modelo_existe(caminho):
    """Verifica se o arquivo .onnx esta no disco."""
    return os.path.exists(caminho)


def _inicializar():
    """
    Cria (uma unica vez) o detector YuNet.
    Falha com mensagem clara se faltar o OpenCV contrib ou o modelo.
    """
    global _DETECTOR
    if _DETECTOR is not None:
        return _DETECTOR

    if not _tem_yunet():
        raise RuntimeError(
            "cv2.FaceDetectorYN nao existe nesta instalacao do OpenCV.\n"
            "Causa quase sempre: voce instalou 'opencv-python' em vez de "
            "'opencv-contrib-python'.\n"
            "Solucao:\n"
            "  pip uninstall -y opencv-python opencv-contrib-python\n"
            "  pip install opencv-contrib-python==4.10.0.84"
        )

    if not modelo_existe(config.YUNET_MODEL):
        raise RuntimeError(
            f"Modelo YuNet nao encontrado em: {config.YUNET_MODEL}\n"
            "Rode:  python scripts/download_models.py"
        )

    _DETECTOR = cv2.FaceDetectorYN.create(
        config.YUNET_MODEL,
        "",
        (320, 320),  # tamanho inicial; ajustamos a cada imagem em detectar()
        config.YUNET_SCORE_THRESHOLD,
        config.YUNET_NMS_THRESHOLD,
        config.YUNET_TOP_K,
    )
    return _DETECTOR


def _redimensionar_para_detector(imagem):
    """
    Reduz a imagem antes de detectar, e devolve o fator de reducao.

    YuNet foi treinado com entradas pequenas, entao imagem muito grande e
    reduzida para nao ficar lenta.

    IMPORTANTE: a escala devolvida e um fator de REDUCAO (menor que 1
    quando a imagem foi diminuida). Para levar uma coordenada medida na
    imagem reduzida de volta para a original, divide-se pela escala.
    Multiplicar encolheria as coordenadas e a caixa de rosto sairia no
    lugar errado da imagem.
    """
    altura, largura = imagem.shape[:2]
    maior = max(altura, largura)

    if maior <= config.DETECT_MAX_SIDE:
        return imagem, 1.0

    escala = config.DETECT_MAX_SIDE / maior
    novo = (int(largura * escala), int(altura * escala))
    imagem_red = cv2.resize(imagem, novo, interpolation=cv2.INTER_AREA)
    return imagem_red, escala


def avaliar_qualidade(imagem, rosto, nitidez_minima=None):
    """
    Avalia se um rosto detectado serve para biometria.

    rosto: dicionario com 'bbox' (x, y, w, h) e 'score'.

    nitidez_minima: sobrepõe config.MIN_SHARPNESS quando informado. O
    cadastro usa um valor mais brando (ver config.MIN_SHARPNESS_CADASTRO).

    Devolve (ok, motivo). 'motivo' explica a recusa, util para o usuario.
    """
    if nitidez_minima is None:
        nitidez_minima = config.MIN_SHARPNESS

    # O tamanho do rosto e medido no ESPACO EM QUE O YuNet OPERA, que e a
    # imagem ja reduzida. Isso torna o criterio independente da resolucao:
    # numa foto de 4000px o mesmo rosto mede 800px; numa de 900px, 180px.
    # Medir na imagem original reprovaria selfies em camera boa e aceitaria
    # as mesmas fotos se o usuario reduzisse a resolucao.
    escala = rosto.get("escala", 1.0)

    _, _, largura_rosto, altura_rosto = rosto["bbox"]
    largura_det = largura_rosto * escala
    altura_det = altura_rosto * escala
    lado_menor = min(largura_det, altura_det)
    lado_maior = max(largura_det, altura_det)

    if lado_menor < config.MIN_FACE_SIZE:
        return False, (
            f"rosto pequeno demais ({int(lado_menor)}px na imagem de deteccao, "
            f"min {config.MIN_FACE_SIZE}px): aproxime-se"
        )

    if lado_maior > config.MAX_FACE_SIZE:
        return False, (
            f"rosto grande demais ({int(lado_maior)}px na imagem de deteccao, "
            f"max {config.MAX_FACE_SIZE}px): afaste-se"
        )

    if rosto["score"] < config.YUNET_SCORE_THRESHOLD:
        return False, f"deteccao fraca (confianca {rosto['score']:.2f})"

    # Mede desfoque na regiao do rosto
    x, y, w, h = [int(v) for v in rosto["bbox"]]
    recorte = imagem[max(0, y):y + h, max(0, x):x + w]
    if recorte.size == 0:
        return False, "nao consegui recortar a regiao do rosto"

    cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
    nitidez = cv2.Laplacian(cinza, cv2.CV_64F).var()

    if nitidez < nitidez_minima:
        # Diagnostico: nitidez quase zero E contraste baixo significa que o
        # recorte caiu em area lisa (parede, fundo), e nao no rosto.
        contraste = float(cinza.std())
        if nitidez < 5 and contraste < 15:
            return False, (
                f"recorte sem detalhe (nitidez {nitidez:.0f}, contraste {contraste:.0f}): "
                "o detector marcou uma regiao lisa. Rode scripts/diagnostico.py"
            )
        return False, f"foto borrada (nitidez {nitidez:.0f}, min {nitidez_minima:.0f})"

    return True, "ok"


def detectar_rostos(imagem, aplicar_filtro_qualidade=True, nitidez_minima=None):
    """
    Detecta rostos em uma imagem BGR.

    Devolve uma lista de dicionarios, cada um com:
      bbox      -> (x, y, w, h) no tamanho da imagem original
      score     -> confianca (0 a 1)
      landmarks -> 5 pontos (olho esq, olho dir, nariz, boca esq, boca dir)
      qualidade -> (ok, motivo)

    A lista vem ordenada do rosto mais confiante para o menos.

    nitidez_minima: repassa o limiar para avaliar_qualidade(). O cadastro
    usa um valor mais brando que o da autenticacao.
    """
    if imagem is None:
        return []

    detector = _inicializar()
    imagem_red, escala = _redimensionar_para_detector(imagem)
    altura_red, largura_red = imagem_red.shape[:2]

    # O detector precisa saber o tamanho exato da entrada
    detector.setInputSize((largura_red, altura_red))
    _, rostos = detector.detect(imagem_red)

    if rostos is None or len(rostos) == 0:
        return []

    resultado = []
    for rosto in rostos:
        # Cada linha do YuNet tem 15 colunas, nesta ordem:
        #   [0:4]   bbox -> x, y, largura, altura
        #   [4:14]  5 landmarks -> olho esq, olho dir, nariz, boca esq, boca dir
        #   [14]    confianca (a ULTIMA coluna, nao a quinta)
        # Ordem conferida no demo oficial do opencv_zoo.
        bbox = tuple(float(v) for v in rosto[0:4])
        pontos = rosto[4:14]
        score = float(rosto[-1])

        # Desfaz o redimensionamento para voltar ao tamanho original.
        #
        # ATENCAO: aqui se DIVIDE pela escala, e nao multiplica.
        # A escala e o fator de REDUCAO: se a imagem de 1600px foi reduzida
        # para 640px, escala = 0.4. Uma coordenada medida na imagem reduzida
        # (ex: 82px) corresponde a 82 / 0.4 = 205px na original.
        # Multiplicar por 0.4 daria 33px, e a caixa cairia no canto errado
        # da imagem -- foi exatamente esse o bug que rechazava todas as fotos.
        bbox_original = tuple(v / escala for v in bbox)
        pontos_originais = [
            float(pontos[i] / escala) for i in range(len(pontos))
        ]

        dicionario = {
            "bbox": bbox_original,
            "score": score,
            "landmarks": pontos_originais,
            "imagem_red": imagem_red,
            "escala": escala,
        }

        if aplicar_filtro_qualidade:
            # Filtra sempre na imagem original (nitidez e medida em px reais),
            # mas repassa a escala para o tamanho do rosto ser medido no
            # espaço de deteccao, e nao no da imagem original.
            dicionario["qualidade"] = avaliar_qualidade(
                imagem,
                {"bbox": bbox_original, "score": score, "escala": escala},
                nitidez_minima=nitidez_minima,
            )
        else:
            dicionario["qualidade"] = (True, "ok")

        resultado.append(dicionario)

    resultado.sort(key=lambda d: d["score"], reverse=True)
    return resultado


def melhor_rosto(imagem, exigir_qualidade=True):
    """
    Devolve o melhor rosto da imagem ou None se nao houver rosto aceitavel.
    E o atalho usado pela maioria do sistema (um rosto por foto).
    """
    rostos = detectar_rostos(imagem, aplicar_filtro_qualidade=True)

    for rosto in rostos:
        if exigir_qualidade and not rosto["qualidade"][0]:
            continue
        return rosto

    return None


def alinhar_rosto(imagem, rosto):
    """
    Recorta e alinha o rosto usando os 5 pontos de referencia do YuNet.
    O resultado e uma imagem quadrada (112x112) com o rosto 'chapado',
    pronta para o SFace gerar o embedding.

    Sem os landmarks fazemos um recorte simples com margem (fallback).
    """
    landmarks = rosto.get("landmarks")
    bbox = rosto["bbox"]

    if not landmarks or len(landmarks) < 10:
        return _recorte_simples(imagem, bbox)

    try:
        # face_aligned tem os 5 pontos: olhos, nariz, cantos da boca
        pontos = np.array(
            [
                [landmarks[0], landmarks[1]],   # olho esquerdo
                [landmarks[2], landmarks[3]],   # olho direito
                [landmarks[4], landmarks[5]],   # nariz
                [landmarks[6], landmarks[7]],   # boca esquerda
                [landmarks[8], landmarks[9]],   # boca direita
            ],
            dtype=np.float32,
        )

        tamanho = (112, 112)
        alinhado = cv2.faceAlignCrop(
            imagem,
            pontos,
            tamanho[0],  # largura
            tamanho[1],  # altura
            1.0,          # escala
            0.0,          # rotacao
        )
        if alinhado is not None and alinhado.size > 0:
            return alinhado
    except Exception:  # noqa: BLE001
        pass  # cai no recorte simples se o alinhamento falhar

    return _recorte_simples(imagem, bbox)


def _recorte_simples(imagem, bbox):
    """
    Recorte com margem quando nao temos landmarks.
    Sem margem lateral para nao pegar fundo, apenas cima (testa) e baixo (queixo).
    """
    x, y, w, h = [int(v) for v in bbox]
    margem_top = int(h * 0.20)
    margem_bottom = int(h * 0.10)

    y1 = max(0, y - margem_top)
    y2 = min(imagem.shape[0], y + h + margem_bottom)
    x1 = max(0, x)
    x2 = min(imagem.shape[1], x + w)

    recorte = imagem[y1:y2, x1:x2]
    if recorte.size == 0:
        return recorte

    # Deforma para um quadrado, como o SFace espera
    altura, largura = recorte.shape[:2]
    lado = max(altura, largura)
    quadrado = cv2.copyMakeBorder(
        recorte,
        0, lado - altura,
        0, lado - largura,
        cv2.BORDER_CONSTANT,
        value=(0, 0, 0),
    )
    return cv2.resize(quadrado, (112, 112))
