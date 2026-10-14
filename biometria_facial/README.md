# APS — Biometria Facial para Controle de Acesso

Ferramenta de identificação e autenticação biométrica facial usada para
restringir o acesso a uma rede simulada do Ministério do Meio Ambiente
(propriedades rurais que usam agrotóxicos proibidos).

## Níveis de acesso

| Nível | Quem acessa | Autenticação |
|-------|-------------|---------------|
| 1 | Todos | Não exige biometria (o acesso é registrado no log mesmo assim) |
| 2 | Diretores de divisão | Biometria + (opcional) prova de vida |
| 3 | Ministro do Meio Ambiente | Biometria mais rígida + (opcional) prova de vida |

Regra: `nivel_usuario >= nivel_recurso` libera o acesso.

Na aba **Usuários** da interface, selecione uma pessoa para alterar seu nível
ou excluí-la. A exclusão remove também as amostras faciais, mas preserva os
registros de auditoria.

## Estado atual

**Fase 1 (núcleo) implementada.** Ainda não é o sistema completo: falta o
banco de dados, o cadastro, a interface e a avaliação.

O que já funciona:
- captura de imagem a partir de arquivo, vídeo ou webcam;
- detecção de rosto com YuNet e alinhamento pelos 5 pontos de referência;
- geração do embedding de 128 dimensões com SFace;
- distância cosseno entre dois embeddings.

## Instalação

Requisitos: Python 3.11, CPU. Funciona em Windows e Linux.

```bash
cd biometria_facial
bash scripts/setup.sh
```

O script cria o venv, instala as dependências, remove instalações
conflitantes do OpenCV, verifica se YuNet e SFace estão presentes e baixa
os modelos. Se uma instalação anterior falhar no meio e deixar o ambiente
quebrado:

```bash
bash scripts/setup.sh --limpar
```

Ou manualmente:

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/download_models.py
```

### Por que estas versões específicas

Este é o ponto que mais gera dor de cabeça, então vale registrar:

| Pacote | Versão | Motivo |
|--------|--------|--------|
| `numpy` | `1.26.4` | O mediapipe (Fase 5) quebra em runtime com numpy 2.x (`numpy has no attribute 'bool8'`). Ele nem declara essa restrição no `pip install`, então o problema só aparece em runtime. |
| `opencv-contrib-python` | `4.10.0.84` | Precisa aceitar numpy 1.x. A partir da série 4.11 o OpenCV passou a exigir `numpy>=2`, o que conflita com o numpy 1.26 acima. |
| `mediapipe` | comentado | Arrasta `jax`/`jaxlib`, que são pesados, e às vezes conflita. Como o liveness é a Fase 5 e é opcional, o projeto fica completo sem ele. |

Dois erros clássicos, ambos cobertos pelo `setup.sh`:

1. **`cv2.FaceDetectorYN doesn't exist`** — significa que foi instalado
   `opencv-python` em vez de `opencv-contrib-python`. Os dois pacotes
   escrevem no mesmo namespace `cv2` e um sobrescreve o outro. O script
   desinstala os dois antes de instalar o certo.
2. **Instalação que falha no meio** — deixa pacotes pela metade. Use
   `bash scripts/setup.sh --limpar`.


## Coleta de fotos de teste

Você ainda não tinha fotos prontas, então a primeira coisa é coletar.
Para cada pessoa do grupo (que entrará como usuário fictício):

```bash
python scripts/coletar_fotos.py ana
python scripts/coletar_fotos.py bruno
python scripts/coletar_fotos.py carla
```

O script guia a pessoa por 5 poses e salva as fotos em `data/<id>/`.
As fotos **não** entram no git (ver `.gitignore`).

Dicas para uma foto boa: luz frontal, fundo neutro, rosto de frente e
ocupando boa parte da imagem.

## Teste da Fase 1

Com duas fotos (da mesma pessoa), o script imprime a distância cosseno:

```bash
python scripts/teste_distancia.py data/ana/ana_1.jpg data/ana/ana_3.jpg
```

Como ler o resultado:
- distância pequena (< 0.3): mesma pessoa
- distância grande (> 0.5): pessoas diferentes

## Estrutura de pastas

