# Instruções para Fazer Push no GitHub

## Problema de Autenticação

O Git está tentando usar credenciais de outro usuário. Siga uma das opções abaixo:

## Opção 1: Usar Personal Access Token (Recomendado)

1. Crie um Personal Access Token no GitHub:
   - Acesse: https://github.com/settings/tokens
   - Clique em "Generate new token" > "Generate new token (classic)"
   - Dê um nome (ex: "bbb-vote-bot")
   - Selecione o escopo: `repo` (todas as permissões de repositório)
   - Clique em "Generate token"
   - **COPIE O TOKEN** (você não verá novamente!)

2. Execute o push usando o token:
   ```powershell
   git push -u origin main
   ```
   - Quando pedir usuário: digite `Douggx`
   - Quando pedir senha: **cole o token** (não sua senha do GitHub)

## Opção 2: Usar SSH (Mais Seguro)

1. Configure uma chave SSH:
   ```powershell
   # Verificar se já existe chave SSH
   ls ~/.ssh
   
   # Se não existir, criar uma nova
   ssh-keygen -t ed25519 -C "seu-email@exemplo.com"
   ```

2. Adicione a chave pública ao GitHub:
   - Copie o conteúdo de `~/.ssh/id_ed25519.pub`
   - Acesse: https://github.com/settings/keys
   - Clique em "New SSH key"
   - Cole a chave e salve

3. Altere o remote para SSH:
   ```powershell
   git remote set-url origin git@github.com:Douggx/bb3-vote-bot.git
   git push -u origin main
   ```

## Opção 3: Limpar Credenciais e Tentar Novamente

```powershell
# Limpar credenciais salvas
git credential-manager-core erase
# Ou no Windows:
cmdkey /list
cmdkey /delete:git:https://github.com

# Tentar push novamente (vai pedir credenciais)
git push -u origin main
```

## Verificar Status

```powershell
git remote -v
git status
```

