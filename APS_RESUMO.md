# APS — Biometria Facial: Resumo do Trabalho

Documento de acompanhamento do projeto. Serve para o grupo retomar de onde
parou sem precisar ler a conversa inteira.

**Última atualização:** após a Fase 2 (código escrito, aguardando teste).

---

## 1. O que é o trabalho

Ferramenta de identificação e autenticação biométrica facial usada para
restringir o acesso a uma rede simulada do Ministério do Meio Ambiente
(propriedades rurais que usam agrotóxicos proibidos).

| Nível | Quem acessa | Autenticação |
|-------|-------------|--------------|
| 1 | Todos | Não exige biometria (o acesso é registrado no log mesmo assim) |
| 2 | Diretores de divisão | Biometria facial |
| 3 | Ministro do Meio Ambiente | Biometria facial mais rígida |

Regra central: **acesso liberado se `nivel_usuario >= nivel_recurso`**.

---

## 2. Estado atual

| Fase | Status |
|------|--------|
| Fase 1 — Núcleo | ✅ Código pronto. Modelos baixados, dependências instaladas. ⚠️ **Critério de pronto ainda não validado** (falta rodar o teste de distância) |
| Fase 2 — Cadastro e autenticação | ✅ Código pronto. ⚠️ **Não testado ainda** |
| Fase 3 — Interface Tkinter | ⬜ Não iniciada |
| Fase 4 — Avaliação (FAR/FRR/EER) | ⬜ Não iniciada |
| Fase 5 — Liveness e acabamento | ⬜ Não iniciada (opcional) |

**Nada foi testado de ponta a ponta ainda.** As fases 1 e 2 estão escritas,
mas o primeiro `teste_distancia.py` bem-sucedido ainda não aconteceu.

---

## 3. Arquivos criados

```
aps2026/
├── APS_RESUMO.md                      <- este documento
└── biometria_facial/
    ├── requirements.txt
    ├── .gitignore
    ├── main.py                        ponto de entrada (delega para a CLI)
    ├── README.md                      instalação, decisões e limitações
    ├── app/
    │   ├── config.py                  TODOS os parâmetros ajustáveis
    │   ├── capture.py                 imagem / vídeo / webcam
    │   ├── detector.py                YuNet + alinhamento + filtro de qualidade
    │   ├── embedder.py                SFace (vetor de 128 dims)
    │   ├── matcher.py                 distância cosseno + limiares
    │   ├── database.py                SQLite + criptografia Fernet
    │   ├── access_control.py          regras dos níveis
    │   ├── audit.py                   log em arquivo + ponte para o banco
    │   └── cli.py                     cadastrar / listar / login / log
    ├── scripts/
    │   ├── setup.sh                   cria venv, instala, baixa modelos, verifica
    │   ├── download_models.py
    │   ├── coletar_fotos.py           coleta guiada via webcam
    │   └── teste_distancia.py         teste rápido da Fase 1
    ├── models/                        .onnx (baixados, fora do git)
    └── data/                          banco, chave e fotos (fora do git)
```

---

## 4. Decisões técnicas (e o porquê)

**YuNet + SFace, ambos do OpenCV.** São leves, rodam em CPU pura e já vêm
no `opencv-contrib-python` — sem instalar framework de deep learning
separado. Decisão forte porque o prazo é curto e OpenCV funciona em Windows
e Linux sem complicação.

**Distância cosseno, não euclidiana.** O embedding representa *direção*, não
magnitude. A distância cosseno mede o ângulo entre os vetores, que é o que
importa. Por isso normalizamos antes de comparar.

**Multi-template com menor distância.** Cada foto de cadastro vira um
embedding. Na verificação 1:1 o rosto apresentado é comparado com todos e
vence a **menor** distância. Padrão em biometria multi-template: uma pose
desfavorável na captura não reprova o acesso sozinha.

**Verificação 1:1, não 1:N.** O usuário informa o ID e o rosto é comparado
só com as amostras dele. Mais simples, mais rápido e mais seguro — não
existe o risco de o sistema autenticar a pessoa errada por resemblecimento.

**Nada de fotos no banco.** Só o embedding, gravado criptografado com
Fernet (chave simétrica em `data/chave.key`). Se alguém copiar o `.db` sem a
chave, não lê nada.

**Nível 1 não exige biometria.** Todos acessam, mas o acesso é registrado
na auditoria do mesmo jeito — o requisito do trabalho é explícito nisso.

**Negar por nível antes de gastar biometria.** Se `nivel_usuario <
nivel_recurso`, o acesso é negado sem rodar reconhecimento facial. Quem não
pode entrar na sala não precisa que o sistema reconheça o rosto dele.

