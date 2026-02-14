# Guia para Publicar no GitHub

## Passo 1: Criar o Repositório no GitHub

1. Acesse https://github.com/new
2. Escolha um nome para o repositório (ex: `bbb-vote-bot`)
3. **NÃO** marque as opções:
   - ❌ Add a README file
   - ❌ Add .gitignore
   - ❌ Choose a license
4. Clique em "Create repository"

## Passo 2: Conectar e Fazer Upload

Após criar o repositório, execute os seguintes comandos no PowerShell (substitua `SEU_USUARIO` e `NOME_DO_REPOSITORIO`):

```powershell
cd C:\bbb-vote-bot
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git
git push -u origin main
```

## Alternativa: Usar o Script Automático

Execute o script PowerShell:

```powershell
.\upload_github.ps1
```

O script irá guiá-lo através do processo.

