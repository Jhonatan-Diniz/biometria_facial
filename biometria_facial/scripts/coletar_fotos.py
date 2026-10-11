"""
Captura de fotos de teste via webcam.

Cada pessoa do grupo entra como um usuario ficticio e grava de 3 a 5 fotos.
As fotos ficam salvas em data/<id_usuario>/ e nao entram no git.

Uso:
    python scripts/coletar_fotos.py ana
    python scripts/coletar_fotos.py ana --indice-camera 1

Instrucoes para uma boa foto (importante para o reconhecimento):
  - Luz frontal, sem sombra forte no rosto.
  - Fundo neutro (parede clara), sem pessoas atras.
  - Rosto de frente para a camera, ocupando boa parte da imagem.
  - Repita as fotos mudando um pouco: central, um pouco a esquerda,
    um pouco a direita, e um leve sorriso. Variacao ajuda o sistema.
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import capture, config  # noqa: E402

# Sugestoes de pose para guiar quem esta sendo fotografado
POSES = [
    "Olhe de frente para a camera, rosto neutro.",
    "Vire levemente para a esquerda (~15 graus).",
    "Vire levemente para a direita (~15 graus).",
    "Face um leve sorriso, ainda de frente.",
    "Incline a cabeca levemente para baixo ou acima.",
]


def coletar(id_usuario, indice_camera=0):
    """
    Guia o usuario a tirar varias fotos, uma por vez, ate ele cancelar
    ou bater a quantidade maxima. Salva em data/<id_usuario>/.
    """
    pasta = os.path.join(config.DATA_DIR, id_usuario)
    os.makedirs(pasta, exist_ok=True)

    print(f"\n============================================")
    print(f"  Coleta de fotos para: {id_usuario}")
    print(f"  Salvando em: {pasta}")
    print(f"============================================")

    num = 1
    while True:
        if num > config.MAX_IMAGENS_CADASTRO:
            print(f"\nLimite de {config.MAX_IMAGENS_CADASTRO} fotos atingido.")
            break

        pose = POSES[(num - 1) % len(POSES)]
        print(f"\n[Foto {num}/{config.MAX_IMAGENS_CADASTRO}] {pose}")
        print("Aperte ESPACO para capturar, ESC para encerrar.")

        try:
            imagem = capture.capturar_da_webcam(indice_camera=indice_camera)
        except ValueError as erro:
            print(f"[ERRO] {erro}")
            break

        caminho = os.path.join(pasta, f"{id_usuario}_{num}.jpg")
        capture.salvar_imagem(imagem, caminho)
        print(f"[OK] Foto salva em: {caminho}")
        num += 1

    total = num - 1
    print(f"\nFim da coleta. {total} foto(s) de '{id_usuario}' salvas.")
    if total < config.MIN_IMAGENS_CADASTRO:
        print(f"Atencao: o ideal e pelo menos {config.MIN_IMAGENS_CADASTRO} fotos por pessoa.")
    return total


def main():
    analise = argparse.ArgumentParser(description="Coleta fotos de teste via webcam.")
    analise.add_argument("id_usuario", help="ID do usuario ficticio, ex: ana")
    analise.add_argument(
        "--indice-camera", type=int, default=0,
        help="indice da webcam (0 = padrao)",
    )
    args = analise.parse_args()

    config.garantir_pastas()
    coletar(args.id_usuario, indice_camera=args.indice_camera)
    return 0


if __name__ == "__main__":
    sys.exit(main())
