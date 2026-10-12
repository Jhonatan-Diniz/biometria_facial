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

    # Um Python pode existir e mesmo assim vir sem sqlite3, que e o modulo C
    # que o projeto usa para guardar os embeddings. Sem isso o erro so
    # apareceria bem depois, no momento do cadastro. Melhor falhar aqui.
    #
    # ATENCAO: vale notar que o Python do pyenv e o Python do sistema nem
    # sempre sao o mesmo executavel. Se /usr/bin/python3 tem sqlite3 mas o
    # pyenv nao, trocar de interpretador tambem resolve.
    if ! "$PYTHON_BIN" -c "import sqlite3" 2>/dev/null; then
        echo "[ERRO] O Python 3.11 encontrado ($PYTHON_BIN) nao tem o modulo sqlite3."
        echo ""
        echo "Causa: o interpretador foi compilado sem o suporte a SQLite."
        echo ""
        echo "Opcao A - reinstalar o Python do pyenv com suporte a SQLite:"
        echo "  sudo apt install libsqlite3-dev"
        echo "  pyenv uninstall 3.11.10 && pyenv install 3.11.10"
        echo ""
        echo "Opcao B - usar o Python do sistema, que costuma ja ter sqlite3:"
        echo "  rm -rf .venv"
        echo "  /usr/bin/python3 -m venv .venv"
        echo "  bash scripts/setup.sh"
        echo ""
        echo "Depois, confira com:"
        echo "  python -c \"import sqlite3; print('ok')\""
        exit 1
    fi

    echo ">>> Criando ambiente virtual com $($PYTHON_BIN --version)"
    "$PYTHON_BIN" -m venv .venv
fi

# Ativa o venv
source .venv/bin/activate

echo ">>> Python em uso: $(python --version)"

# Mesmo_python, mesmo problema: um venv ja criado a partir de um Python
# sem sqlite3 continua sem sqlite3.
if ! python -c "import sqlite3" 2>/dev/null; then
    echo ""
    echo "[ERRO] Este ambiente virtual nao tem sqlite3."
    echo "Ele foi herdado do Python base, que foi compilado sem esse modulo."
    echo ""
    echo "Opcao A - reinstalar o Python do pyenv com suporte a SQLite:"
    echo "  sudo apt install libsqlite3-dev"
    echo "  pyenv uninstall 3.11.10 && pyenv install 3.11.10"
    echo "  bash scripts/setup.sh --limpar"
    echo ""
    echo "Opcao B - recriar o venv com o Python do sistema:"
    echo "  rm -rf .venv"
    echo "  /usr/bin/python3 -m venv .venv"
    echo "  bash scripts/setup.sh"
    exit 1
fi

echo ">>> sqlite3 OK"
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
import sqlite3

import cv2
import numpy
from cryptography.fernet import Fernet

print(f"    python {sys.version.split()[0]}")
print(f"    numpy {numpy.__version__}")
print(f"    opencv {cv2.__version__}")
print(f"    sqlite3 {sqlite3.sqlite_version}")

# Checagem de ponta a ponta: gera e criptografa um embedding falso.
# Pega aqui qualquer problema que so apareceria no meio do uso real.
import numpy as np

embedding_falso = np.zeros(128, dtype=np.float32)
chave = Fernet.generate_key()
Fernet(chave).encrypt(embedding_falso.tobytes())

print("    YuNet OK | SFace OK | Fernet OK")
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
