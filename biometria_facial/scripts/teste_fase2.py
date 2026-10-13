"""
Teste de aceitação da Fase 2.

Roda uma sequencia de cenarios e diz PASSOU ou FALHOU em cada um.
Este e o script que valida a Fase 2 inteira de uma vez.

Uso:
    python scripts/teste_fase2.py
    python scripts/teste_fase2.py --pessoas matheus yaskara jhonatan
"""

import argparse
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

from app import access_control, capture, config, database, embedder  # noqa: E402

# Resultado de cada cenario: (nome, passou, detalhe)
RESULTADOS = []


def checar(nome, condicao, detalhe=""):
    RESULTADOS.append((nome, bool(condicao), detalhe))
    marca = "PASSOU" if condicao else "FALHOU"
    print(f"  [{marca}] {nome}")
    if detalhe:
        print(f"          {detalhe}")
    return condicao


def embedding_de(caminho):
    """Extrai o embedding de uma foto, ou None se nao der."""
    try:
        imagem = capture.carregar_imagem(caminho)
        embedding, _detalhes = embedder.gerar_embedding_com_deteccao(
            imagem, exigir_qualidade=False
        )
        return embedding
    except Exception:  # noqa: BLE001
        return None


def primeira_foto(pessoa):
    """Primeira imagem encontrada na pasta da pessoa."""
    pasta = os.path.join(config.DATA_DIR, pessoa)
    if not os.path.isdir(pasta):
        return None
    for nome in sorted(os.listdir(pasta)):
        if os.path.splitext(nome)[1].lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}:
            return os.path.join(pasta, nome)
    return None


