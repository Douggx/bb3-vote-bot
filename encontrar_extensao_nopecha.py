"""
Script auxiliar para encontrar o caminho da extensão NopeCHA
"""
import os
from pathlib import Path

def encontrar_nopecha():
    """Encontra o caminho da extensão NopeCHA instalada no Chrome"""
    
    # ID da extensão NopeCHA
    extension_id = "dknlfmjaanfblgfdfebhijalfmhmjjjo"
    
    # Caminhos possíveis no Windows
    local_appdata = os.getenv('LOCALAPPDATA')
    if not local_appdata:
        print("❌ Não foi possível encontrar a pasta AppData")
        return None
    
    # Caminho padrão das extensões do Chrome
    extensions_path = Path(local_appdata) / "Google" / "Chrome" / "User Data" / "Default" / "Extensions" / extension_id
    
    print(f"\n{'='*60}")
    print(f"PROCURANDO EXTENSÃO NOPECHA")
    print(f"{'='*60}\n")
    print(f"Procurando em: {extensions_path}")
    print()
    
    if not extensions_path.exists():
        print(f"❌ Pasta da extensão não encontrada em: {extensions_path}")
        print(f"\nTente instalar a extensão primeiro:")
        print(f"1. Abra o Chrome")
        print(f"2. Vá para: https://chromewebstore.google.com/detail/nopecha-captcha-solver/dknlfmjaanfblgfdfebhijalfmhmjjjo")
        print(f"3. Clique em 'Adicionar ao Chrome'")
        print(f"4. Execute este script novamente")
        return None
    
    # Procura pela versão mais recente
    versions = list(extensions_path.iterdir())
    if not versions:
        print(f"❌ Nenhuma versão encontrada na pasta da extensão")
        return None
    
    # Pega a versão mais recente (geralmente a última pasta)
    latest_version = max(versions, key=lambda p: p.stat().st_mtime if p.is_dir() else 0)
    
    if not latest_version.is_dir():
        print(f"❌ Versão inválida encontrada")
        return None
    
    extension_full_path = latest_version.resolve()
    
    print(f"✓ EXTENSÃO ENCONTRADA!")
    print(f"\nCaminho completo:")
    print(f"  {extension_full_path}")
    print(f"\n{'='*60}")
    print(f"COMO USAR:")
    print(f"{'='*60}")
    print(f"1. Copie o caminho acima")
    print(f"2. Abra o arquivo config.json")
    print(f"3. Adicione a linha 'extension_path' com o caminho:")
    print(f"\n   \"extension_path\": \"{extension_full_path}\",")
    print(f"\n   IMPORTANTE: Use barras duplas (\\\\) no Windows!")
    print(f"   Exemplo correto:")
    print(f"   \"extension_path\": \"{str(extension_full_path).replace(chr(92), chr(92)*2)}\",")
    print(f"\n{'='*60}\n")
    
    return str(extension_full_path)

if __name__ == "__main__":
    caminho = encontrar_nopecha()
    if caminho:
        print(f"\n✅ Caminho encontrado com sucesso!")
        print(f"   {caminho}")
    else:
        print(f"\n❌ Não foi possível encontrar a extensão automaticamente.")
        print(f"   Siga as instruções acima ou consulte INSTALAR_EXTENSAO_NOPECHA.md")