```
biometria_facial/
├── app/
│   ├── capture.py         # arquivo, vídeo, webcam
│   ├── detector.py        # YuNet + alinhamento + filtro de qualidade
│   ├── embedder.py        # SFace
│   ├── matcher.py         # distância cosseno + limiares
│   └── config.py          # todos os parâmetros ajustáveis
├── scripts/
│   ├── setup.sh           # cria venv, instala, baixa modelos
│   ├── download_models.py
│   ├── coletar_fotos.py
│   └── teste_distancia.py
├── models/                # .onnx (baixados, fora do git)
└── data/                  # banco, chave e fotos (fora do git)
```

## Decisões técnicas

**Por que YuNet e SFace?** São modelos leves, rodam em CPU sem aceleração
e vêm dentro do próprio OpenCV — sem installs extras de deep learning.

**Por que distância cosseno e não distância euclidiana?** O embedding é
um vetor de direção, não de magnitude. A distância cosseno mede o ângulo,
que é o que realmente importa. Por isso normalizamos o vetor antes.

**Alinhamento.** Antes de gerar o embedding, o rosto é recortado e
"chapado" para 112×112 usando os 5 pontos de referência do YuNet
(olhos, nariz, boca). Sem isso a taxa de reconhecimento cai bastante,
porque uma foto de frente e uma de leve ângulo produzem vetores diferentes.

**Filtro de qualidade.** YuNet só detecta rostos entre ~10×10 e ~300×300 px.
Fotos com rosto pequeno, grande, borrado ou detectado com pouca confiança
são recusadas com uma mensagem explicando o motivo. Isso evita que um
embedding ruim entre no banco.

**Limiares por nível.** Nível 3 tem limiar menor (0.32) que o nível 2
(0.45): quanto mais restrito o dado, menos tolerate a falso positivo.
Esses valores são ponto de partida; a Fase 4 calcula os reais a partir
das fotos do grupo.

## Resultados medidos (fotos do grupo, 3 pessoas × ~5 fotos)

Medido com `scripts/matriz_distancias.py`, que faz teste **hold-out**:
remove uma foto da galeria e a usa como se fosse a foto de prova do dia
seguinte. Isso importa porque comparar fotos de cadastro entre si subestima
a distância real — elas foram tiradas na mesma sessão, com a mesma luz.

| Métrica | Valor |
|---------|-------|
| Reconhecimento de foto **nova** (hold-out) | 9/12 — **75%** |
| Pior impostora (pessoa errada) | 0.5173 |
| Limiar nível 2 / 3 | 0.48 / 0.45 |

**Por que 75% e não 100%.** Três fotos de prova deram 0.5199, 0.5012 e
0.5241 — acima da pior impostora. Não existe limiar que aceite essas três
e ainda barre a impostora: subir o limiar para ~0.53 resolve o falso
negativo, mas deixa a pessoa errada entrar.

Os limiares foram escolhidos para **priorizar a segurança**: ficam abaixo
de 0.5173, então nenhuma impostora entra. O preço é o falso negativo — as
fotos de prova mais difíceis são negadas.

Em controle de acesso, negar o legítimo é um erro annoyance; deixar o
intruso entrar é o erro grave. Daí a escolha.

### Limitação principal

A causa é a qualidade da captura, não o código. As fotos de teste têm
nitidez entre 9 e 54 (medida por `scripts/diagnostico.py`) e brilho médio
de 96/255. Rosto com pouco detalhe produz embedding instável, e o
resultado são dois "modos" de distância: 0.15–0.43 e 0.50–0.52.

**Como melhorar**, se houver tempo antes da apresentação:

1. **Luz de janela ou luminária** frontal. É o fator de maior impacto.
2. **Variar a pose** ~15° para esquerda e direita entre as fotos.
3. **Mais pessoas** no teste (5 em vez de 3): afunila as duas distribuições
   e deixa o limiar confiável.

Nenhuma dessas mudanças altera código — apenas os dados de entrada.

## Limitações conhecidas

- Ainda não há banco de dados nem cadastro (Fase 2).
- Sem prova de vida (anti-spoofing): segurar uma foto na frente da câmera
  engana o sistema. É a Fase 5, opcional.
- `mediapipe` (Fase 5) às vezes falha em Windows; se der problema,
  o liveness pode ser feito com OpenCV puro.
- O número de usuários de teste é pequeno (3 a 5), então o EER da Fase 4
  terá intervalo de confiança grande. Isso é esperado em trabalho acadêmico.
