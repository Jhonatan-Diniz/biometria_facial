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


def melhor_limiar(embeddings):
    """
    Calcula o intervalo de limiares em que o sistema nao erra, usando o
    criterio que importa para o login real.

    No login, uma foto e apresentada e comparada contra a galeria de N
    amostras, vencendo a MENOR distancia. O par relevante por usuario e,
    portanto, a melhor genuina. O pior caso contra impostoras e a menor
    distancia entre qualquer amostra do usuario e qualquer foto alheia.

    O sistema acerta em todos os casos enquanto:
        max_dos_usuarios( melhor_genuina ) < limiar < min_dos_usuarios( pior_impostora )

    Se esse intervalo for vazio, nao existe limiar perfeito.
    """
    pessoas = sorted(embeddings)

    melhores_genuinas = []
    piores_impostoras = []

    for pessoa in pessoas:
        amos = list(embeddings[pessoa].values())

        if len(amos) > 1:
            melhores_genuinas.append(min(
                matcher.distancia_cosseno(a, b)
                for i, a in enumerate(amos)
                for b in amos[i + 1:]
            ))

        pior = None
        for outra in pessoas:
            if outra == pessoa:
                continue
            for emb_a in embeddings[pessoa].values():
                for emb_b in embeddings[outra].values():
                    d = matcher.distancia_cosseno(emb_a, emb_b)
                    if pior is None or d < pior:
                        pior = d
        if pior is not None:
            piores_impostoras.append(pior)

    if not melhores_genuinas or not piores_impostoras:
        return None

    return {
        "pior_genuina": max(melhores_genuinas),
        "melhor_impostora": min(piores_impostoras),
    }


def analise_multi_template(embeddings, gen_limiar):
    """
    Simula o que o login realmente faz.

    O login nao compara a foto com UM embedding: compara com os N do
    usuario e vence a MENOR distancia. Isso muda tudo na pratica. Uma
    impostora cuja distancia media e alta ainda pode "casar" se UMA das
    amostras do usuario for parecida com ela.

    Devolve, por pessoa, a pior distancia impostora possivel (a minima
    entre as amostras) e a melhor distancia genuina. É o numero que decide
    se o limiar e seguro.
    """
    pessoas = sorted(embeddings)
    print("\n" + "=" * 70)
    print(f"COMO O LOGIN REALMENTE DECIDE (multi-template, limiar {gen_limiar:.2f})")
    print("=" * 70)
    print(f"  {'usuario':<16}{'genuina':<22}{'pior impostora':<22}{'risco'}")
    print(f"  {'-' * 76}")

    for pessoa in pessoas:
        amos = list(embeddings[pessoa].values())

        # Melhor distancia entre fotos da propria pessoa (o login deve liberar)
        melhor_genuina = min(
            matcher.distancia_cosseno(a, b)
            for i, a in enumerate(amos)
            for b in amos[i + 1:]
        ) if len(amos) > 1 else None

        # Pior caso contra impostores: a MENOR distancia entre as amostras
        # desta pessoa e qualquer foto de outra pessoa
        pior_impostora = None
        origem = None
        for outra in pessoas:
            if outra == pessoa:
                continue
            for nome_b, emb_b in embeddings[outra].items():
                for nome_a, emb_a in embeddings[pessoa].items():
                    d = matcher.distancia_cosseno(emb_a, emb_b)
                    if pior_impostora is None or d < pior_impostora:
                        pior_impostora = d
                        origem = f"{nome_a} x {outra}/{nome_b}"

        if melhor_genuina is None or pior_impostora is None:
            continue

        # O acesso e liberado se a minima <= limiar
        gen_ok = melhor_genuina <= gen_limiar
        imp_passa = pior_impostora <= gen_limiar

        if imp_passa:
            risco = "IMPOSTOR ENTRA"
        elif not gen_ok:
            risco = "reconhece mal"
        else:
            risco = "ok"

        marca_gen = "libera" if gen_ok else "NEGA!"
        marca_imp = "ENTRA!" if imp_passa else "ok"

        print(f"  {pessoa:<12}"
              f"{melhor_genuina:>8.4f} {marca_gen:<9}"
              f"{pior_impostora:>8.4f} {marca_imp:<8}"
              f"{risco}")

    # ---- Julgamento deste limiar ----
    # Conta quantos usuarios reconhecem e quantas impostoras sao barradas.
    reconhecidos = 0
    avaliados = 0
    impostoras_barradas = 0
    impostoras_total = 0

    for pessoa in pessoas:
        amos = list(embeddings[pessoa].values())
        if len(amos) > 1:
            avaliados += 1
            melhor = min(
                matcher.distancia_cosseno(a, b)
                for i, a in enumerate(amos)
                for b in amos[i + 1:]
            )
            if melhor <= gen_limiar:
                reconhecidos += 1

        for outra in pessoas:
            if outra == pessoa:
                continue
            for emb_a in embeddings[pessoa].values():
                for emb_b in embeddings[outra].values():
                    impostoras_total += 1
                    if matcher.distancia_cosseno(emb_a, emb_b) > gen_limiar:
                        impostoras_barradas += 1

    taxa_rec = 100.0 * reconhecidos / avaliados if avaliados else 0
    taxa_bloq = 100.0 * impostoras_barradas / impostoras_total if impostoras_total else 0

    print(f"\n  no limiar {gen_limiar:.2f}:")
    print(f"    usuarios reconhecidos  {reconhecidos}/{avaliados}  ({taxa_rec:.0f}%)")
    print(f"    impostoras barradas     {impostoras_barradas}/{impostoras_total}  ({taxa_bloq:.0f}%)")

    if taxa_rec == 100 and taxa_bloq == 100:
        print("    -> PERFEITO: nenhuma confusao neste limiar.")
    elif taxa_rec == 100:
        print(f"    -> {100 - taxa_bloq:.0f}% de impostoras entram. Limiar frouxo.")
    elif taxa_bloq == 100:
        print(f"    -> {100 - taxa_rec:.0f}% dos usuarios legimos sao negados. Limiar apertado.")
    else:
        print("    -> Mistura de erros. Refaca as fotos para dar margem.")


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