### A armadilha das dependências (já mordida)

A escolha `numpy<2` e `opencv-contrib-python` não são independentes:

- O **mediapipe** (liveness, Fase 5) quebra em runtime com numpy 2.x, mas
  declara a dependência **sem fixar versão** — o problema só aparece depois.
- O **OpenCV 4.11+** passou a exigir `numpy>=2`.

Ou seja: para manter numpy 1.26, é obrigatório o OpenCV **4.10.0.84**.
Combinar `numpy 1.26` com `opencv 4.12` não é possível. Está documentado no
`requirements.txt` e no `README.md`.

Outro erro clássico: instalar `opencv-python` em vez de
`opencv-contrib-python`. Os dois escrevem no mesmo namespace `cv2` e um
sobrescreve o outro — o sintoma é `cv2.FaceDetectorYN doesn't exist`. O
`setup.sh` já desinstala os dois antes de instalar o certo.

---

## 5. As fases e o critério de pronto de cada

### Fase 1 — Núcleo ✅ (falta validar)
`config.py`, `capture.py`, `detector.py`, `embedder.py`, download dos modelos.
**Pronto quando:** um script recebe duas fotos e imprime a distância cosseno.

### Fase 2 — Cadastro e autenticação ✅ (falta testar)
`database.py`, `audit.py`, `access_control.py`, `cli.py`, `matcher.py`.
**Pronto quando:** 3 usuários fictícios (níveis 1, 2 e 3) cadastrados e
autenticados via CLI, com a regra de nível respeitada.

### Fase 3 — Interface Tkinter ⬜
Telas de cadastro, login (arquivo / vídeo / webcam) e painel com os 3
níveis simulados.
**Pronto quando:** fluxo completo cadastro → login → acesso liberado ou
negado, tudo pela interface.

### Fase 4 — Avaliação ⬜
`tests/evaluate.py` com pares genuínos e impostores a partir de `data/`.
**Pronto quando:** ROC e FAR×FRR gerados em `tests/results/`, EER impresso,
e limiares sugeridos para o `config.py`.

### Fase 5 — Liveness e acabamento ⬜ (opcional)
Detecção de piscada exigida para níveis 2 e 3, README final, roteiro de
demonstração.

---

## 6. Como rodar agora

