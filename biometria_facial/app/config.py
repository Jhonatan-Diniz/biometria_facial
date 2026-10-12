"""
Configuração central do projeto.

Tudo que é ajustável fica aqui: caminhos, parâmetros dos modelos,
limiares de distância e regras de acesso. Nenhum outro módulo
deve ter "número mágico" (valor fixo espalhado pelo código).
"""

import os

# --- Caminhos ---
# BASE_DIR aponta para a pasta raiz do projeto (biometria_facial/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")          # fotos de teste
DB_PATH = os.path.join(DATA_DIR, "biometria.db")   # banco SQLite
KEY_PATH = os.path.join(DATA_DIR, "chave.key")     # chave de criptografia
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "auditoria.log")
RESULTS_DIR = os.path.join(BASE_DIR, "tests", "results")

# Arquivos de modelo (baixados pelo scripts/download_models.py)
YUNET_MODEL = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_MODEL = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

# --- Parâmetros do detector YuNet ---
# score_threshold: confiança mínima da detecção (0 a 1)
# nms_threshold:     limiar de supressão de não-máximos (evita caixa duplicada)
# top_k:             número máximo de rostos devolvidos
YUNET_SCORE_THRESHOLD = 0.6
YUNET_NMS_THRESHOLD = 0.3
YUNET_TOP_K = 5000

# Tamanho de entrada do detector. Frames de webcam/vídeo são redimensionados
# para caber neste lado maior; imagens de arquivo passam direto.
DETECT_MAX_SIDE = 640

# --- Qualidade mínima da imagem (filtro de fotos ruins) ---
# Tamanho do rosto, medido NA IMAGEM QUE O Yunet VÊ (a imagem reduzida),
# e não na imagem original. Medir na original reprovaria selfies tirados com
# câmera boa e aceitaria as mesmas fotos se o usuário reduzisse a resolução.
# Ver detector.avaliar_qualidade.
MIN_FACE_SIZE = 40          # lado menor do rosto, em px (na imagem de detecção)
MAX_FACE_SIZE = 400         # lado maior do rosto, em px (na imagem de detecção)

# Nitidez mínima: variância do Laplaciano no recorte do rosto.
# O Laplaciano realça mudanças de brilho; em foto nítida há muitos
# (olhos, sobrancelhas, borda do rosto) e a variância é alta.
#
# Estes valores foram MEDIDOS com scripts/diagnostico.py nas fotos de teste do
# grupo. Ver APS_RESUMO.md para a tabela com os números reais.
#
# ATENÇÃO: nitidez depende de resolução e de iluminação. Foto em baixa luz
# tem menos detalhe e pontua mais baixo mesmo estando em foco. Sempre meça
# antes de mudar o número:
#   python scripts/diagnostico.py data/<usuario>
MIN_SHARPNESS = 20.0

# Nitidez mínima no cadastro. Mais branda de propósito: no cadastro é melhor
# aceitar e avisar do que obrigar a pessoa a refazer 5 fotos. Na
# autenticação o filtro vale mais, porque uma foto ruim já está no banco e
# não pode mais ser corrigida.
MIN_SHARPNESS_CADASTRO = 8.0

# --- Parâmetros do reconhecedor SFace ---
EMBEDDING_SIZE = 128        # dimensão do vetor gerado pelo SFace

# --- Níveis de acesso ---
# O usuário só acessa recurso se nivel_usuario >= nivel_recurso.
NIVEL_TODOS = 1
NIVEL_DIRETOR = 2
NIVEL_MINISTRO = 3

# Limiar de distância cosseno por nível do RECURSO protegido.
# Distâncias pequenas = mais parecidos. O nível 3 é mais rígido
# (limiar menor), pois um falso positivo ali é mais grave.
# Esses valores são um ponto de partida; a Fase 4 (evaluate.py)
# calcula os limiares reais a partir das fotos de teste.
LIMIAR_DISTANCIA = {
    NIVEL_TODOS: 0.65,       # nível 1 não exige biometria, mas o valor é usado como fallback
    NIVEL_DIRETOR: 0.45,
    NIVEL_MINISTRO: 0.32,
}

# Quantas fotos o usuário precisa fornecer no cadastro.
MIN_IMAGENS_CADASTRO = 3
MAX_IMAGENS_CADASTRO = 5

# Níveis que exigem prova de vida (Fase 5, opcional).
NIVEL_COM_LIVENESS = (NIVEL_DIRETOR, NIVEL_MINISTRO)

# Liga/desliga a prova de vida. False até a Fase 5 ser implementada:
# enquanto isso, o sistema funciona só com a biometria facial.
LIVENESS_ATIVO = False

# --- Liveness (Fase 5) ---
EAR_LIMIAR_FECHADO = 0.20   # EAR abaixo disso = olho fechado
EAR_LIMIAR_ABERTO = 0.25     # EAR acima disso = olho aberto
PISCADAS_EXIGIDAS = 2
TIMEOUT_LIVENESS_SEG = 10


def caminho_recurso_exemplo(nivel):
    """
    Devolve o nome do recurso simulado de um determinado nível.
    A "rede" do Ministério é simulada por telas no Tkinter;
    aqui ficam só os nomes usados na interface e no log.
    """
    return {
        NIVEL_TODOS: "Painel público de propriedades",
        NIVEL_DIRETOR: "Diretoria de fiscalização",
        NIVEL_MINISTRO: "Painel do Ministro",
    }.get(nivel, "recurso desconhecido")


def garantir_pastas():
    """Cria as pastas de dados, modelos, logs e resultados se não existirem."""
    for pasta in (MODELS_DIR, DATA_DIR, LOG_DIR, RESULTS_DIR):
        os.makedirs(pasta, exist_ok=True)
