# Como Treinar o Reconhecimento de Captcha

## 📋 Visão Geral

Este sistema permite coletar e classificar imagens do captcha para treinar um modelo de machine learning que melhora a precisão do reconhecimento automático.

## 🚀 Passo a Passo

### 1️⃣ Coletar Imagens do Captcha

**Opção A: Coleta Automática (Recomendado)**

Execute o coletor automático que salva as imagens quando o captcha aparece:

```bash
python coletar_imagens_captcha.py
```

O script irá:
- Abrir o navegador na página de votação
- Quando aparecer o captcha, coletar automaticamente as 9 imagens do grid
- Salvar em `training_images/unclassified/`
- Continuar coletando enquanto você usa o bot normalmente

**Opção B: Coleta Manual**

Se preferir, você pode:
1. Tirar screenshots do captcha manualmente
2. Recortar as 9 imagens do grid
3. Salvar em `training_images/unclassified/`

### 2️⃣ Classificar as Imagens

Execute a interface gráfica para classificar as imagens coletadas:

```bash
python inserir_imagens_captcha.py
```

A interface permite:
- ✅ Ver cada imagem coletada
- ✅ Classificar como **MOUSE**, **PASSARINHO** ou **OUTRO**
- ✅ Navegar entre imagens (Anterior/Próximo)
- ✅ Importar mais imagens de uma pasta
- ✅ Ver estatísticas

**Como classificar:**

- **🖱️ MOUSE**: Clique quando a imagem mostrar um mouse de computador
  - Exemplo: "Toque em itens comumente usados com o item mostrado" (teclado)
  - Selecione todas as imagens que são mouses

- **🐦 PASSARINHO**: Clique quando a imagem mostrar um pássaro/passarinho
  - Exemplo: "Selecione todas as criaturas que poderiam se abrigar" (casinha)
  - Selecione todas as imagens que são passarinhos

- **❌ OUTRO**: Clique para imagens que não são mouse nem passarinho
  - Exemplo: roupas, sapatos, outros objetos

### 3️⃣ Treinar o Modelo

Depois de classificar imagens suficientes (recomendado: 50-100 de cada tipo):

```bash
python train_captcha_model.py train
```

O script irá:
- Carregar todas as imagens classificadas
- Treinar um modelo Random Forest
- Salvar em `models/captcha_model.pkl`
- Mostrar a precisão do modelo

### 4️⃣ Usar o Modelo Treinado

O bot usa automaticamente o modelo treinado quando:
- O arquivo `models/captcha_model.pkl` existe
- `captcha_mode: "auto"` está no `config.json`

## 📁 Estrutura de Pastas

```
bbb-vote-bot/
├── training_images/
│   ├── mouse/              # Imagens de mouse (classificadas)
│   ├── passarinho/         # Imagens de passarinho (classificadas)
│   ├── other/              # Outras imagens (classificadas)
│   └── unclassified/       # Imagens coletadas (aguardando classificação)
├── models/
│   └── captcha_model.pkl   # Modelo treinado (gerado automaticamente)
├── coletar_imagens_captcha.py    # Coleta automática
├── inserir_imagens_captcha.py    # Interface de classificação
└── train_captcha_model.py        # Treinamento do modelo
```

## 💡 Dicas Importantes

### Quantidade de Imagens

- **Mínimo**: 50-100 imagens por categoria
- **Ideal**: 200+ imagens por categoria
- **Quanto mais, melhor**: Mais imagens = maior precisão

### Variedade

Colete imagens variadas:
- ✅ Diferentes tipos de mouse (com fio, sem fio, cores diferentes)
- ✅ Diferentes tipos de passarinho (cores, tamanhos)
- ✅ Inclua imagens que NÃO são mouse/passarinho na pasta "other"

### Fluxo Recomendado

1. **Execute o bot normalmente** com `captcha_mode: "auto"`
2. **Em paralelo**, execute `coletar_imagens_captcha.py` para coletar imagens
3. **Periodicamente**, execute `inserir_imagens_captcha.py` para classificar
4. **Quando tiver imagens suficientes**, execute `train_captcha_model.py train`
5. **O modelo será usado automaticamente** na próxima execução do bot

## 🔧 Comandos Rápidos

```bash
# 1. Coletar imagens automaticamente
python coletar_imagens_captcha.py

# 2. Classificar imagens (interface gráfica)
python inserir_imagens_captcha.py

# 3. Treinar modelo
python train_captcha_model.py train

# 4. Ver estatísticas (dentro da interface gráfica)
# Clique no botão "📊 Estatísticas"
```

## ❓ Troubleshooting

**Erro: "Nenhuma imagem encontrada"**
- Certifique-se de que há imagens em `training_images/unclassified/`
- Use `coletar_imagens_captcha.py` para coletar

**Interface gráfica não abre**
- Verifique se tem tkinter instalado: `py -m pip install tk`

**Modelo não está sendo usado**
- Verifique se `models/captcha_model.pkl` existe
- Verifique os logs do bot para erros

**Precisão baixa**
- Colete mais imagens (200+ de cada tipo)
- Certifique-se de que as imagens estão classificadas corretamente
- Retreine o modelo

## 📊 Exemplo de Uso

```bash
# Terminal 1: Rodar o bot
py main.py

# Terminal 2: Coletar imagens
python coletar_imagens_captcha.py

# Quando tiver imagens suficientes:
# Terminal 2: Classificar
python inserir_imagens_captcha.py

# Depois de classificar:
# Terminal 2: Treinar
python train_captcha_model.py train
```

O modelo treinado será usado automaticamente pelo bot na próxima execução!

