"""
Captura de imagens de rosto a partir de três fontes:
  - arquivo de imagem (jpg, png, bmp...)
  - arquivo de video (mp4, avi...)
  - webcam

Todas as funções devolvem uma imagem no formato do OpenCV (numpy array BGR),
para que o detector.py sempre receba o mesmo tipo de dado.
"""

import os

import cv2

from app import config

# Extensoes de video reconhecidas pelo OpenCV
EXTENSOES_VIDEO = {
    ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".m4v", ".webm",
}

# Quantos frames o capturar_de_video examina antes de desistir
MAX_FRAMES_VIDEO = 30


def carregar_imagem(caminho):
    """
    Le uma imagem do disco e devolve o array BGR.
    Lanca ValueError se o arquivo nao existir ou nao for uma imagem valida.
    """
    if not os.path.exists(caminho):
        raise ValueError(f"Arquivo nao encontrado: {caminho}")

    imagem = cv2.imread(caminho)
    if imagem is None:
        raise ValueError(f"Nao foi possivel ler a imagem: {caminho}")

    return imagem


def capturar_da_webcam(indice_camera=0, tempo_maximo_s=10):
    """
    Abre a webcam e espera o usuario apertar ESPACO para capturar.
    Aperta ESC ou espere tempo_maximo_s para desistir.

    Devolve a imagem capturada (BGR).
    Leva ValueError se nao houver frames (sem camera, por exemplo).
    """
    camera = cv2.VideoCapture(indice_camera)
    if not camera.isOpened():
        camera.release()
        raise ValueError(
            f"Nao foi possivel abrir a webcam no indice {indice_camera}.\n"
            "Diagnostique antes de tentar de novo:\n"
            "  python scripts/diagnostico_webcam.py\n"
            "\n"
            "Causas comuns:\n"
            "  - Se voce esta no WSL: o WSL2 nao ve webcam sem o usbipd-win.\n"
            "    O script de diagnostico explica o passo a passo.\n"
            "  - A camera esta ocupada por outro programa (Zoom, Meet, navegador).\n"
            "  - A camera esta desligada pelo botao do teclado.\n"
            "  - A imagem abre mas fica preta: driver ou permissao do Windows.\n"
            "\n"
            "Alternativa que funciona sempre: use um arquivo de video."
        )

    print("\n=== WEBCAM ===")
    print("Posicione o rosto no centro e olhe para a camera.")
    print("ESPACO = capturar foto | ESC = sair sem capturar")
    print()

    imagem = None
    inicio = cv2.getTickCount()

    frames_sem_ler = 0

    while True:
        ok, frame = camera.read()

        if not ok or frame is None:
            # Algumas cameras "abrem" mas nunca entregam quadro. Contamos
            # para dar uma mensagem util em vez de encerrar em silencio.
            frames_sem_ler += 1
            if frames_sem_ler > 30:
                print("\n[A webcam abriu mas nao entregou nenhum frame em 30 tentativas.]")
                print("Causa provavel: a camera esta ocupada por outro programa,")
                print("ou o driver nao funciona no WSL. Diagnostique com:")
                print("  python scripts/diagnostico_webcam.py")
                break
            continue

        frames_sem_ler = 0

        # Espelha para ficar com cara de espelho (mais natural para o usuario)
        frame_mirror = cv2.flip(frame, 1)

        cv2.putText(
            frame_mirror,
            "ESPACO: capturar  |  ESC: sair",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            (0, 255, 0),
            2,
        )
        cv2.imshow("Captura facial", frame_mirror)

        tecla = cv2.waitKey(1) & 0xFF
        if tecla == 32:  # ESPACO
            imagem = frame_mirror.copy()
            break
        if tecla == 27:  # ESC
            break

        # Tempo esgotado
        decorrido_s = (cv2.getTickCount() - inicio) / cv2.getTickFrequency()
        if decorrido_s > tempo_maximo_s:
            print("Tempo esgotado sem captura.")
            break

    camera.release()
    cv2.destroyAllWindows()

    if imagem is None:
        raise ValueError(
            "Nenhuma foto foi capturada. Se a janela chegou a abrir e voce "
            "apertou ESPACO, o problema e outro: confira se o rosto estava "
            "visivel e dentro do quadro."
        )

    return imagem


def capturar_de_video(caminho_video, frame_desejado=0):
    """
    Le um frame de um arquivo de video.
    Por padrao pega o primeiro frame com rosto (ate o limite definido em
    MAX_FRAMES_VIDEO), o que evitaideos que comecam com quadro preto.

    Devolve a imagem (BGR).
    """
    if not os.path.exists(caminho_video):
        raise ValueError(f"Video nao encontrado: {caminho_video}")

    video = cv2.VideoCapture(caminho_video)
    if not video.isOpened():
        raise ValueError(f"Nao foi possivel abrir o video: {caminho_video}")

    frame = None
    for indice in range(MAX_FRAMES_VIDEO):
        ok, frame_atual = video.read()
        if not ok:
            break

        # Pula frames muito escuros (transicoes de cena)
        if cv2.mean(frame_atual)[0] > 30:
            frame = frame_atual
            if indice >= frame_desejado:
                break

    video.release()

    if frame is None:
        raise ValueError("Nenhum frame utilizavel foi encontrado no video.")

    return frame


def capturar_por_fonte(fonte, indice_camera=0):
    """
    Funcao unica de entrada para a interface e para a CLI.

    fonte pode ser:
      - caminho de imagem  -> "minha_foto.jpg"
      - caminho de video   -> "meu_video.mp4"
      - "webcam"           -> abre a camera

    Devolve a imagem (BGR) ou None se o usuario cancelar.
    """
    if fonte is None:
        return None

    if str(fonte).lower() == "webcam":
        return capturar_da_webcam(indice_camera=indice_camera)

    if not os.path.exists(fonte):
        raise ValueError(f"Arquivo nao encontrado: {fonte}")

    extensao = os.path.splitext(fonte)[1].lower()
    if extensao in EXTENSOES_VIDEO:
        return capturar_de_video(fonte)
    return carregar_imagem(fonte)


def salvar_imagem(imagem, caminho):
    """Salva uma imagem em disco, criando a pasta se necessario."""
    pasta = os.path.dirname(caminho)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    cv2.imwrite(caminho, imagem)
    return caminho


def padronizar_tamanho(imagem, lado_maior=config.DETECT_MAX_SIDE):
    """
    Reduz imagens muito grandes para o detector nao ficar lento.
    Mantem a proporcao. Imagens menores que o limite ficam como estao.
    """
    altura, largura = imagem.shape[:2]
    maior = max(altura, largura)

    if maior <= lado_maior:
        return imagem

    escala = lado_maior / maior
    novo = (int(largura * escala), int(altura * escala))
    return cv2.resize(imagem, novo, interpolation=cv2.INTER_AREA)
