"""
Baixa os modelos .onnx do repositório opencv_zoo para a pasta models/.

Uso:
    python scripts/download_models.py

Se a máquina estiver sem internet, baixe manualmente e coloque na pasta models/:
    https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
    https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
"""

import os
import sys
import urllib.request

# Sobe duas níveis para chegar na raiz do projeto
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import config  # noqa: E402

# URLs dos modelos dentro do opencv_zoo
MODELOS = [
    (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    ),
    (
        "face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    ),
]

# Espelho alternativo (caso o GitHub esteja bloqueado na sua rede)
ESPELHO = [
    (
        "face_detection_yunet_2023mar.onnx",
        "https://huggingface.co/opencv/face_detection_yunet/resolve/main/face_detection_yunet_2023mar.onnx",
    ),
    (
        "face_recognition_sface_2021dec.onnx",
        "https://huggingface.co/opencv/face_recognition_sface/resolve/main/face_recognition_sface_2021dec.onnx",
    ),
]


def baixar(url, destino):
    """Baixa um arquivo exibindo progresso simples. Devolve True em caso de sucesso."""
    try:
        print(f"    baixando de {url}")
        urllib.request.urlretrieve(url, destino)
        return True
    except Exception as erro:  # noqa: BLE001
        print(f"    falhou: {erro}")
        if os.path.exists(destino):
            os.remove(destino)  # não deixa arquivo pela metade
        return False


def garantir_modelo(nome, destino):
    """Baixa um modelo se ele ainda não estiver na pasta models/."""
    if os.path.exists(destino):
        tamanho = os.path.getsize(destino)
        print(f"[OK] {nome} ja existe ({tamanho/1024:.0f} KB)")
        return True

    print(f"[..] baixando {nome}...")
    for url, _ in MODELOS + ESPELHO:
        if os.path.basename(url) != nome:
            continue
        if baixar(url, destino):
            tamanho = os.path.getsize(destino)
            print(f"[OK] {nome} salvo ({tamanho/1024:.0f} KB)")
            return True

    print(f"[ERRO] nao foi possivel baixar {nome}")
    return False


def main():
    config.garantir_pastas()
    print(f"Pasta de modelos: {config.MODELS_DIR}\n")

    tudo_ok = True
    for nome, url in MODELOS:
        destino = os.path.join(config.MODELS_DIR, nome)
        if not garantir_modelo(nome, destino):
            tudo_ok = False

    print()
    if tudo_ok:
        print("Todos os modelos estao prontos.")
        return 0

    print("Faltaram modelos. Baixe manualmente para:", config.MODELS_DIR)
    print("  https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet")
    print("  https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface")
    return 1


if __name__ == "__main__":
    sys.exit(main())
