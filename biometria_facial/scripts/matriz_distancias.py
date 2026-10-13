"""
Matriz de distancias entre as fotos de teste.

Responde a pergunta que importa: "o modelo consegue SEPARAR as pessoas?"
Nao adianta o login ter sido permitido se for porque o limiar esta frouxo.

Mostra tres coisas:
  1. Distancias ENTRE fotos da MESMA pessoa (genuinas) -> devem ser pequenas
  2. Distancias ENTRE fotos de pessoas DIFERENTES (impostoras) -> devem ser grandes
  3. Onde os limiares atuais caem em relacao a essa distribuicao

Se as duas distribuicoes se sobrepoem, o problema sao as fotos, nao o codigo.

Uso:
    python scripts/matriz_distancias.py
    python scripts/matriz_distancias.py --pessoas matheus yaskara
"""

import argparse
import itertools
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import capture, config, embedder, matcher  # noqa: E402

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def achar_pessoas(pasta_dados):
    """Devolve {id: [caminhos das imagens]}, uma pasta por pessoa."""
    pessoas = {}
    if not os.path.isdir(pasta_dados):
        return pessoas

    for entrada in sorted(os.listdir(pasta_dados)):
        subpasta = os.path.join(pasta_dados, entrada)
        if not os.path.isdir(subpasta):
            continue

        imagens = [
            os.path.join(subpasta, nome)
            for nome in sorted(os.listdir(subpasta))
            if os.path.splitext(nome)[1].lower() in EXTENSOES_IMAGEM
        ]
        if imagens:
            pessoas[entrada] = imagens

    return pessoas


def carregar_embeddings(pessoas):
    """
    Extrai (e opcionalmente reaproveita) os embeddings de cada foto.
    Devolve {pessoa: {caminho: embedding}} e um dicionario de problemas.
    """
    embeddings = {}
    problemas = {}

    for pessoa, caminhos in pessoas.items():
        embeddings[pessoa] = {}
        problemas[pessoa] = []
        print(f"\nProcessando {pessoa} ({len(caminhos)} fotos)...")
        for caminho in caminhos:
            nome = os.path.basename(caminho)
            try:
                imagem = capture.carregar_imagem(caminho)
                embedding, detalhes = embedder.gerar_embedding_com_deteccao(
                    imagem, exigir_qualidade=False
                )
            except Exception as erro:  # noqa: BLE001
                problemas[pessoa].append((nome, str(erro)))
                print(f"  [X] {nome}: {erro}")
                continue

            if embedding is None:
                problemas[pessoa].append((nome, detalhes["erro"]))
                print(f"  [X] {nome}: {detalhes['erro']}")
                continue

            embeddings[pessoa][nome] = embedding
            print(f"  [OK] {nome}  confianca={detalhes['score']:.2f}")

    return embeddings, problemas


def distancias_genuinas(embeddings):
    """Todas as distancias entre pares de fotos da MESMA pessoa."""
    resultados = []
    for pessoa, por_nome in embeddings.items():
        nomes = list(por_nome)
        for nome_a, nome_b in itertools.combinations(nomes, 2):
            distancia = matcher.distancia_cosseno(por_nome[nome_a], por_nome[nome_b])
            resultados.append((pessoa, nome_a, nome_b, distancia))
    return resultados


def distancias_impostoras(embeddings):
    """Todas as distancias entre pares de fotos de pessoas DIFERENTES."""
    resultados = []
    pessoas = list(embeddings)
    for pessoa_a, pessoa_b in itertools.combinations(pessoas, 2):
        for nome_a, emb_a in embeddings[pessoa_a].items():
            for nome_b, emb_b in embeddings[pessoa_b].items():
                distancia = matcher.distancia_cosseno(emb_a, emb_b)
                resultados.append((pessoa_a, nome_a, pessoa_b, nome_b, distancia))
    return resultados


def resumir(valores):
    """Minimo, maximo, media e mediana de uma lista de distancias."""
    if not valores:
        return None
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2 == 0:
        mediana = (ordenados[meio - 1] + ordenados[meio]) / 2
    else:
        mediana = ordenados[meio]
    return {
        "min": min(valores),
        "max": max(valores),
        "media": sum(valores) / len(valores),
        "mediana": mediana,
        "total": len(valores),
    }


