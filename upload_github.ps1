# Script para fazer upload do repositório para o GitHub
# Execute este script após criar o repositório no GitHub

Write-Host "=== Upload para GitHub ===" -ForegroundColor Cyan
Write-Host ""

# Solicitar o nome do repositório
$repoName = Read-Host "Digite o nome do repositório no GitHub (ex: bbb-vote-bot)"

# Solicitar o nome de usuário do GitHub
$username = Read-Host "Digite seu nome de usuário do GitHub"

Write-Host ""
Write-Host "Opções:" -ForegroundColor Yellow
Write-Host "1. Repositório público"
Write-Host "2. Repositório privado"
$visibility = Read-Host "Escolha uma opção (1 ou 2)"

$isPrivate = if ($visibility -eq "2") { "--private" } else { "--public" }

Write-Host ""
Write-Host "Criando repositório no GitHub..." -ForegroundColor Green

# Verificar se o GitHub CLI está instalado
$ghInstalled = Get-Command gh -ErrorAction SilentlyContinue

if ($ghInstalled) {
    # Usar GitHub CLI se disponível
    Write-Host "Usando GitHub CLI..." -ForegroundColor Green
    gh repo create $repoName $isPrivate --source=. --remote=origin --push
} else {
    # Instruções manuais
    Write-Host ""
    Write-Host "GitHub CLI não está instalado. Siga estas instruções:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Acesse: https://github.com/new" -ForegroundColor Cyan
    Write-Host "2. Crie um novo repositório com o nome: $repoName" -ForegroundColor Cyan
    Write-Host "3. NÃO inicialize com README, .gitignore ou licença" -ForegroundColor Cyan
    Write-Host "4. Depois execute os seguintes comandos:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   git remote add origin https://github.com/$username/$repoName.git" -ForegroundColor White
    Write-Host "   git branch -M main" -ForegroundColor White
    Write-Host "   git push -u origin main" -ForegroundColor White
    Write-Host ""
    
    $continue = Read-Host "Já criou o repositório no GitHub? (s/n)"
    if ($continue -eq "s" -or $continue -eq "S") {
        Write-Host ""
        Write-Host "Adicionando remote e fazendo push..." -ForegroundColor Green
        
        # Renomear branch para main (padrão do GitHub)
        git branch -M main
        
        # Adicionar remote
        git remote add origin "https://github.com/$username/$repoName.git"
        
        # Fazer push
        Write-Host "Fazendo push para o GitHub..." -ForegroundColor Green
        git push -u origin main
        
        Write-Host ""
        Write-Host "✅ Repositório enviado com sucesso!" -ForegroundColor Green
        Write-Host "URL: https://github.com/$username/$repoName" -ForegroundColor Cyan
    } else {
        Write-Host "Execute este script novamente após criar o repositório." -ForegroundColor Yellow
    }
}

