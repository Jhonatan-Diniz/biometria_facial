"""
Interface de linha de comando para cadastro e autenticacao.

Uso:
    python app/cli.py cadastrar --id ana --nome "Ana Souza" --nivel 1
    python app/cli.py cadastrar --id ana --fotos data/ana
    python app/cli.py listar
    python app/cli.py login --id ana --fonte data/ana/ana_1.jpg --nivel 3
    python app/cli.py login --id ana --fonte webcam --nivel 3
    python app/cli.py log
"""

import argparse
import os
import sys

# Permite rodar o arquivo direto (python app/cli.py)
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from app import access_control  # noqa: E402
from app import audit  # noqa: E402
from app import capture  # noqa: E402
from app import config  # noqa: E402
from app import database  # noqa: E402
from app import embedder  # noqa: E402

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ------------------------------------------------------------------
# Comandos
# ------------------------------------------------------------------

def comando_cadastrar(args):
    """
    Cadastra um usuario e gera os embeddings a partir de uma pasta de fotos.
    Faz as duas coisas juntas porque faz sentido no uso real: nao existe
    usuario uteis sem amostra de rosto.
    """
    id_usuario = database.normalizar_id(args.id)
    nome = args.nome if args.nome else args.id

    sucesso, mensagem = database.cadastrar_usuario(id_usuario, nome, args.nivel)
    if not sucesso:
        print(f"[ERRO] {mensagem}")
        return 1
    print(f"[OK] {mensagem}")

    if not args.fotos:
        print("[AVISO] Nenhuma pasta de fotos informada. "
              "O usuario foi criado sem amostras de rosto e nao podera usar os niveis 2 e 3.")
        return 0

    fotos = listar_imagens(args.fotos)
    if not fotos:
        print(f"[ERRO] Nenhuma imagem encontrada em: {args.fotos}")
        return 1

    if len(fotos) > config.MAX_IMAGENS_CADASTRO:
        fotos = fotos[: config.MAX_IMAGENS_CADASTRO]
        print(f"[AVISO] Usando apenas as {config.MAX_IMAGENS_CADASTRO} primeiras imagens.")

    if len(fotos) < config.MIN_IMAGENS_CADASTRO:
        print(f"[AVISO] Apenas {len(fotos)} imagem(ns). "
              f"O recomendado e {config.MIN_IMAGENS_CADASTRO} a {config.MAX_IMAGENS_CADASTRO}.")

    print(f"\nExtraindo embeddings de {len(fotos)} imagem(ns)...\n")

    gravados = 0
    falhas = []
    for caminho in fotos:
        nome_arquivo = os.path.basename(caminho)
        try:
            imagem = capture.carregar_imagem(caminho)
            embedding, detalhes = embedder.gerar_embedding_com_deteccao(
                imagem, exigir_qualidade=True
            )

            if embedding is None:
                falhas.append((nome_arquivo, detalhes["erro"]))
                print(f"  [X] {nome_arquivo}: {detalhes['erro']}")
                continue

            ok, msg = database.adicionar_embedding(id_usuario, embedding)
            if ok:
                gravados += 1
                print(f"  [OK] {nome_arquivo}  confianca={detalhes['score']:.2f}")
            else:
                falhas.append((nome_arquivo, msg))
                print(f"  [X] {nome_arquivo}: {msg}")
        except Exception as erro:  # noqa: BLE001
            falhas.append((nome_arquivo, str(erro)))
            print(f"  [X] {nome_arquivo}: {erro}")

    print(f"\nResumo: {gravados}/{len(fotos)} embedding(s) gravados para '{id_usuario}'.")

    if gravados == 0:
        print("[ERRO] Nenhuma foto serviu para cadastro. Veja o README: "
              "luz frontal, rosto de frente e fundo neutro fazem muita diferenca.")
        return 1

    if falhas:
        print("\nFotos descartadas:")
        for nome_arquivo, motivo in falhas:
            print(f"  - {nome_arquivo}: {motivo}")

    return 0


def comando_listar(args):
    """Mostra os usuarios cadastrados."""
    usuarios = database.listar_usuarios()

    if not usuarios:
        print("Nenhum usuario cadastrado.")
        print("Comece com:  python app/cli.py cadastrar --id ana --nivel 1 --fotos data/ana")
        return 0

    print(f"\n{'ID':<16}{'NOME':<24}{'NIVEL':<8}{'AMOSTRAS':<10}")
    print("-" * 58)
    for usuario in usuarios:
        print(
            f"{usuario['id']:<16}"
            f"{usuario['nome'][:23]:<24}"
            f"{usuario['nivel']:<8}"
            f"{usuario['qtd_embeddings']:<10}"
        )
    print()
    return 0


