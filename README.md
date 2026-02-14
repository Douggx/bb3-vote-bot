# BBB Auto Vote Bot

Bot automatizado para votação no Big Brother Brasil 26 usando Playwright.

## Características

- ✅ Votação automática em múltiplas abas simultaneamente
- ✅ Detecção robusta de elementos (não depende de classes CSS que mudam)
- ✅ Suporte para resolução manual de captcha
- ✅ Loop contínuo de votação com botão "Votar Novamente"
- ✅ Detecção automática de estados da página (votação, confirmação, erro)
- ✅ Logging detalhado de todas as operações

## Requisitos

- Python 3.8 ou superior
- Playwright instalado

## Instalação

1. Clone ou baixe este repositório

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Instale os navegadores do Playwright:
```bash
playwright install chromium
```

## Configuração

Edite o arquivo `config.json`:

```json
{
  "participant_name": "Leandro",
  "num_tabs": 3,
  "vote_url": "https://gshow.globo.com/realities/bbb/bbb-26/voto-da-torcida/votacao/voto-da-torcida-quem-voce-quer-eliminar-do-bbb-26-fMdXG0MsZh.ghtml",
  "headless": false,
  "captcha_timeout": 300,
  "max_votes_per_tab": -1,
  "delay_between_votes": {
    "min": 2,
    "max": 5
  }
}
```

### Parâmetros de Configuração

- `participant_name`: Nome do participante para votar (ex: "Leandro", "Brigido", "Ana Paula Renault")
- `num_tabs`: Número de abas simultâneas
- `vote_url`: URL da página de votação
- `headless`: `false` para ver o navegador (recomendado para resolver captcha manualmente), `true` para modo invisível
- `captcha_timeout`: Tempo máximo de espera para resolução manual do captcha (segundos)
- `max_votes_per_tab`: Número máximo de votos por aba (-1 para infinito)
- `delay_between_votes`: Delay aleatório entre votos (em segundos)

## Uso

Execute o script principal:

```bash
python main.py
```

O bot irá:
1. Abrir o número de abas configurado
2. Navegar para a página de votação
3. Clicar no participante configurado
4. Aguardar você resolver o captcha manualmente
5. Após o voto ser confirmado, clicar em "Votar Novamente"
6. Repetir o processo indefinidamente

## Como Funciona

### Detecção Robusta de Elementos

O bot usa múltiplas estratégias para encontrar elementos, não dependendo de classes CSS que podem mudar:

1. **Botões de voto**: Prioriza `aria-label`, depois busca por texto, depois XPath
2. **Botão "Votar Novamente"**: Mesma estratégia com múltiplos fallbacks
3. **Estados da página**: Detecta votação ativa, confirmação de voto ou erros

### Resolução de Captcha

- O bot detecta automaticamente quando o captcha aparece
- Pausa e aguarda resolução manual
- Verifica periodicamente se o captcha foi resolvido
- Continua automaticamente após resolução

### Múltiplas Abas

- Cada aba funciona independentemente
- Votos são executados em paralelo
- Cada aba tem seu próprio contador de votos

## Logs

Os logs são salvos em:
- Console (stdout)
- Arquivo `bbb_vote_bot.log`

## Notas Importantes

⚠️ **Aviso Legal**: Este bot é apenas para fins educacionais. Use por sua conta e risco. O uso de bots para votação pode violar os termos de serviço do site.

⚠️ **Captcha Manual**: O bot requer resolução manual do captcha. Para automação completa, seria necessário integrar com serviços de resolução de captcha (2captcha, anti-captcha, etc.).

## Estrutura do Projeto

```
bbb-vote-bot/
├── main.py                 # Script principal
├── config.json             # Configurações
├── bot.py                  # Classe principal do bot
├── browser_manager.py      # Gerenciamento de múltiplas abas
├── captcha_handler.py      # Detecção e tratamento de captcha
├── requirements.txt        # Dependências
└── README.md              # Este arquivo
```

## Troubleshooting

### Bot não encontra o botão do participante
- Verifique se o nome do participante em `config.json` está exatamente como aparece na página
- Verifique se a URL está correta

### Captcha não é detectado
- Certifique-se de que `headless: false` para ver o que está acontecendo
- Aumente o `captcha_timeout` se necessário

### Erro ao instalar Playwright
- Certifique-se de ter Python 3.8+
- Tente: `pip install --upgrade playwright`
- Depois: `playwright install chromium`

## Funcionalidades Futuras

- [ ] Integração com serviços de captcha (2captcha, anti-captcha)
- [ ] Rotação de proxies
- [ ] Interface gráfica
- [ ] Estatísticas de votos em tempo real

## Licença

Este projeto é apenas para fins educacionais.