def main():
    analise = argparse.ArgumentParser(description="Matriz de distancias entre fotos.")
    analise.add_argument("--pessoas", nargs="*", default=None,
                         help="IDs a considerar. Padrao: todas as pastas em data/.")
    analise.add_argument("--detalhe", action="store_true",
                         help="Lista todos os pares, nao so o resumo.")
    args = analise.parse_args()

    config.garantir_pastas()

    pessoas = achar_pessoas(config.DATA_DIR)
    if args.pessoas:
        pessoas = {p: c for p, c in pessoas.items() if p in args.pessoas}

    if not pessoas:
        print(f"Nenhuma pasta com imagens encontrada em {config.DATA_DIR}")
        print("Coloque as fotos em data/<usuario>/*.jpg e rode de novo.")
        return 1

    print(f"Pessoas encontradas: {', '.join(pessoas)}")
    embeddings, problemas = carregar_embeddings(pessoas)

    embeddings = {p: e for p, e in embeddings.items() if e}
    if not embeddings:
        print("\n[ERRO] Nenhum embedding foi extraido.")
        return 1

    genuinas = distancias_genuinas(embeddings)
    impostoras = distancias_impostoras(embeddings)

    # ---- Resumo ----
    print("\n" + "=" * 70)
    print("DISTANCIAS")
    print("=" * 70)

    res_gen = resumir([d for *_, d in genuinas])
    res_imp = resumir([d for *_, d in impostoras])

    if res_gen:
        print("\nGENUINAS (mesma pessoa) - devem ser PEQUENAS")
        print(f"  pares: {res_gen['total']}")
        print(f"  min {res_gen['min']:.4f} | mediana {res_gen['mediana']:.4f} | "
              f"media {res_gen['media']:.4f} | max {res_gen['max']:.4f}")
    else:
        print("\nGENUINAS: nenhuma (cada pessoa tem só 1 foto).")

    if res_imp:
        print("\nIMPOSTORAS (pessoas diferentes) - devem ser GRANDES")
        print(f"  pares: {res_imp['total']}")
        print(f"  min {res_imp['min']:.4f} | mediana {res_imp['mediana']:.4f} | "
              f"media {res_imp['media']:.4f} | max {res_imp['max']:.4f}")
    else:
        print("\nIMPOSTORAS: nenhuma (só há 1 pessoa).")

    # ---- Diagnostico ----
    print("\n" + "=" * 70)
    print("DIAGNOSTICO")
    print("=" * 70)

    if res_gen and res_imp:
        separacao = res_imp["min"] - res_gen["max"]
        print(f"  maior genuina ....... {res_gen['max']:.4f}")
        print(f"  menor impostora ..... {res_imp['min']:.4f}")
        print(f"  folga ............... {separacao:+.4f}")

        if separacao > 0:
            print("\n  [BOM] As distribuicoes NAO se sobrepoem.")
            print("  Existe um limiar que separa perfeitamente as pessoas.")
            meio = (res_gen["max"] + res_imp["min"]) / 2
            print(f"  Limiar sugerido (meio da folga): {meio:.4f}")
            print(f"  Valores atuais em config.py:")
            for nivel, valor in sorted(config.LIMIAR_DISTANCIA.items()):
                marca = "  <- acima do sugerido, MUITO permissivo" if valor > meio else ""
                print(f"    nivel {nivel}: {valor:.4f}{marca}")
        else:
            print("\n  [ATENCAO] As distribuicoes se SOBREPOEM.")
            print("  Nenhum limiar separa perfeitamente estas fotos. Isso significa")
            print("  que as fotos nao tem variacao suficiente entre as pessoas:")
            print("    - pouca luz -> rosto sem detalhe -> embedding instavel")
            print("    - fotos parecidas demais entre pessoas diferentes")
            print("  Nao e bug do codigo. Refaca as fotos com mais luz e variacao.")

        if res_gen["mediana"] > 0.4:
            print(f"\n  [ATENCAO] Distancia genuina mediana em {res_gen['mediana']:.4f}.")
            print("  Para a MESMA pessoa, o esperado e abaixo de 0.3. Acima disso as")
            print("  fotos provavelmente tem pouca luz ou muito movimento.")

    elif res_gen:
        print("\n  So ha uma pessoa. Cadastre pelo menos 2 para medir impostores.")

    # ---- Lista detalhada ----
    if args.detalhe:
        print("\n" + "=" * 70)
        print("DETALHE DAS DISTANCIAS")
        print("=" * 70)

        print("\nPares genuinos:")
        for pessoa, nome_a, nome_b, distancia in sorted(genuinas, key=lambda x: x[3]):
            print(f"  {distancia:.4f}  {pessoa}/{nome_a} vs {nome_b}")

        print("\nPares impostores:")
        for pa, na, pb, nb, distancia in sorted(impostoras, key=lambda x: x[4]):
            print(f"  {distancia:.4f}  {pa}/{na} vs {pb}/{nb}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