```bash
cd biometria_facial
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### Erro: `ModuleNotFoundError: No module named '_sqlite3'`

O Python da máquina foi compilado sem o módulo C do SQLite. Não é bug do
projeto. O sintoma só aparece no cadastro, bem depois da instalação.

Note no traceback qual interpretador está em uso. Se aparecer
`~/.pyenv/versions/...`, o venv herdou esse Python e não tem conserto
sem recriar.

```bash
# ver se algum python da máquina tem sqlite3
/usr/bin/python3 -c "import sqlite3; print('sistema OK')"
```

**Opção A** — reinstalar o Python do pyenv com suporte:
```bash
sudo apt install libsqlite3-dev
pyenv uninstall 3.11.10 && pyenv install 3.11.10
bash scripts/setup.sh --limpar
```

**Opção B** — recriar o venv com o Python do sistema:
```bash
rm -rf .venv
/usr/bin/python3 -m venv .venv
bash scripts/setup.sh
```

O `setup.sh` agora checa isso logo no começo e falha com a instrução certa,
em vez de deixar o erro aparecer no meio do cadastro.

### Foto reprovada no cadastro: "nitidez 0, min 60"

Sintoma parecido: todas as fotos da pessoa reprovam com nitidez 0–6.

**Não é foto ruim.** Nitidez 0 é numericamente impossível numa foto real —
significa que o recorte caiu numa região lisa (parede ou fundo). Investigue:

```bash
python scripts/diagnostico.py data/matheus --gravar
```

O script mostra, por imagem: dimensões, se foi redimensionada, nitidez da
foto inteira, posição e tamanho de cada rosto detectado, nitidez e contraste
do recorte, e salva uma cópia anotada com a caixa e os landmarks em
`tests/results/`. Abrindo essa imagem dá para ver se o YuNet está marcando
o rosto certo.

**Se for mesmo foto borrada** (nitidez entre 5 e 25, mas com contraste
normal), o limiar de 60 era rígido demais. Os valores atuais:

| Onde | Limiar | Por quê |
|------|--------|---------|
| Autenticação | `MIN_SHARPNESS = 25` | Foto ruim já está no banco e não pode ser corrigida |
| Cadastro | `MIN_SHARPNESS_CADASTRO = 12` | Melhor aceitar com aviso do que obrigar a refazer 5 fotos |

Ambos ficam em `app/config.py`. Use `--estrito` no cadastro para voltar ao
filtro cheio:

```bash
python app/cli.py cadastrar --id matheus --nivel 2 --fotos data/matheus --estrito
```

**Atenção:** a nitidez depende da resolução. Uma foto de 4000px tem muito
mais detalhe que uma de 640px, então a mesma pessoa tira nota pior só por
estar em imagem menor. Meça antes de mexer nos números.

### 6.1 Validar a Fase 1

```bash
python scripts/coletar_fotos.py ana
python scripts/teste_distancia.py data/ana/ana_1.jpg data/ana/ana_3.jpg
```

Esperado: distância **menor que 0.3** para duas fotos da mesma pessoa.
Se der `Nenhum rosto foi detectado` ou distância altíssima, normalmente é
foto com rosto pequeno, borrado ou em contraluz.

### 6.2 Fotos de teste

Para **cada** pessoa do grupo (entrando como usuário fictício):

```bash
python scripts/coletar_fotos.py ana
python scripts/coletar_fotos.py bruno
python scripts/coletar_fotos.py carla
```

O script abre a webcam, sugere uma pose por vez, e você aperta **ESPAÇO**
para capturar ou **ESC** para parar.

**Quantas fotos:** mínimo 3, máximo 5. Recomendado **5**, porque cada uma
vira um template e mais templates reduzem falso negativo.

**Quais poses** (é a ordem que o script sugere):

| # | Pose |
|---|-----|
| 1 | De frente para a câmera, rosto neutro |
| 2 | Virado levemente para a esquerda (~15°) |
| 3 | Virado levemente para a direita (~15°) |
| 4 | Leve sorriso, ainda de frente |
| 5 | Cabeça levemente inclinada para baixo ou para cima |

A variação de ângulo é o que mais importa. Sem ela as 5 fotos ficam quase
idênticas e o sistema não aprende a reconhecer a pessoa de outro ângulo.

**Requisitos técnicos** (o filtro recusa com o motivo informado):
rosto entre 60 px e 400 px, nitidez mínima, detecção com confiança ≥ 0.6,
luz frontal, fundo neutro, sem outra pessoa atrás.

**Dica para a Fase 4:** se der tempo, faça uma **segunda rodada** de 5
fotos (`ana_6.jpg` … `ana_10.jpg`) num dia ou iluminação diferente. A
`evaluate.py` lê a pasta `data/` direto, não o banco, então essas extras
servem como imagens de teste — é o que dá volume decente de pares genuínos
com só 3 pessoas. Sem elas o EER fica com intervalo de confiança enorme.

### 6.3 Cadastrar e testar a Fase 2

```bash
# cadastro (ajuste os nomes para o grupo real)
python app/cli.py cadastrar --id ana   --nome "Ana Souza"  --nivel 1 --fotos data/ana
python app/cli.py cadastrar --id bruno --nome "Bruno Lima" --nivel 2 --fotos data/bruno
python app/cli.py cadastrar --id carla --nome "Carla Dias" --nivel 3 --fotos data/carla

python app/cli.py listar
```

Os 4 casos que provam a regra `nivel_usuario >= nivel_recurso`:

```bash
# carla (nível 3) no recurso de nível 3  -> PERMITIDO
python app/cli.py login --id carla --fonte data/carla/carla_1.jpg --nivel 3

# bruno (nível 2) no recurso de nível 3 -> NEGADO por nível insuficiente
python app/cli.py login --id bruno --fonte data/bruno/bruno_1.jpg --nivel 3

# bruno (nível 2) no recurso de nível 2 -> PERMITIDO
python app/cli.py login --id bruno --fonte data/bruno/bruno_1.jpg --nivel 2

# ana no recurso de nível 1, sem foto nenhuma -> PERMITIDO
python app/cli.py login --id ana --nivel 1

