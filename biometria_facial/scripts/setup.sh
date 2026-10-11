#!/usr/bin/env bash
# Cria o ambiente virtual do projeto e instala as dependencias.
#
# Uso:
#   bash scripts/setup.sh              # instala normal
#   bash scripts/setup.sh --limpar     # apaga o .venv e recomeca do zero
#
# Use --limpar se uma instalacao anterior falhar no meio do caminho
# e deixar pacotes pela metade.
set -e

cd "$(dirname "$0")/.."

# ---------------------------------------------------------------
# --limpar: comeca do zero, evitando ambiente corrompido
# ---------------------------------------------------------------
if [ "$1" == "--limpar" ]; then
    echo ">>> Removendo o ambiente virtual anterior"
    rm -rf .venv
fi

# ---------------------------------------------------------------
# Cria o venv
# ---------------------------------------------------------------
if [ ! -d ".venv" ]; then
    # Descobre um python 3.11 disponivel na maquina
    PYTHON_BIN=""
    for candidato in python3.11 python3 python; do
        if command -v "$candidato" >/dev/null 2>&1; then
            if "$candidato" -c 'import sys; sys.exit(0 if sys.version_info[:2]==(3,11) else 1)' 2>/dev/null; then
                PYTHON_BIN="$candidato"
                break
            fi
        fi
    done

    if [ -z "$PYTHON_BIN" ]; then
        echo "[ERRO] Python 3.11 nao encontrado no PATH."
        echo "Instale o Python 3.11 e tente de novo."
        exit 1
    fi

    echo ">>> Criando ambiente virtual com $($PYTHON_BIN --version)"
    "$PYTHON_BIN" -m venv .venv
fi

# Ativa o venv
source .venv/bin/activate

echo ">>> Python em uso: $(python --version)"
echo ">>> Atualizando pip"
python -m pip install --upgrade pip

# ---------------------------------------------------------------
# Limpeza preventiva: garante que NAO exista opencv-python junto,
# que e a causa numero 1 de "cv2.FaceDetectorYN nao existe"
# ---------------------------------------------------------------
echo ">>> Removendo possiveis instalacoes conflitantes do OpenCV"
python -m pip uninstall -y opencv-python opencv-contrib-python-headless opencv-python-headless >/dev/null 2>&1 || true

echo ">>> Instalando dependencias"
python -m pip install -r requirements.txt

# ---------------------------------------------------------------
# Verificacao: o OpenCV instalado tem YuNet e SFace?
# ---------------------------------------------------------------
echo ">>> Verificando YuNet e SFace"
python - <<'PYCODE'
import sys
import cv2
import numpy

print(f"    numpy {numpy.__version__}")
print(f"    opencv {cv2.__version__}")

problemas = []
if not hasattr(cv2, "FaceDetectorYN"):
    problemas.append("cv2.FaceDetectorYN ausente (falta opencv-contrib-python)")
if not hasattr(cv2, "FaceRecognizerSF"):
    problemas.append("cv2.FaceRecognizerSF ausente (falta opencv-contrib-python)")

if problemas:
    print("\n[ERRO] OpenCV instalado nao serve para este projeto:")
    for p in problemas:
        print(f"    - {p}")
    print("\nTente: bash scripts/setup.sh --limpar")
    sys.exit(1)

print("    YuNet OK | SFace OK")
PYCODE

echo ">>> Baixando os modelos .onnx"
python scripts/download_models.py

echo ""
echo "==================================================="
echo " Instalacao concluida!"
echo ""
echo " Ativar ambiente :  source .venv/bin/activate"
echo "                   (Windows: .venv\\Scripts\\activate)"
echo ""
echo " Coletar fotos   :  python scripts/coletar_fotos.py ana"
echo " Testar distancia :  python scripts/teste_distancia.py a.jpg b.jpg"
echo "==================================================="