def tabela_por_conjunto(pares, titulo):
    """
    Agrupa os pares por pessoa (genuinas) ou par de pessoas (impostoras) e
    mostra o pior caso de cada grupo.

    Serve para localizar QUAL pessoa ou QUAL dupla esta causando a
    sobreposicao. A media geral esconde isso: uma unica foto ruim entre
    varias boas desaparece no agregado.
    """
    grupos = {}
    for item in pares:
        chave = item[0] if titulo == "genuinas" else (item[0], item[2])
        grupos.setdefault(chave, []).append(item[-1])

    if not grupos:
        return

    print(f"\n  por {titulo[:-1] if titulo.endswith('as') else titulo}:")
    print(f"    {'grupo':<22}{'pares':<8}{'min':<10}{'mediana':<10}{'max'}")
    print(f"    {'-' * 58}")

    ordenados = sorted(
        grupos.items(),
        key=lambda kv: resumir(kv[1])["max"],
        reverse=True,
    )

    for chave, valores in ordenados:
        r = resumir(valores)
        nome = chave if isinstance(chave, str) else f"{chave[0]} x {chave[1]}"
        print(f"    {nome:<22}{r['total']:<8}{r['min']:<10.4f}"
              f"{r['mediana']:<10.4f}{r['max']:.4f}")


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
        tabela_por_conjunto(genuinas, "genuinas")
    else:
        print("\nGENUINAS: nenhuma (cada pessoa tem só 1 foto).")

    if res_imp:
        print("\nIMPOSTORAS (pessoas diferentes) - devem ser GRANDES")
        print(f"  pares: {res_imp['total']}")
        print(f"  min {res_imp['min']:.4f} | mediana {res_imp['mediana']:.4f} | "
              f"media {res_imp['media']:.4f} | max {res_imp['max']:.4f}")
        tabela_por_conjunto(impostoras, "impostoras")
    else:
        print("\nIMPOSTORAS: nenhuma (só há 1 pessoa).")

    # ---- Diagnostico ----
    print("\n" + "=" * 70)
    print("DIAGNOSTICO")
    print("=" * 70)

    if res_gen and res_imp:
        print(f"  maior genuina ....... {res_gen['max']:.4f}")
        print(f"  menor impostora ..... {res_imp['min']:.4f}")

        # O criterio correto NAO e comparar o maior genuino com a menor
        # impostora. No login so uma foto e apresentada por vez; a galeria
        # do cadastro e usada para escolher a melhor comparacao. O par que
        # decide e a melhor genuina de cada usuario contra a pior impostora
        # de cada usuario.
        faixa = melhor_limiar(embeddings)
        separacao = faixa["melhor_impostora"] - faixa["pior_genuina"]

        print(f"\n  Criterio do login real (multi-template):")
        print(f"  pior genuina ......... {faixa['pior_genuina']:.4f}")
        print(f"  melhor impostora ..... {faixa['melhor_impostora']:.4f}")
        print(f"  intervalo util ....... "
              f"({faixa['pior_genuina']:.4f}, {faixa['melhor_impostora']:.4f})")

        if separacao > 0:
            print("\n  [BOM] Existe um intervalo de limiar em que o sistema nao erra.")
            meio = (faixa["pior_genuina"] + faixa["melhor_impostora"]) / 2
            print(f"  Limiar sugerido (meio da folga): {meio:.4f}")
            print("  Pode usar qualquer valor dentro do intervalo acima.")
            print(f"\n  Valores atuais em config.py:")
            for nivel, valor in sorted(config.LIMIAR_DISTANCIA.items()):
                if faixa["pior_genuina"] < valor < faixa["melhor_impostora"]:
                    marca = "  ok"
                elif valor >= faixa["melhor_impostora"]:
                    marca = "  <- PERMISSIVO demais (impostora entra)"
                else:
                    marca = "  <- APERTADO demais (usuario legitimo negado)"
                print(f"    nivel {nivel}: {valor:.4f}{marca}")
        else:
            print("\n  [ATENCAO] Nao existe limiar perfeito para estas fotos.")
            print("  Affaste o maior limiar possivel e ainda ha confusao.")

            # Descobre QUAIS pessoas causam a sobreposicao. A media geral
            # esconde: se so uma dupla se confunde, o problema e local.
            confusas = []
            for pessoa_a, pessoa_b in itertools.combinations(sorted(embeddings), 2):
                valores = [
                    d for pa, _na, pb, _nb, d in impostoras
                    if pa == pessoa_a and pb == pessoa_b
                ]
                r = resumir(valores)
                if r and r["min"] < res_gen["max"]:
                    confusas.append((pessoa_a, pessoa_b, r["min"]))

            if confusas:
                print("\n  Duplas de pessoas que se confundem entre si:")
                for pessoa_a, pessoa_b, menor in sorted(confusas, key=lambda x: x[2]):
                    print(f"    {pessoa_a} x {pessoa_b}: menor impostora {menor:.4f}")
                print("\n  Essas pessoas tem aparencia parecida E as fotos")
                print("  provavelmente tem pouca luz, o que achata a diferenca.")
            else:
                print("\n  Nenhuma dupla se confunde. A sobreposicao vem de fotos")
                print("  ruins de UMA pessoa contra as fotos dela mesma.")

            print("\n  Nao e bug do codigo. Refaca as fotos com mais luz e variacao.")

        if res_gen["mediana"] > 0.4:
            print(f"\n  [ATENCAO] Distancia genuina mediana em {res_gen['mediana']:.4f}.")
            print("  Para a MESMA pessoa, o esperado e abaixo de 0.3. Acima disso as")
            print("  fotos provavelmente tem pouca luz ou muito movimento.")

    elif res_gen:
        print("\n  So ha uma pessoa. Cadastre pelo menos 2 para medir impostores.")

    # ---- Simulacao do login real ----
    if len(embeddings) >= 2:
        for nivel in sorted(config.LIMIAR_DISTANCIA):
            analise_multi_template(embeddings, config.LIMIAR_DISTANCIA[nivel])

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
