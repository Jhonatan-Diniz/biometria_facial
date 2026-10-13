"""
Diagnostico da webcam.

Testa os indices de camera um a um e relata o que aconteceu, em vez de
so dizer "nao foi possivel abrir a webcam".

Uso:
    python scripts/diagnostico_webcam.py
    python scripts/diagnostico_webcam.py --maximo 5
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

import cv2  # noqa: E402


def testar_indice(indice):
    """
    Tenta abrir um indice de camera e devolve um dicionario com o
    resultado: abriu, quantos frames, resolucao e se a imagem tem conteudo.
    """
    resultado = {
        "indice": indice,
        "abriu": False,
        "erro": None,
        "frames": 0,
        "largura": 0,
        "altura": 0,
        "brilho": None,
        "conteudo": False,
    }

    camera = cv2.VideoCapture(indice)

    if not camera.isOpened():
        resultado["erro"] = "VideoCapture nao abriu o indice"
        camera.release()
        return resultado

    resultado["abriu"] = True

    # Le alguns frames para confirmar que o stream entrega imagem de verdade.
    # Em Cameras claimed por outro app, isOpened() retorna True mas read() falha.
    for _ in range(10):
        ok, frame = camera.read()
        if not ok or frame is None:
            break
        resultado["frames"] += 1

    if resultado["frames"] > 0:
        resultado["altura"], resultado["largura"] = frame.shape[:2]
        cinza = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        resultado["brilho"] = float(cinza.mean())
        desvio = float(cinza.std())

        # Se a imagem e preta (brilho ~0 e desvio ~0), a camera abriu mas
        # nao esta entregando quadro valido. Costuma ser driver ou permissao.
        resultado["conteudo"] = resultado["brilho"] > 5 and desvio > 5
        resultado["contraste"] = desvio

    camera.release()
    return resultado


def main():
    analise = argparse.ArgumentParser(description="Testa os indices de camera.")
    analise.add_argument("--maximo", type=int, default=4,
                         help="Quantos indices testar (padrao 4)")
    args = analise.parse_args()

    print("=" * 70)
    print("DIAGNOSTICO DA WEBCAM")
    print("=" * 70)
    print(f"OpenCV: {cv2.__version__}")
    print(f"Plataforma: {sys.platform}")
    print()

    alguma_funciona = False

    for indice in range(args.maximo):
        print(f"--- indice {indice} ---")
        r = testar_indice(indice)

        if not r["abriu"]:
            print("  NAO ABRIU")
            print()
            continue

        print(f"  abriu .............. sim")
        print(f"  frames lidos ...... {r['frames']}")

        if r["frames"] == 0:
            print("  PROBLEMA: abriu mas nao entregou nenhum frame.")
            print("  A camera esta sendo usada por outro programa (Zoom, Teams,")
            print("  navegador com camera aberta)? Feche e tente de novo.")
            print()
            continue

        print(f"  resolucao ......... {r['largura']}x{r['altura']}")
        print(f"  brilho medio ...... {r['brilho']:.1f}")
        print(f"  contraste ......... {r.get('contraste', 0):.1f}")

        if not r["conteudo"]:
            print("  PROBLEMA: a imagem chega quase preta. Driver ou permissao.")
        else:
            print("  STATUS ............ FUNCIONA")

        alguma_funciona = alguma_funciona or r["conteudo"]
        print()

    print("=" * 70)

    if alguma_funciona:
        print("Ha pelo menos uma camera funcionando.")
        print("Use no login:  python app/cli.py login --id matheus "
              "--fonte webcam --indice-camera <N>")
    else:
        print("Nenhuma camera entregou imagem valida.")
        print()
        print("Causas mais comuns, da mais provavel para a menos:")
        print()
        print("  1. ESTA MAQUINA ESTA RODANDO WSL")
        print("     O WSL2 nao enxerga dispositivos USB sem o usbipd-win.")
        print("     No PowerShell (admin) do Windows:")
        print("       winget install dorssel.usbipd-win")
        print("       usbipd list")
        print("       # localize a camera no resultado e anote o ID")
        print("       usbipd bind --busid <ID>")
        print("       usbipd attach --wsl --busid <ID> --auto-attach")
        print("     Sem isso, nenhuma webcam funciona no WSL.")
        print()
        print("  2. A CAMERA ESTA OCUPADA")
        print("     Feche Zoom, Teams, Meet, navegador com camera ligada.")
        print("     No Windows, o botao de camera do teclado desliga a camera.")
        print()
        print("  3. PERMISSAO DO WINDOWS")
        print("     Configuracoes > Privacidade > Camera: ative o acesso.")
        print()
        print("  4. TESTE DIRETO NO WINDOWS PRIMEIRO")
        print("     Se a camera nao funciona no Windows, nao vai funcionar aqui.")
        print()
        print("  ALTERNATIVA que sempre funciona: use o arquivo de video.")
        print("  Grave um video no celular ou no app de camera do Windows e use:")
        print("    python app/cli.py login --id matheus --fonte meu_video.mp4 --nivel 2")

    print("=" * 70)
    return 0 if alguma_funciona else 1


if __name__ == "__main__":
    sys.exit(main())