def main():
    analise = argparse.ArgumentParser(description="Teste de aceitacao da Fase 2.")
    analise.add_argument("--pessoas", nargs="*", default=None)
    args = analise.parse_args()

    config.garantir_pastas()

    print("=" * 70)
    print("TESTE DE ACEITACAO - FASE 2")
    print("=" * 70)

    # ---------------------------------------------------------------
    print("\n[1] Banco de dados e criptografia")
    # ---------------------------------------------------------------
    conexao = database.conectar()
    tabelas = {
        linha[0]
        for linha in conexao.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conexao.close()

    for tabela in ("users", "embeddings", "audit_log"):
        checar(f"tabela '{tabela}' existe", tabela in tabelas)

    checar("chave Fernet foi criada", os.path.exists(config.KEY_PATH))

    # O embedding no banco precisa estar cifrado: nao pode ser lido como texto.
    usuarios = database.listar_usuarios()
    checar("existe pelo menos 1 usuario cadastrado", len(usuarios) > 0,
           f"{len(usuarios)} encontrado(s)")

    if usuarios:
        primeiro = usuarios[0]["id"]
        conexao = database.conectar()
        linha = conexao.execute(
            "SELECT embedding FROM embeddings WHERE user_id = ? LIMIT 1", (primeiro,)
        ).fetchone()
        conexao.close()

        if linha:
            bruto = linha["embedding"]
            # Se estivesse em texto puro, os bytes flutuantes nao seriam legiveis
            # como utf-8. Como blob cifrado do Fernet, sempre comeca com 0x80.
            comecou_com_token = bruto[:1] == b"\x80"
            checar("embedding gravado esta CIFRADO (blob Fernet)",
                   comecou_com_token,
                   f"primeiro byte = {bruto[:1].hex()} (esperado 80)")

            # E precisa conseguir decifrar de volta
            try:
                decifrado = database.decifrar_embedding(bruto)
                checar("embedding decifra com a chave do sistema",
                       len(decifrado) == config.EMBEDDING_SIZE,
                       f"{len(decifrado)} dimensoes")
            except Exception as erro:  # noqa: BLE001
                checar("embedding decifra com a chave do sistema", False, str(erro))
        else:
            checar("usuario tem pelo menos 1 embedding", False,
                   f"'{primeiro}' nao tem nenhuma amostra")

    # ---------------------------------------------------------------
    print("\n[2] Regra de nivel (nivel_usuario >= nivel_recurso)")
    # ---------------------------------------------------------------
    checar("nivel 1 libera nivel 1", access_control.pode_acessar(1, 1))
    checar("nivel 1 nao libera nivel 2", not access_control.pode_acessar(1, 2))
    checar("nivel 2 libera nivel 2", access_control.pode_acessar(2, 2))
    checar("nivel 2 nao libera nivel 3", not access_control.pode_acessar(2, 3))
    checar("nivel 3 libera nivel 3", access_control.pode_acessar(3, 3))
    checar("nivel 3 libera nivel 1", access_control.pode_acessar(3, 1))

    # ---------------------------------------------------------------
    print("\n[3] Nivel 1 nao exige biometria")
    # ---------------------------------------------------------------
    if usuarios:
        alvo = usuarios[-1]["id"]
        r = access_control.avaliar_acesso(alvo, config.NIVEL_TODOS,
                                          embedding_tentativa=None)
        checar("nivel 1 libera sem nenhuma imagem", r["permitido"])
        checar("nivel 1 nao mexe em biometria (distancia vazia)",
               r["distancia"] is None)
        checar("nivel 1 registra auditoria mesmo liberando",
               r["resultado_registrado"] == access_control.PERMITIDO)

    # ---------------------------------------------------------------
    print("\n[4] Negacao por nivel insuficiente")
    # ---------------------------------------------------------------
    alvo_n2 = next((u["id"] for u in usuarios if u["nivel"] == 2), None)
    alvo_n3 = next((u["id"] for u in usuarios if u["nivel"] == 3), None)

    if alvo_n2:
        r = access_control.avaliar_acesso(alvo_n2, config.NIVEL_MINISTRO,
                                          embedding_tentativa=None)
        checar("usuario nivel 2 e negado no recurso nivel 3", not r["permitido"])
        checar("negacao por nivel NAO gasta biometria",
               r["distancia"] is None,
               "distancia vazia = regra de nivel resolveu antes do reconhecimento")
        checar("negacao por nivel registra auditoria",
               r["resultado_registrado"] == access_control.NEGADO)

    # ---------------------------------------------------------------
    print("\n[5] Autenticacao 1:1 (reconhecimento real)")
    # ---------------------------------------------------------------
    if args.pessoas:
        pessoas = args.pessoas
    else:
        pessoas = [u["id"] for u in usuarios if u["nivel"] >= 2]

    if len(pessoas) >= 2:
        pessoa = pessoas[0]
        foto = primeira_foto(pessoa)
        embedding = embedding_de(foto) if foto else None

        if embedding is None:
            checar(f"reconhecer '{pessoa}' com a propria foto", False,
                   "nao consegui extrair embedding da foto")
        else:
            nivel_usuario = database.buscar_usuario(pessoa)["nivel"]
            recurso = min(nivel_usuario, config.NIVEL_MINISTRO)

            r = access_control.avaliar_acesso(pessoa, recurso,
                                              embedding_tentativa=embedding,
                                              origem="teste")
            checar(f"'{pessoa}' e reconhecido com a propria foto",
                   r["permitido"],
                   f"distancia {r['distancia']:.4f} vs limiar {r['limiar']:.4f}"
                   if r["distancia"] is not None else r["motivo"])

            # ---- Impostor: a foto de um, contra o cadastro do outro ----
            pessoa_b = pessoas[1]
            r2 = access_control.avaliar_acesso(pessoa_b, recurso,
                                               embedding_tentativa=embedding,
                                               origem="teste")
            checar(f"impostor: '{pessoa}' apresentado como '{pessoa_b}' e NEGADO",
                   not r2["permitido"],
                   f"distancia {r2['distancia']:.4f} vs limiar {r2['limiar']:.4f}"
                   if r2["distancia"] is not None else r2["motivo"])

    else:
        print("  (poucas pessoas com nivel >= 2; rode com --pessoas)")

    # ---------------------------------------------------------------
    print("\n[6] Usuario inexistente")
    # ---------------------------------------------------------------
    r = access_control.avaliar_acesso("nao_existe_xyz", config.NIVEL_MINISTRO,
                                      embedding_tentativa=None)
    checar("usuario inexistente e negado", not r["permitido"])
    checar("usuario inexistente registra auditoria",
           r["resultado_registrado"] == access_control.NEGADO)

    # ---------------------------------------------------------------
    print("\n[7] Auditoria")
    # ---------------------------------------------------------------
    registros = database.listar_auditoria(limite=100)
    checar("ha registros de auditoria", len(registros) > 0, f"{len(registros)} registro(s)")

    if registros:
        completos = all(
            r["data_hora"] and r["resultado"] in ("PERMITIDO", "NEGADO")
            for r in registros
        )
        checar("todo registro tem data/hora e resultado", completos)

    checar("arquivo de log existe", os.path.exists(config.LOG_FILE), config.LOG_FILE)

    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    passaram = sum(1 for _n, ok, _d in RESULTADOS if ok)
    falharam = len(RESULTADOS) - passaram

    print(f"RESULTADO: {passaram}/{len(RESULTADOS)} verificacoes passaram")
    if falharam:
        print(f"\n{falharam} FALHARAM:")
        for nome, ok, detalhe in RESULTADOS:
            if not ok:
                print(f"  - {nome}" + (f" ({detalhe})" if detalhe else ""))
    else:
        print("FASE 2 COMPLETA.")

    print("=" * 70)
    return 0 if falharam == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