def comando_login(args):
    """
    Verificacao 1:1. O usuario informa o ID; o rosto apresentado e comparado
    APENAS com as amostras desse ID. Em seguida checa o nivel do recurso.
    """
    print(f"\nusuario: {args.id}")
    print(f"recurso: nivel {args.nivel} - {config.caminho_recurso_exemplo(args.nivel)}")
    print(f"origem:  {args.fonte}\n")

    # Pega o embedding do rosto apresentado
    embedding = None
    origem = "arquivo"

    if args.fonte:
        try:
            if str(args.fonte).lower() == "webcam":
                origem = "webcam"
                imagem = capture.capturar_por_fonte("webcam", indice_camera=args.indice_camera)
            else:
                origem = "video" if os.path.splitext(args.fonte)[1].lower() in capture.EXTENSOES_VIDEO else "arquivo"
                imagem = capture.capturar_por_fonte(args.fonte)

            if imagem is not None:
                embedding, detalhes = embedder.gerar_embedding_com_deteccao(
                    imagem, exigir_qualidade=True
                )
                if embedding is None:
                    print(f"[X] Nao foi possivel extrair o embedding: {detalhes['erro']}")
                    # Registra mesmo assim: tentativa falha tambem e auditoria
                    access_control.avaliar_acesso(
                        args.id, args.nivel, embedding_tentativa=None, origem=origem
                    )
                    return 1
                print(f"[OK] Rosto detectado (confianca {detalhes['score']:.2f}).\n")
        except ValueError as erro:
            print(f"[ERRO] {erro}")
            return 1

    resultado = access_control.avaliar_acesso(
        args.id, args.nivel, embedding_tentativa=embedding, origem=origem
    )

    # ---- Mostra o veredito ----
    print("=" * 62)
    if resultado["permitido"]:
        print(" ACESSO PERMITIDO")
    else:
        print(" ACESSO NEGADO")
    print("=" * 62)
    print(f" Recurso ....... {resultado['recurso']}")
    print(f" Nivel do recurso {resultado['nivel_recurso']} | nivel do usuario {resultado['nivel_usuario']}")

    if resultado["distancia"] is not None:
        print(
            f" Distancia ..... {resultado['distancia']:.4f} "
            f"(limiar {resultado['limiar']:.4f})"
        )
        print(
            f" Amostras ...... {resultado['amostras_com_match']} de "
            f"{resultado['amostras_avaliadas']} casaram"
        )

    print(f" Motivo ........ {resultado['motivo']}")
    print(f"\n (acesso registrado na auditoria: {resultado['resultado_registrado']})\n")

    return 0 if resultado["permitido"] else 1


def comando_log(args):
    """Mostra os acessos mais recentes."""
    audit.mostrar_ultimos(limite=args.limite)
    print(f"\n(log completo em {config.LOG_FILE})\n")
    return 0


# ------------------------------------------------------------------
# Auxiliares
# ------------------------------------------------------------------

def listar_imagens(pasta):
    """Lista os arquivos de imagem de uma pasta, em ordem alfabetica."""
    if os.path.isfile(pasta):
        return [pasta] if os.path.splitext(pasta)[1].lower() in EXTENSOES_IMAGEM else []

    if not os.path.isdir(pasta):
        return []

    arquivos = [
        os.path.join(pasta, nome)
        for nome in sorted(os.listdir(pasta))
        if os.path.splitext(nome)[1].lower() in EXTENSOES_IMAGEM
    ]
    return arquivos


def construir_parser():
    """Monta o parser de argumentos com os subcomandos."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="Biometria facial - controle de acesso por nivel.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    # cadastrar
    p_cad = sub.add_parser("cadastrar", help="Cadastra um usuario e gera seus embeddings.")
    p_cad.add_argument("--id", required=True, help="ID do usuario, ex: ana")
    p_cad.add_argument("--nome", help="Nome completo (padrao: o proprio ID)")
    p_cad.add_argument("--nivel", type=int, required=True, choices=[1, 2, 3],
                       help="Nivel de acesso do usuario")
    p_cad.add_argument("--fotos", help="Pasta (ou arquivo) com as fotos de cadastro")
    p_cad.set_defaults(funcao=comando_cadastrar)

    # listar
    p_list = sub.add_parser("listar", help="Lista os usuarios cadastrados.")
    p_list.set_defaults(funcao=comando_listar)

    # login
    p_login = sub.add_parser("login", help="Autentica um usuario em um recurso de nivel N.")
    p_login.add_argument("--id", required=True, help="ID informado no login (verificacao 1:1)")
    p_login.add_argument("--fonte", help="Foto, video, a palavra 'webcam', ou vazio para nivel 1")
    p_login.add_argument("--nivel", type=int, required=True, choices=[1, 2, 3],
                         help="Nivel do recurso protegido")
    p_login.add_argument("--indice-camera", type=int, default=0, help="Indice da webcam")
    p_login.set_defaults(funcao=comando_login)

    # log
    p_log = sub.add_parser("log", help="Mostra os acessos mais recentes.")
    p_log.add_argument("--limite", type=int, default=20, help="Quantidade de registros")
    p_log.set_defaults(funcao=comando_log)

    return parser


def main():
    parser = construir_parser()
    args = parser.parse_args()

    config.garantir_pastas()
    audit.configurar()

    try:
        return args.funcao(args)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuario.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