python app/cli.py log
```

Os casos **2** e **4** são os mais interessantes para a demonstração: o 2 é
negado *sem* gastar biometria (a distância sai `n/a` no log) e o 4 libera
*sem* foto nenhuma. São as duas regras especiais do enunciado, rodando.

---

## 7. Próximos passos

### Imediato — fechar o teste da Fase 1

Rode o `teste_distancia.py` (seção 6.1). **Não avance sem ele passar.**
Se falhar, me cole a saída: a mensagem de erro do filtro de qualidade já diz
o que ajustar.

### Depois — coletar as fotos

Seção 6.2. Sem isso nada mais pode ser testado, porque nada pode ser
cadastrado.

### Depois — validar a Fase 2

Seção 6.3. Me cole a saída do `listar` e do `log`. Se algum cadastro
imprimir `[X]` nas fotos, o motivo vem junto.

### Em seguida — Fase 3 (Tkinter)

Criaria `ui/main_window.py` e `ui/panels.py`, reaproveitando `capture.py`,
`embedder.py` e `access_control.py` sem reescrever nada. Três telas:
cadastro, login e painel. O painel mostra as 3 telas de nível, liberada ou
bloqueada conforme o veredito, mais a lista de acessos recentes (lendo de
`audit.listar_ultimos()`). O `main.py` passa a abrir a interface em vez da CLI.

Cuidado importante: o reconhecimento facial é **lento** (YuNet + SFace por
foto leva centenas de ms). Rodar dentro do event loop do Tkinter trava a
janela. A solução mais simples é usar `after()` para processar em segundo
plano, ou aceitar o congelamento de meio segundo.

### Depois — Fase 4 (avaliação)

`tests/evaluate.py` lê as pastas em `data/`, gera todos os pares possíveis:
- **genuínos**: duas imagens da mesma pessoa
- **impostores**: uma imagem de cada pessoa contra todas as outras

Calcula FAR, FRR, EER, ROC e FAR×FRR com scikit-learn + matplotlib, salva
em `tests/results/` e sugere limiares para o `config.py`.

Com 3 pessoas × 5 fotos são 15 imagens e 210 pares, o que dá uma FAR/FRR
estimada em uma taxa real. Com a segunda rodada de fotos, o número dobra.

### Se sobrar tempo — Fase 5 (liveness)

Detecção de piscada exigida para níveis 2 e 3. O gancho já está pensado em
`access_control.avaliar_acesso()`, entre a comparação e o veredito — mas
deliberadamente **não** foi escrito: um liveness que nega sem implementação
seria pior do que liveness ausente. Se o mediapipe der problema na
instalação, a alternativa mais simples é calcular o EAR (EAR ratio) com
OpenCV puro, sem dependência nova.

---

## 8. Riscos e como estamos mitigando

| Risco | Mitigação | Situação |
|-------|-----------|----------|
| `cv2.FaceDetectorYN` ausente | `opencv-contrib-python` fixado; `setup.sh` desinstala o `opencv-python` antes; `detector.py` dá mensagem explicativa | ✅ Contornado |
| Conflito numpy × OpenCV × mediapipe | Versões fixadas e o motivo documentado | ✅ Contornado |
| Download dos `.onnx` bloqueado | URLs principais + espelho no HuggingFace + instrução de download manual | ✅ Contornado |
| Ambiente quebrado após install falhar | `bash scripts/setup.sh --limpar` | ✅ Contornado |
| Fotos de teste ruins | Filtro de qualidade com motivo explícito; roteiro de poses | ✅ Implementado |
| **Poucas fotos de teste → EER instável** | Segunda rodada de 5 fotos sugerida | ⚠️ Depende do grupo |
| **Interface travando no Tkinter** | Reconhecimento é lento; usar `after()` | ⬜ Não mitigado |
| **mediapipe falha no Windows** | Comentado no `requirements.txt`; alternativa em OpenCV puro | ⬜ Previsto |

---

## 9. Se o tempo apertar — ordem de corte

1. **Liveness (Fase 5 inteira)** → níveis 2 e 3 só por embedding. Documentar
   como limitação explícita. *É o primeiro a cair porque é o único que não
   afeta a demonstração das regras de acesso.*
2. **Entrada por vídeo e webcam** → só arquivo de imagem. O `capture.py` já
   é compartilhado, então o custo é quase zero de código.
3. **Painel com as 3 telas** → tela única dizendo "ACESSO LIBERADO" ou
   "ACESSO BLOQUEADO".
4. **Criptografia Fernet** → guardar o embedding em base64 puro, marcando no
   README que é versão de demonstração.
5. **Gráfico FAR×FRR** → manter só a ROC.

**Nunca cortar:** Fase 1 e Fase 2. Sem elas não existe APS.

---

## 10. Perguntas em aberto

Nenhuma bloqueante. As duas decisões que dependiam de informação do grupo já
foram tomadas:

- **Fotos de teste:** o grupo vai fotografar via `coletar_fotos.py`. Cada
  pessoa entra como usuário fictício.
- **Versão do Python:** 3.11, escolhida por compatibilidade com mediapipe,
  OpenCV e scikit-learn.

Pendência menor, para decidir quando chegar na Fase 4: **quantas pessoas vão
participar da coleta.** Com 3 o EER fica com intervalo de confiança grande;
com 5 fica mais convincente para a apresentação.
