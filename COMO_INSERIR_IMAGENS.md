# Como Inserir Imagens do Captcha

## Método Simples: Copiar e Colar na Pasta

### Passo 1: Preparar as Imagens

1. **Coletar imagens do captcha:**
   - Tire screenshots do captcha quando aparecer
   - OU salve as imagens do grid (9 imagens por captcha)
   - Formato aceito: PNG, JPG, JPEG, BMP

2. **Organizar as imagens:**
   - Você pode salvar todas as imagens em qualquer pasta
   - Não precisa renomear ou organizar antes

### Passo 2: Inserir as Imagens

**Opção A: Copiar e Colar Diretamente**

1. Abra o Windows Explorer
2. Navegue até a pasta do projeto: `C:\bbb-vote-bot\`
3. Vá para a pasta: `training_images\unclassified\`
   - Se a pasta não existir, ela será criada automaticamente
4. **Cole as imagens** nesta pasta (Ctrl+V)

**Opção B: Usar a Interface Gráfica**

1. Execute: `python inserir_imagens_captcha.py`
2. Clique em **"📁 Importar de Pasta"**
3. Selecione a pasta onde estão suas imagens
4. As imagens serão copiadas automaticamente

### Passo 3: Classificar as Imagens

1. Execute: `python inserir_imagens_captcha.py`
2. As imagens que você colou aparecerão automaticamente
3. Para cada imagem, clique em:
   - **🖱️ MOUSE** - se for um mouse de computador
   - **🐦 PASSARINHO** - se for um pássaro/passarinho
   - **❌ OUTRO** - se não for nenhum dos dois
4. Use **"🔄 Atualizar"** se adicionou novas imagens

### Passo 4: Treinar o Modelo

Depois de classificar imagens suficientes (50-100 de cada tipo):

```bash
python train_captcha_model.py train
```

## Estrutura de Pastas

```
bbb-vote-bot/
└── training_images/
    ├── unclassified/     ← COLE AS IMAGENS AQUI
    ├── mouse/            ← Imagens classificadas como mouse
    ├── passarinho/       ← Imagens classificadas como passarinho
    └── other/            ← Outras imagens
```

## Dicas

- **Nome dos arquivos**: Não importa o nome, pode ser qualquer coisa
- **Quantidade**: Cole quantas imagens quiser de uma vez
- **Formato**: PNG, JPG, JPEG, BMP são aceitos
- **Tamanho**: Qualquer tamanho funciona (será redimensionado automaticamente)

## Exemplo Prático

1. Você vê o captcha no navegador
2. Tira screenshot ou salva as 9 imagens do grid
3. Copia as imagens (Ctrl+C)
4. Vai em `C:\bbb-vote-bot\training_images\unclassified\`
5. Cola as imagens (Ctrl+V)
6. Abre `python inserir_imagens_captcha.py`
7. Classifica cada imagem
8. Treina o modelo quando tiver imagens suficientes

Pronto! É simples assim! 🎉

