"""
Ponto de entrada do projeto.

Hoje abre a interface de linha de comando (a interface grafica em
Tkinter entra na Fase 3). Para manter o comando unico, este arquivo
delega para app/cli.py.
"""

import sys

from app import cli

if __name__ == "__main__":
    sys.exit(cli.main())
