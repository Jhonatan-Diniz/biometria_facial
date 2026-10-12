"""
Diagnostico de fotos de rosto.

Mostra por que cada imagem foi aceita ou recusada pelo filtro de qualidade,
com numeros concretos. Serve para descobrir se o problema e a foto ou o
criterio do filtro.

Uso:
    python scripts/diagnostico.py data/matheus
    python scripts/diagnostico.py data/matheus/matheus1.jpeg
    python scripts/diagnostico.py data/ --gravar   # salva imagens anotadas
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app import capture, config, detector  # noqa: E402

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def nitidez(cinza):
    """
    Mede a nitidez pela variancia do Laplaciano.

    O Laplaciano realca mudancas bruscas de brilho. Em uma foto nitida
    existem muitas (olhos, sobrancelha, borda do rosto), logo a varianca
    e alta. Em uma foto borrada quase nao existe nenhuma, e a varianca
    cai para perto de zero.

    Referencia empirica para rostos em fotos de webcam 720p:
        acima de 100  = nitida
        30 a 100      = aceitavel
        abaixo de 30  = provavelmente borrada
    """
    return float(cv2.Laplacian(cinza, cv2.CV_64F).var())


def analisar(caminho, gravar=False):
    """Analisa uma imagem e imprime o relatorio."""
    imagem = capture.carregar_imagem(caminho)
    altura, largura = imagem.shape[:2]
    cinza_inteira = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)

    print("=" * 70)
    print(os.path.basename(caminho))
    print("=" * 70)
    print(f"  dimensoes ........ {largura}x{altura}")

    maior = max(altura, largura)
    if maior > config.DETECT_MAX_SIDE:
        escala = config.DETECT_MAX_SIDE / maior
        print(f"  redimensionada ... sim, fator {escala:.3f} "
              f"(-> {int(largura*escala)}x{int(altura*escala)} para detectar)")
    else:
        escala = 1.0
        print(f"  redimensionada ... nao (ja cabe em {config.DETECT_MAX_SIDE}px)")

    print(f"  nitidez da foto .. {nitidez(cinza_inteira):.0f} (referencia da imagem toda)")

    # Detecta sem aplicar filtro, para ver TUDO que foi encontrado
    rostos = detector.detectar_rostos(imagem, aplicar_filtro_qualidade=False)

    if not rostos:
        print("\n  [ERRO] Nenhum rosto detectado.")
        print("         A imagem pode estar virada, muito escura, ou o rosto")
        print("         pode ser pequeno demais para o YuNet (min ~10px).")
        return

    # Chamamos com aplicar_filtro_qualidade=True para que 'veredito filtro'
    # mostre o resultado REAL. Com False, o campo vem preenchido como "ok"
    # sem passar pelo filtro, e o diagnostico mente sobre o veredito.
    rostos = detector.detectar_rostos(imagem, aplicar_filtro_qualidade=True)

    print(f"  rostos detectados  {len(rostos)}")
    print()

    for indice, rosto in enumerate(rostos):
        x, y, w, h = [int(v) for v in rosto["bbox"]]
        lado_menor = min(w, h)
        lado_maior = max(w, h)

        # Tamanho no espaco de deteccao, que e onde os limites valem
        escala = rosto.get("escala", 1.0)
        lado_det = max(w, h) * escala

        print(f"  --- rosto {indice} (confianca {rosto['score']:.3f}) ---")
        print(f"      posicao ......... x={x} y={y} w={w} h={h}")
        print(f"      lado menor/maior  {lado_menor} / {lado_maior} px (original)")
        print(f"      lado na deteccao  {int(lado_det)} px "
              f"(limites: min {config.MIN_FACE_SIZE} / max {config.MAX_FACE_SIZE})")
        print(f"      limite confianca  {config.YUNET_SCORE_THRESHOLD}")
        print(f"      confianca ....... {rosto['score']:.3f}  "
              f"{'OK' if rosto['score'] >= config.YUNET_SCORE_THRESHOLD else 'ABAIXO'}")

        # Recorta exatamente a regiao que o filtro usa
        recorte = imagem[max(0, y):y + h, max(0, x):x + w]
        if recorte.size == 0:
            print("      recorte ......... VAZIO (coordenadas fora da imagem!)")
            print()
            continue

        valor = nitidez(cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY))
        print(f"      nitidez do rosto  {valor:.0f}  "
              f"{'OK' if valor >= config.MIN_SHARPNESS else 'ABAIXO do min ' + str(config.MIN_SHARPNESS)}")
        print(f"                      (cadastro exige {config.MIN_SHARPNESS_CADASTRO})")

        # Quanto do recorte e realmente "informacao" e quanto e cor chapado?
        cinza = cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY)
        print(f"      brilho medio ..... {cinza.mean():.0f} (0=preto, 255=branco)")
        print(f"      contraste ........ {cinza.std():.1f}")

        # Diagnostico: uma regiao quase sem contraste E nitidez zero
        # significa que o recorte caiu em area lisa (fundo/parede).
        if valor < config.MIN_SHARPNESS and cinza.std() < 15:
            print("      >> ALERTA: regiao sem contraste e sem nitidez.")
            print("         Um rosto detectado com confianca alta NUNCA cai numa")
            print("         regao lisa. Quase sempre isso significa que as")
            print("         coordenadas do rosto estao erradas -- confira se a")
            print("         conversao de escala em detector.py esta dividindo")
            print("         pela escala em vez de multiplicar.")

        print(f"      veredito filtro . {rosto['qualidade'][1]}")
        print()

    if gravar:
        pasta = config.RESULTS_DIR
        os.makedirs(pasta, exist_ok=True)
        anotada = imagem.copy()
        for rosto in rostos:
            x, y, w, h = [int(v) for v in rosto["bbox"]]
            cv2.rectangle(anotada, (x, y), (x + w, y + h), (0, 255, 0), 2)
            for i in range(0, 10, 2):
                cv2.circle(anotada, (int(rosto["landmarks"][i]),
                                     int(rosto["landmarks"][i + 1])), 3, (0, 0, 255), -1)
        destino = os.path.join(pasta, f"debug_{os.path.basename(caminho)}")
        cv2.imwrite(destino, anotada)
        print(f"  imagem anotada salva em: {destino}")


def listar_imagens(caminho):
    """Aceita um arquivo ou uma pasta e devolve a lista de imagens."""
    if os.path.isfile(caminho):
        return [caminho]

    if not os.path.isdir(caminho):
        print(f"[ERRO] Nao encontrado: {caminho}")
        return []

    encontradas = []
    for raiz, _pastas, arquivos in os.walk(caminho):
        for nome in sorted(arquivos):
            if os.path.splitext(nome)[1].lower() in EXTENSOES_IMAGEM:
                encontradas.append(os.path.join(raiz, nome))
    return encontradas


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    gravar = "--gravar" in sys.argv
    alvos = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not alvos:
        print(__doc__)
        return 1

    total = 0
    for alvo in alvos:
        caminhos = listar_imagens(alvo)
        if not caminhos:
            continue
        print(f"\n### {len(caminhos)} imagem(ns) em '{alvo}'\n")
        for caminho in caminhos:
            analisar(caminho, gravar=gravar)
            total += 1

    print(f"\n{'=' * 70}")
    print(f"Analisadas {total} imagem(ns).")
    print(f"Limiar atual de nitidez: {config.MIN_SHARPNESS}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
