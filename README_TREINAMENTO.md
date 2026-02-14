# Sistema de Treinamento de Captcha

Este sistema permite coletar imagens do captcha e treinar um modelo de machine learning para melhorar a precisão do reconhecimento automático.

## Instalação

As dependências já estão no `requirements.txt`. Instale com:

```bash
pip install -r requirements.txt
```

## Como Funciona

### 1. Coletar Imagens do Captcha

Execute o coletor de imagens:

```bash
python train_captcha_model.py collect
```

Este script irá:
- Abrir o navegador na página de votação
- Quando aparecer o captcha, você deve resolver manualmente
- As 9 imagens do grid serão coletadas automaticamente
- Você será perguntado qual tipo de desafio é (Mouse, Passarinho ou Outro)
- As imagens serão salvas nas pastas correspondentes:
  - `training_images/mouse/` - Imagens de mouse
  - `training_images/passarinho/` - Imagens de passarinho
  - `training_images/other/` - Outras imagens

**Dica**: Colete pelo menos 10-20 grids de cada tipo para ter um bom modelo.

### 2. Classificar Imagens Manualmente (Opcional)

Se você já tem imagens coletadas e quer classificá-las manualmente:

```bash
python train_captcha_model.py classify
```

Coloque as imagens em `training_images/unclassified/` e o script irá:
- Mostrar cada imagem
- Perguntar qual categoria ela pertence
- Mover para a pasta correta

### 3. Treinar o Modelo

Depois de coletar imagens suficientes, treine o modelo:

```bash
python train_captcha_model.py train
```

O script irá:
- Carregar todas as imagens das pastas
- Extrair características de cada imagem
- Treinar um modelo Random Forest
- Salvar o modelo em `models/captcha_model.pkl`
- Mostrar a precisão do modelo

### 4. Usar o Modelo Treinado

O bot usa automaticamente o modelo treinado se ele existir em `models/captcha_model.pkl`.

Se o modelo não existir, o bot usa detecção por características visuais (método padrão).

## Estrutura de Pastas

```
bbb-vote-bot/
├── training_images/
│   ├── mouse/          # Imagens de mouse coletadas
│   ├── passarinho/     # Imagens de passarinho coletadas
│   ├── other/          # Outras imagens
│   └── unclassified/   # Imagens para classificar manualmente
├── models/
│   └── captcha_model.pkl  # Modelo treinado (gerado automaticamente)
└── train_captcha_model.py  # Script de treinamento
```

## Dicas

1. **Quantidade de Imagens**: 
   - Mínimo: 50-100 imagens por categoria
   - Ideal: 200+ imagens por categoria
   - Quanto mais imagens, melhor a precisão

2. **Variedade**:
   - Colete imagens de diferentes tipos de mouse (com fio, sem fio, diferentes cores)
   - Colete imagens de diferentes tipos de passarinho
   - Inclua imagens que NÃO são mouse/passarinho na pasta "other"

3. **Retreinar**:
   - Se a precisão não estiver boa, colete mais imagens e retreine
   - Você pode adicionar mais imagens às pastas e treinar novamente

4. **Testar**:
   - Depois de treinar, teste o bot com `captcha_mode: "auto"` no `config.json`
   - Observe os logs para ver se está usando o modelo treinado

## Comandos Rápidos

```bash
# Coletar imagens
python train_captcha_model.py collect

# Classificar imagens
python train_captcha_model.py classify

# Treinar modelo
python train_captcha_model.py train
```

## Troubleshooting

**Erro: "Nenhuma imagem de treinamento encontrada"**
- Certifique-se de que há imagens nas pastas `training_images/mouse/` ou `training_images/passarinho/`

**Modelo não está sendo usado**
- Verifique se o arquivo `models/captcha_model.pkl` existe
- Verifique os logs do bot para ver se há erros ao carregar o modelo

**Precisão baixa**
- Colete mais imagens de treinamento
- Certifique-se de que as imagens estão classificadas corretamente
- Retreine o modelo

