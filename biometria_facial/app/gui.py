"""Interface Tkinter para cadastro e controle de acesso biometrico."""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app import access_control
from app import audit
from app import capture
from app import config
from app import database
from app import embedder

EXTENSOES_IMAGEM = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
FILTROS_ARQUIVO = [
    ("Imagens e videos", "*.jpg *.jpeg *.png *.bmp *.webp *.mp4 *.avi *.mov *.mkv *.wmv *.flv *.m4v *.webm"),
    ("Todos os arquivos", "*.*"),
]


class BiometriaApp(tk.Tk):
    """Janela principal do aplicativo de biometria facial."""

    def __init__(self):
        super().__init__()
        config.garantir_pastas()
        audit.configurar()

        self.title("Biometria Facial | Controle de acesso")
        self.geometry("1040x720")
        self.minsize(900, 640)
        self.configure(bg="#f3f6f4")

        self._fila = queue.Queue()
        self._ocupado = False
        self._fechando = False
        self._botoes_acao = []
        self._fotos_cadastro = []

        self._configurar_estilo()
        self._criar_interface()
        self._atualizar_usuarios()
        self._atualizar_auditoria()
        self.after(100, self._processar_fila)
        self.protocol("WM_DELETE_WINDOW", self._fechar)

    def _configurar_estilo(self):
        estilo = ttk.Style(self)
        estilo.theme_use("clam")
        estilo.configure("TFrame", background="#f3f6f4")
        estilo.configure("Card.TFrame", background="#ffffff")
        estilo.configure("TLabel", background="#f3f6f4", foreground="#22332b", font=("Segoe UI", 10))
        estilo.configure("Card.TLabel", background="#ffffff", foreground="#22332b", font=("Segoe UI", 10))
        estilo.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground="#173d2b")
        estilo.configure("Subtitle.TLabel", foreground="#627269", font=("Segoe UI", 10))
        estilo.configure("CardTitle.TLabel", background="#ffffff", font=("Segoe UI", 13, "bold"))
        estilo.configure("CardText.TLabel", background="#ffffff", foreground="#5c6b63")
        estilo.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        estilo.configure("Primary.TButton", background="#167345", foreground="#ffffff")
        estilo.map("Primary.TButton", background=[("active", "#105b36"), ("disabled", "#9caea3")])
        estilo.configure("Treeview", rowheight=29, font=("Segoe UI", 9))
        estilo.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        estilo.configure("ResultAllowed.TLabel", background="#e7f5ec", foreground="#145c34", padding=14)
        estilo.configure("ResultDenied.TLabel", background="#fff0ed", foreground="#8a2e20", padding=14)

    def _criar_interface(self):
        topo = ttk.Frame(self, padding=(24, 18, 24, 12))
        topo.pack(fill="x")
        ttk.Label(topo, text="Biometria Facial", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            topo,
            text="Cadastro de pessoas e verificação de acesso por nível",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, padx=24, pady=(0, 12))

        self.aba_acesso = ttk.Frame(self.abas, padding=20)
        self.aba_cadastro = ttk.Frame(self.abas, padding=20)
        self.aba_usuarios = ttk.Frame(self.abas, padding=20)
        self.aba_auditoria = ttk.Frame(self.abas, padding=20)

        self.abas.add(self.aba_acesso, text="Acesso")
        self.abas.add(self.aba_cadastro, text="Cadastro")
        self.abas.add(self.aba_usuarios, text="Usuários")
        self.abas.add(self.aba_auditoria, text="Auditoria")

        self._criar_aba_acesso()
        self._criar_aba_cadastro()
        self._criar_aba_usuarios()
        self._criar_aba_auditoria()

        barra = ttk.Frame(self, padding=(24, 0, 24, 12))
        barra.pack(fill="x")
        ttk.Separator(barra).pack(fill="x", pady=(0, 8))
        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(barra, textvariable=self.status_var, style="Subtitle.TLabel").pack(anchor="w")

    def _criar_aba_acesso(self):
        self.aba_acesso.columnconfigure(0, weight=1)
        self.aba_acesso.rowconfigure(0, weight=1)

        cartao = ttk.Frame(self.aba_acesso, style="Card.TFrame", padding=24)
        cartao.grid(row=0, column=0, sticky="n", padx=70, pady=20)
        cartao.columnconfigure(1, weight=1)

        ttk.Label(cartao, text="Verificar acesso", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            cartao,
            text="Informe o usuário e selecione o nível do recurso que deseja acessar.",
            style="CardText.TLabel",
            wraplength=560,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 22))

        ttk.Label(cartao, text="ID do usuário", style="Card.TLabel").grid(
            row=2, column=0, sticky="w", padx=(0, 16), pady=8
        )
        self.login_id_var = tk.StringVar()
        ttk.Entry(cartao, textvariable=self.login_id_var, width=34).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=8
        )

        ttk.Label(cartao, text="Nível do recurso", style="Card.TLabel").grid(
            row=3, column=0, sticky="w", padx=(0, 16), pady=8
        )
        self.login_nivel_var = tk.StringVar(value="2")
        ttk.Combobox(
            cartao,
            textvariable=self.login_nivel_var,
            values=("1", "2", "3"),
            state="readonly",
            width=31,
        ).grid(row=3, column=1, columnspan=2, sticky="ew", pady=8)

        ttk.Label(cartao, text="Imagem / vídeo", style="Card.TLabel").grid(
            row=4, column=0, sticky="w", padx=(0, 16), pady=8
        )
        self.fonte_login_var = tk.StringVar(value="")
        ttk.Entry(cartao, textvariable=self.fonte_login_var, state="readonly").grid(
            row=4, column=1, sticky="ew", pady=8
        )
        ttk.Button(cartao, text="Selecionar", command=self._selecionar_fonte_login).grid(
            row=4, column=2, padx=(8, 0), pady=8
        )
        ttk.Button(cartao, text="Usar webcam", command=self._usar_webcam_login).grid(
            row=5, column=1, sticky="w", pady=(2, 8)
        )
        ttk.Button(cartao, text="Limpar", command=self._limpar_fonte_login).grid(
            row=5, column=2, sticky="e", pady=(2, 8)
        )

        ttk.Label(
            cartao,
            text="Nível 1 não exige reconhecimento facial. Para os níveis 2 e 3, "
                 "selecione uma imagem/vídeo ou use a webcam.",
            style="CardText.TLabel",
            wraplength=560,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 16))

        self.resultado_acesso = ttk.Label(
            cartao,
            text="O resultado da verificação aparecerá aqui.",
            style="CardText.TLabel",
            wraplength=560,
            justify="left",
        )
        self.resultado_acesso.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 14))

        botao = ttk.Button(
            cartao,
            text="Verificar acesso",
            style="Primary.TButton",
            command=self._verificar_acesso,
        )
        botao.grid(row=8, column=0, columnspan=3, sticky="ew")
        self._botoes_acao.append(botao)

    def _criar_aba_cadastro(self):
        self.aba_cadastro.columnconfigure(0, weight=1)
        cartao = ttk.Frame(self.aba_cadastro, style="Card.TFrame", padding=24)
        cartao.pack(fill="both", expand=True, padx=50, pady=12)
        cartao.columnconfigure(1, weight=1)
        cartao.rowconfigure(5, weight=1)

        ttk.Label(cartao, text="Cadastrar usuário", style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(
            cartao,
            text="As fotos são processadas para gerar embeddings criptografados; "
                 "as imagens originais não são armazenadas.",
            style="CardText.TLabel",
            wraplength=680,
        ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(5, 16))

        ttk.Label(cartao, text="ID", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=7)
        self.cadastro_id_var = tk.StringVar()
        ttk.Entry(cartao, textvariable=self.cadastro_id_var).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=7
        )

        ttk.Label(cartao, text="Nome", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=7)
        self.cadastro_nome_var = tk.StringVar()
        ttk.Entry(cartao, textvariable=self.cadastro_nome_var).grid(
            row=3, column=1, columnspan=2, sticky="ew", pady=7
        )

        ttk.Label(cartao, text="Nível", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=7)
        self.cadastro_nivel_var = tk.StringVar(value="1")
        ttk.Combobox(
            cartao,
            textvariable=self.cadastro_nivel_var,
            values=("1", "2", "3"),
            state="readonly",
        ).grid(row=4, column=1, columnspan=2, sticky="ew", pady=7)

        linha_fotos = ttk.Frame(cartao, style="Card.TFrame")
        linha_fotos.grid(row=5, column=0, columnspan=3, sticky="nsew", pady=(12, 8))
        linha_fotos.columnconfigure(0, weight=1)
        linha_fotos.rowconfigure(1, weight=1)
        ttk.Label(linha_fotos, text="Fotos de cadastro (recomendado: 3 a 5)", style="Card.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )

        lista_frame = ttk.Frame(linha_fotos, style="Card.TFrame")
        lista_frame.grid(row=1, column=0, sticky="nsew")
        lista_frame.columnconfigure(0, weight=1)
        lista_frame.rowconfigure(0, weight=1)
        self.lista_fotos = tk.Listbox(
            lista_frame,
            height=6,
            selectmode=tk.EXTENDED,
            font=("Segoe UI", 9),
            relief="solid",
            borderwidth=1,
        )
        self.lista_fotos.grid(row=0, column=0, sticky="nsew")
        barra = ttk.Scrollbar(lista_frame, orient="vertical", command=self.lista_fotos.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.lista_fotos.configure(yscrollcommand=barra.set)

        acoes_fotos = ttk.Frame(linha_fotos, style="Card.TFrame")
        acoes_fotos.grid(row=1, column=1, sticky="ns", padx=(10, 0))
        ttk.Button(acoes_fotos, text="Adicionar fotos", command=self._adicionar_fotos).pack(fill="x", pady=(0, 8))
        ttk.Button(acoes_fotos, text="Remover selecionadas", command=self._remover_fotos).pack(fill="x")

        self.cadastro_resultado_var = tk.StringVar(value="")
        ttk.Label(
            cartao,
            textvariable=self.cadastro_resultado_var,
            style="CardText.TLabel",
            wraplength=700,
        ).grid(row=6, column=0, columnspan=3, sticky="w", pady=(6, 10))
        botao = ttk.Button(
            cartao,
            text="Salvar cadastro",
            style="Primary.TButton",
            command=self._cadastrar_usuario,
        )
        botao.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        self._botoes_acao.append(botao)

    def _criar_aba_usuarios(self):
        self.aba_usuarios.columnconfigure(0, weight=1)
        self.aba_usuarios.rowconfigure(1, weight=1)
        cabecalho = ttk.Frame(self.aba_usuarios)
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(cabecalho, text="Usuários cadastrados", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(cabecalho, text="Atualizar", command=self._atualizar_usuarios).pack(side="right")

        self.tabela_usuarios = ttk.Treeview(
            self.aba_usuarios,
            columns=("id", "nome", "nivel", "amostras"),
            show="headings",
        )
        for coluna, texto, largura in (
            ("id", "ID", 180),
            ("nome", "Nome", 300),
            ("nivel", "Nível", 140),
            ("amostras", "Amostras faciais", 150),
        ):
            self.tabela_usuarios.heading(coluna, text=texto)
            self.tabela_usuarios.column(coluna, width=largura, anchor="w")
        self.tabela_usuarios.grid(row=1, column=0, sticky="nsew")
        barra = ttk.Scrollbar(self.aba_usuarios, orient="vertical", command=self.tabela_usuarios.yview)
        barra.grid(row=1, column=1, sticky="ns")
        self.tabela_usuarios.configure(yscrollcommand=barra.set)

    def _criar_aba_auditoria(self):
        self.aba_auditoria.columnconfigure(0, weight=1)
        self.aba_auditoria.rowconfigure(1, weight=1)
        cabecalho = ttk.Frame(self.aba_auditoria)
        cabecalho.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(cabecalho, text="Tentativas recentes", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(cabecalho, text="Atualizar", command=self._atualizar_auditoria).pack(side="right")

        self.tabela_auditoria = ttk.Treeview(
            self.aba_auditoria,
            columns=("data", "usuario", "recurso", "origem", "distancia", "resultado"),
            show="headings",
        )
        for coluna, texto, largura in (
            ("data", "Data/hora", 150),
            ("usuario", "Usuário", 130),
            ("recurso", "Recurso", 260),
            ("origem", "Origem", 90),
            ("distancia", "Distância", 90),
            ("resultado", "Resultado", 110),
        ):
            self.tabela_auditoria.heading(coluna, text=texto)
            self.tabela_auditoria.column(coluna, width=largura, anchor="w")
        self.tabela_auditoria.grid(row=1, column=0, sticky="nsew")
        barra = ttk.Scrollbar(self.aba_auditoria, orient="vertical", command=self.tabela_auditoria.yview)
        barra.grid(row=1, column=1, sticky="ns")
        self.tabela_auditoria.configure(yscrollcommand=barra.set)

    def _selecionar_fonte_login(self):
        caminho = filedialog.askopenfilename(
            title="Selecione uma imagem ou vídeo",
            filetypes=FILTROS_ARQUIVO,
        )
        if caminho:
            self.fonte_login_var.set(caminho)

    def _usar_webcam_login(self):
        self.fonte_login_var.set("webcam")

    def _limpar_fonte_login(self):
        self.fonte_login_var.set("")

    def _adicionar_fotos(self):
        caminhos = filedialog.askopenfilenames(
            title="Selecione fotos para o cadastro",
            filetypes=[
                ("Imagens", "*.jpg *.jpeg *.png *.bmp *.webp"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        for caminho in caminhos:
            if caminho not in self._fotos_cadastro:
                self._fotos_cadastro.append(caminho)
                self.lista_fotos.insert(tk.END, caminho)

    def _remover_fotos(self):
        selecionados = list(self.lista_fotos.curselection())
        for indice in reversed(selecionados):
            self.lista_fotos.delete(indice)
            del self._fotos_cadastro[indice]

    def _verificar_acesso(self):
        id_usuario = self.login_id_var.get().strip()
        if not id_usuario:
            messagebox.showwarning("Campo obrigatório", "Informe o ID do usuário.", parent=self)
            return

        nivel = int(self.login_nivel_var.get())
        fonte = self.fonte_login_var.get().strip()
        if nivel > config.NIVEL_TODOS and not fonte:
            messagebox.showwarning(
                "Imagem necessária",
                "Os recursos de nível 2 e 3 exigem uma imagem, um vídeo ou uma captura da webcam.",
                parent=self,
            )
            return

        def verificar(progresso):
            embedding = None
            origem = "interface"
            erro_imagem = ""

            if nivel > config.NIVEL_TODOS:
                origem = "webcam" if fonte.lower() == "webcam" else (
                    "video" if os.path.splitext(fonte)[1].lower() in capture.EXTENSOES_VIDEO else "arquivo"
                )
                progresso("Capturando imagem e analisando o rosto...")
                imagem = capture.capturar_por_fonte(fonte, indice_camera=0)
                if imagem is None:
                    raise ValueError("A captura foi cancelada.")
                embedding, detalhes = embedder.gerar_embedding_com_deteccao(
                    imagem,
                    exigir_qualidade=True,
                )
                if embedding is None:
                    erro_imagem = detalhes["erro"]
                else:
                    progresso("Rosto detectado. Verificando credenciais...")

            resultado = access_control.avaliar_acesso(
                id_usuario,
                nivel,
                embedding_tentativa=embedding,
                origem=origem,
            )
            return resultado, erro_imagem

        self.resultado_acesso.configure(text="Verificação em andamento...", style="CardText.TLabel")
        self._executar_em_segundo_plano(verificar, self._mostrar_resultado_acesso)

    def _mostrar_resultado_acesso(self, dados):
        resultado, erro_imagem = dados
        permitido = resultado["permitido"]
        linhas = [
            "ACESSO PERMITIDO" if permitido else "ACESSO NEGADO",
            f"Recurso: {resultado['recurso']}",
            f"Nível do usuário: {resultado['nivel_usuario'] or 'não encontrado'}"
            f"  |  Nível exigido: {resultado['nivel_recurso']}",
        ]
        if resultado["distancia"] is not None:
            linhas.append(
                f"Distância: {resultado['distancia']:.4f}"
                f"  |  Limiar: {resultado['limiar']:.4f}"
            )
            linhas.append(
                f"Amostras correspondentes: {resultado['amostras_com_match']}"
                f" de {resultado['amostras_avaliadas']}"
            )
        linhas.append(f"Motivo: {resultado['motivo']}")
        if erro_imagem:
            linhas.append(f"Imagem recusada: {erro_imagem}")

        self.resultado_acesso.configure(
            text="\n".join(linhas),
            style="ResultAllowed.TLabel" if permitido else "ResultDenied.TLabel",
        )
        self._atualizar_auditoria()

    def _cadastrar_usuario(self):
        id_usuario = self.cadastro_id_var.get().strip()
        nome = self.cadastro_nome_var.get().strip() or id_usuario
        if not id_usuario:
            messagebox.showwarning("Campo obrigatório", "Informe o ID do usuário.", parent=self)
            return

        nivel = int(self.cadastro_nivel_var.get())
        fotos = list(self._fotos_cadastro)

        def cadastrar(progresso):
            id_normalizado = database.normalizar_id(id_usuario)
            sucesso, mensagem = database.cadastrar_usuario(id_normalizado, nome, nivel)
            if not sucesso:
                raise ValueError(mensagem)

            selecionadas = fotos[: config.MAX_IMAGENS_CADASTRO]
            gravados = 0
            falhas = []
            for indice, caminho in enumerate(selecionadas, start=1):
                progresso(f"Processando foto {indice} de {len(selecionadas)}...")
                nome_arquivo = os.path.basename(caminho)
                try:
                    imagem = capture.carregar_imagem(caminho)
                    embedding, detalhes = embedder.gerar_embedding_com_deteccao(
                        imagem,
                        exigir_qualidade=True,
                        nitidez_minima=config.MIN_SHARPNESS_CADASTRO,
                    )
                    if embedding is None:
                        falhas.append(f"{nome_arquivo}: {detalhes['erro']}")
                        continue

                    gravado, motivo = database.adicionar_embedding(id_normalizado, embedding)
                    if gravado:
                        gravados += 1
                    else:
                        falhas.append(f"{nome_arquivo}: {motivo}")
                except Exception as erro:  # noqa: BLE001
                    falhas.append(f"{nome_arquivo}: {erro}")

            return {
                "id": id_normalizado,
                "gravados": gravados,
                "selecionadas": len(selecionadas),
                "falhas": falhas,
                "limite_excedido": len(fotos) > config.MAX_IMAGENS_CADASTRO,
            }

        self.cadastro_resultado_var.set("Salvando usuário e processando imagens...")
        self._executar_em_segundo_plano(cadastrar, self._mostrar_resultado_cadastro)

    def _mostrar_resultado_cadastro(self, dados):
        linhas = [f"Usuário '{dados['id']}' cadastrado. Amostras salvas: {dados['gravados']}."]
        if not dados["selecionadas"]:
            linhas.append("Nenhuma foto selecionada; esse usuário não terá acesso biométrico aos níveis 2 e 3.")
        if dados["limite_excedido"]:
            linhas.append(f"Foram usadas somente as {config.MAX_IMAGENS_CADASTRO} primeiras fotos.")
        if dados["falhas"]:
            linhas.append("Fotos não utilizadas:")
            linhas.extend(f"• {falha}" for falha in dados["falhas"])
        self.cadastro_resultado_var.set("\n".join(linhas))
        self._atualizar_usuarios()

    def _atualizar_usuarios(self):
        try:
            usuarios = database.listar_usuarios()
        except Exception as erro:  # noqa: BLE001
            messagebox.showerror("Erro ao carregar usuários", str(erro), parent=self)
            return

        self.tabela_usuarios.delete(*self.tabela_usuarios.get_children())
        for usuario in usuarios:
            self.tabela_usuarios.insert(
                "",
                tk.END,
                values=(
                    usuario["id"],
                    usuario["nome"],
                    usuario["nivel"],
                    usuario["qtd_embeddings"],
                ),
            )

    def _atualizar_auditoria(self):
        try:
            registros = database.listar_auditoria(limite=100)
        except Exception as erro:  # noqa: BLE001
            messagebox.showerror("Erro ao carregar auditoria", str(erro), parent=self)
            return

        self.tabela_auditoria.delete(*self.tabela_auditoria.get_children())
        for registro in registros:
            distancia = (
                f"{registro['distancia']:.4f}"
                if registro["distancia"] is not None
                else "—"
            )
            self.tabela_auditoria.insert(
                "",
                tk.END,
                values=(
                    registro["data_hora"],
                    registro["user_id"] or "—",
                    registro["recurso"] or "—",
                    registro["origem"] or "—",
                    distancia,
                    registro["resultado"],
                ),
            )

    def _executar_em_segundo_plano(self, operacao, ao_concluir):
        if self._ocupado:
            return
        self._ocupado = True
        self._ao_concluir = ao_concluir
        self.status_var.set("Trabalhando...")
        for botao in self._botoes_acao:
            botao.configure(state="disabled")

        def progresso(mensagem):
            self._fila.put(("progresso", mensagem))

        def executar():
            try:
                resultado = operacao(progresso)
            except Exception as erro:  # noqa: BLE001
                self._fila.put(("erro", str(erro)))
            else:
                self._fila.put(("resultado", resultado))

        threading.Thread(target=executar, daemon=True).start()

    def _processar_fila(self):
        if self._fechando:
            return

        try:
            while True:
                tipo, conteudo = self._fila.get_nowait()
                if tipo == "progresso":
                    self.status_var.set(conteudo)
                elif tipo == "erro":
                    self._finalizar_tarefa()
                    self.status_var.set("A operação não foi concluída.")
                    messagebox.showerror("Erro", conteudo, parent=self)
                else:
                    callback = self._ao_concluir
                    self._finalizar_tarefa()
                    callback(conteudo)
                    self.status_var.set("Pronto")
        except queue.Empty:
            pass

        self.after(100, self._processar_fila)

    def _finalizar_tarefa(self):
        self._ocupado = False
        for botao in self._botoes_acao:
            botao.configure(state="normal")

    def _fechar(self):
        self._fechando = True
        self.destroy()


def main():
    """Inicia a interface gráfica."""
    BiometriaApp().mainloop()
    return 0
