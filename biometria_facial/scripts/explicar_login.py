"""
Por que uma foto especifica nao e reconhecida no login?

Responde comparando a foto de teste contra CADA amostra do cadastro do
usuario, e mostra tambem a distancia contra as outras pessoas. Sem isso
nao da para saber se o problema e o limiar, a foto, ou o cadastro.

Uso:
    python scripts/explicar_login.py matheus data/matheus/matheus6.jpeg
    python scripts/explicar_login.py matheus data/matheus/matheus6.jpeg --nivel 3

Le a galeria do BANCO (nao da pasta), porque e com a galeria que o login
compara. Se a foto nova foi placed na pasta mas o cadastro nao foi
refeito, ela nao esta no banco e o login nao tem como usa-la.
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import capture, config, database, embedder, matcher  # noqa: E402


def embedding_de(caminho):
    """Extrai o embedding de uma foto, mostrando o motivo se falhar."""
    try:
        imagem = capture.carregar_imagem(caminho)
    except ValueError as erro:
        return None, str(erro)

    embedding, detalhes = embedder.gerar_embedding_com_deteccao(
        imagem, exigir_qualidade=False
    )
    if embedding is None:
        return None, detalhes["erro"]

    return embedding, f"confianca {detalhes['score']:.2f}"


def main():
    analise = argparse.ArgumentParser(description="Explica um login que falhou.")
    analise.add_argument("usuario", help="ID do usuario, ex: matheus")
    analise.add_argument("foto", help="Caminho da foto apresentada no login")
    analise.add_argument("--nivel", type=int, default=None, choices=[1, 2, 3],
                         help="Nivel do recurso (padrao: o nivel do usuario)")
    args = analise.parse_args()

    config.garantir_pastas()

    # ---- A foto apresentada ----
    if not os.path.exists(args.foto):
        print(f"[ERRO] Foto nao encontrada: {args.foto}")
        return 1

    print("=" * 70)
    print(f"FOTO APRESENTADA: {args.foto}")
    print("=" * 70)

    probe, info = embedding_de(args.foto)
    if probe is None:
        print(f"  [ERRO] Nao extrai embedding: {info}")
        return 1
    print(f"  {info}")

    # ---- O usuario existe? ----
    usuario = database.buscar_usuario(args.usuario)
    if usuario is None:
        print(f"\n[ERRO] Usuario '{args.usuario}' nao esta cadastrado.")
        return 1

    nivel = args.nivel if args.nivel else usuario["nivel"]
    limiar = matcher.limiar(nivel)

    print(f"\n  usuario: {usuario['id']} ({usuario['nome']}), nivel {usuario['nivel']}")
    print(f" recurso de nivel {nivel}, limiar {limiar:.4f}")

    # ---- A galeria do BANCO ----
    amostras = database.embeddings_do_usuario(args.usuario)
    print(f"  amostras no BANCO: {len(amostras)}")

    if not amostras:
        print(f"\n  [ERRO] O usuario nao tem nenhuma amostra no banco.")
        print(f"  Rode o cadastro:")
        print(f"    python app/cli.py cadastrar --id {args.usuario} "
              f"--nivel {usuario['nivel']} --fotos data/{args.usuario}")
        return 1

    # ---- Comparacao contra a propria galeria ----
    print(f"\n{'=' * 70}")
    print("CONTRA A PROPRIA GALERIA (o login vence a menor)")
    print("=" * 70)

    distancias = []
    for indice, amostra in enumerate(amostras, start=1):
        d = matcher.distancia_cosseno(probe, amostra)
        distancias.append(d)
        marca = "CASA" if d <= limiar else "nao casa"
        print(f"  amostra {indice}: {d:.4f}  {marca}")

    melhor = min(distancias)
    veredito = "PERMITIDO" if melhor <= limiar else "NEGADO"
    print(f"\n  melhor distancia: {melhor:.4f}  vs limiar {limiar:.4f}")
    print(f"  VEREDITO: {veredito}")

    if melhor > limiar:
        print(f"\n  Faltaram {melhor - limiar:.4f} para passar.")

    # ---- Contra as outras pessoas ----
    print(f"\n{'=' * 70}")
    print("CONTRA AS OUTRAS PESSOAS (impostoras)")
    print("=" * 70)

    outros = database.listar_usuarios()
    piores = []
    for outro in outros:
        if outro["id"] == args.usuario:
            continue
        amos = database.embeddings_do_usuario(outro["id"])
        if not amos:
            continue
        menor = min(matcher.distancia_cosseno(probe, a) for a in amos)
        piores.append((menor, outro["id"]))

    for menor, outro_id in sorted(piores):
        print(f"  {outro_id:<16} menor impostora: {menor:.4f}"
              f"  {'ENTRARIA' if menor <= limiar else 'barrada'}")

    # ---- Diagnostico ----
    if piores:
        melhor_impostora = min(p for p, _ in piores)
        print(f"\n  melhor genuina ....... {melhor:.4f}")
        print(f"  melhor impostora ..... {melhor_impostora:.4f}")
        print(f"  intervalo seguro ...... "
              f"({melhor:.4f}, {melhor_impostora:.4f})")

        if melhor_impostora > limiar:
            print(f"\n  O limiar {limiar:.4f} JA esta dentro do intervalo seguro.")
            print("  Nao afrouxe o limiar: isso abriria porta para impostora.")
            print(f"\n  Se a foto nova e da mesma pessoa, o caminho e:")
            print(f"    1. Rodar o diagnostico de nitidez nela:")
            print(f"         python scripts/diagnostico.py {args.foto}")
            print(f"    2. Se estiver escura ou borrada, refazer a foto.")
            print(f"    3. Se estiver boa, refazer o cadastro incluindo ela:")
            print(f"         python app/cli.py cadastrar --id {args.usuario} "
                  f"--nivel {usuario['nivel']} --fotos data/{args.usuario}")
            print(f"    (o cadastro precisa ser refeito: colocar a foto na pasta")
            print(f"     nao a coloca no banco)")
        else:
            print(f"\n  [ATENCAO] O limiar {limiar:.4f} esta FRouxO: uma impostora")
            print("  entraria. Baixe o limiar antes de continuar.")

    return 0 if melhor <= limiar else 1


if __name__ == "__main__":
    sys.exit(main())
