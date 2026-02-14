# Como Instalar a Extensão NopeCHA no Bot

A extensão NopeCHA resolve automaticamente CAPTCHAs (reCAPTCHA, hCaptcha, etc.) no navegador do bot.

## Passo 1: Baixar a Extensão

### Opção A: Usando Chrome (Recomendado)

1. Abra o Chrome e vá para: https://chromewebstore.google.com/detail/nopecha-captcha-solver/dknlfmjaanfblgfdfebhijalfmhmjjjo
2. Clique em "Adicionar ao Chrome" para instalar a extensão
3. Depois de instalada, vá para `chrome://extensions/`
4. Ative o "Modo do desenvolvedor" (canto superior direito)
5. Encontre a extensão "NopeCHA: CAPTCHA Solver"
6. Clique em "Detalhes"
7. Anote o "ID da extensão" (algo como: `dknlfmjaanfblgfdfebhijalfmhmjjjo`)

### Opção B: Baixar Manualmente

1. Use uma ferramenta como [CRX Extractor](https://chrome.google.com/webstore/detail/crx-extractordownload/ajkhmmldelboeejdcakjdaibfcdbpkhf) ou similar
2. Ou baixe diretamente usando:
   - URL: `https://clients2.google.com/service/update2/crx?response=redirect&prodversion=120.0&x=id%3Ddknlfmjaanfblgfdfebhijalfmhmjjjo%26uc`
   - Salve como `nopecha.crx`

## Passo 2: Encontrar o Caminho da Extensão

### Método 1: Localizar no Windows (Mais Fácil)

1. Abra o Windows Explorer
2. Cole este caminho na barra de endereço (substitua `[SEU_USUARIO]` pelo seu nome de usuário):
   ```
   C:\Users\[SEU_USUARIO]\AppData\Local\Google\Chrome\User Data\Default\Extensions
   ```
   
   **OU** use o atalho: Pressione `Win + R`, digite:
   ```
   %LOCALAPPDATA%\Google\Chrome\User Data\Default\Extensions
   ```

3. Procure pela pasta `dknlfmjaanfblgfdfebhijalfmhmjjjo` (ID da extensão NopeCHA)
4. Entre nessa pasta
5. Dentro, haverá uma pasta com a versão (ex: `0.5.5_0`)
6. **Este é o caminho que você precisa!**

Exemplo completo:
```
C:\Users\João\AppData\Local\Google\Chrome\User Data\Default\Extensions\dknlfmjaanfblgfdfebhijalfmhmjjjo\0.5.5_0
```

### Método 2: Usando PowerShell (Automático)

1. Abra o PowerShell
2. Execute este comando:
   ```powershell
   Get-ChildItem "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Extensions\dknlfmjaanfblgfdfebhijalfmhmjjjo" | Select-Object FullName
   ```
3. Copie o caminho completo mostrado

### Se você baixou o arquivo .crx:

1. Renomeie `nopecha.crx` para `nopecha.zip`
2. Extraia o conteúdo para uma pasta (ex: `nopecha_extension`)
3. Use o caminho dessa pasta

## Passo 3: Configurar no Bot

1. Abra o arquivo `config.json`
2. Adicione a linha `"extension_path"` com o caminho completo da extensão:

```json
{
  "participant_name": "Leandro",
  "num_tabs": 10,
  "vote_url": "https://gshow.globo.com/realities/bbb/bbb-26/voto-da-torcida/votacao/voto-da-torcida-quem-voce-quer-eliminar-do-bbb-26-fMdXG0MsZh.ghtml",
  "headless": false,
  "captcha_timeout": 300,
  "max_votes_per_tab": -1,
  "extension_path": "C:\\Users\\João\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Extensions\\dknlfmjaanfblgfdfebhijalfmhmjjjo\\0.5.5_0",
  "delay_between_votes": {
    "min": 2,
    "max": 5
  }
}
```

**IMPORTANTE:**
- Use barras invertidas duplas (`\\`) no Windows
- Use o caminho completo (absoluto)
- O caminho deve apontar para a pasta da extensão (não o arquivo .crx)

## Passo 4: Verificar se Funcionou

1. Execute o bot: `python main.py`
2. Quando o navegador abrir, verifique se a extensão NopeCHA está ativa
3. Você pode verificar em `chrome://extensions/` (mesmo no navegador do Playwright)

## Dicas

- Se a extensão não carregar, verifique se o caminho está correto
- Certifique-se de que a extensão está na versão mais recente
- No modo headless, extensões podem não funcionar - use `"headless": false`

## Solução de Problemas

### Erro: "Extension path not found"
- Verifique se o caminho está correto
- Certifique-se de usar barras duplas no Windows (`\\`)
- Verifique se a pasta da extensão existe

### Extensão não aparece no navegador
- Verifique se o caminho aponta para a pasta da extensão (não o arquivo .crx)
- Tente usar o caminho completo do Windows
- Certifique-se de que `headless` está como `false`

### Extensão não resolve CAPTCHAs
- Verifique se a extensão está ativa no Chrome Web Store
- Alguns sites podem detectar e bloquear extensões de CAPTCHA
- Considere usar a versão paga da NopeCHA para melhor suporte

