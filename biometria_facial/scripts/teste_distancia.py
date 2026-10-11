"""
Teste rapido da Fase 1: recebe DUAS fotos e imprime a distancia cosseno
entre os embeddings dos rostos encontrados.

Uso:
    python scripts/teste_distancia.py data/ana/foto1.jpg data/ana/foto2.jpg

Se as duas fotos forem da MESMA pessoa, a distancia deve ser pequena.
Se forem de pessoas diferentes, a distancia deve ser grande.
"""

import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import capture, config, embedder, matcher  # noqa: E402


def embedding_de_arquivo(caminho):
    """Carrega uma foto, detecta o rosto e devolve o embedding (ou None)."""
    imagem = capture.carregar_imagem(caminho)
    embedding, detalhes = embedder.gerar_embedding_com_deteccao(imagem, exigir_qualidade=False)

    if embedding is None:
        print(f"  {os.path.basename(caminho)}: FALHOU -> {detalhes['erro']}")
        return None

    print(f"  {os.path.basename(caminho)}: confianca={detalhes['score']:.2f}  dim={embedding.shape}")
    return embedding


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 1

    caminho_a, caminho_b = sys.argv[1], sys.argv[2]

    print("Extraindo embeddings...")
    emb_a = embedding_de_arquivo(caminho_a)
    emb_b = embedding_de_arquivo(caminho_b)

    if emb_a is None or emb_b is None:
        print("\n[ERRO] Nao foi possivel extrair o embedding de uma das fotos.")
        return 1

    distancia = matcher.distancia_cosseno(emb_a, emb_b)

    print("\n==============================")
    print(f"Distancia cosseno: {distancia:.4f}")
    print(f"Limiar nivel 2:    {matcher.limiar(config.NIVEL_DIRETOR):.4f}")
    print(f"Limiar nivel 3:    {matcher.limiar(config.NIVEL_MINISTRO):.4f}")
    print("==============================")
    if distancia < matcher.limiar(config.NIVEL_MINISTRO):
        print("Mesma pessoa (ou muito parecidos).")
    elif distancia < matcher.limiar(config.NIVEL_DIRETOR):
        print("Faces parecidas, mas acima do limiar do nivel 3.")
    else:
        print("Pessoas diferentes.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
