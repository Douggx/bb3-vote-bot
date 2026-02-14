"""
Script principal do bot de votação BBB
"""
import json
import logging
import asyncio
import sys
import threading
try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    print("AVISO: Biblioteca 'keyboard' não instalada. Pausa manual não funcionará.")
    print("Instale com: pip install keyboard")
from browser_manager import BrowserManager

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bbb_vote_bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)


def load_config(config_path: str = 'config.json') -> dict:
    """
    Carrega configurações do arquivo JSON
    
    Args:
        config_path: Caminho para o arquivo de configuração
        
    Returns:
        Dicionário com as configurações
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Configurações carregadas de {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Arquivo de configuração não encontrado: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Erro ao decodificar JSON: {e}")
        sys.exit(1)


# Sistema de pausa DESATIVADO
# def setup_keyboard_listener(...):
#     pass


async def main():
    """Função principal"""
    logger.info("=" * 50)
    logger.info("BBB Auto Vote Bot - Iniciando")
    logger.info("=" * 50)
    
    # Carrega configurações
    config = load_config()
    
    # Valida configurações obrigatórias
    required_keys = ['participant_name', 'num_tabs', 'vote_url']
    for key in required_keys:
        if key not in config:
            logger.error(f"Configuração obrigatória ausente: {key}")
            sys.exit(1)
    
    # Extrai configurações
    participant_name = config['participant_name']
    num_tabs = config['num_tabs']
    vote_url = config['vote_url']
    headless = config.get('headless', False)
    captcha_timeout = config.get('captcha_timeout', 300)
    captcha_mode = config.get('captcha_mode', 'manual')  # 'auto' ou 'manual'
    max_votes_per_tab = config.get('max_votes_per_tab', -1)
    
    # Configura delay entre votos
    delay_config = config.get('delay_between_votes', {})
    delay_min = delay_config.get('min', 2)
    delay_max = delay_config.get('max', 5)
    
    logger.info(f"Participante: {participant_name}")
    logger.info(f"Número de abas: {num_tabs}")
    logger.info(f"URL: {vote_url}")
    logger.info(f"Headless: {headless}")
    logger.info(f"Timeout captcha: {captcha_timeout}s")
    logger.info(f"Modo captcha: {captcha_mode}")
    logger.info(f"Max votos por aba: {max_votes_per_tab if max_votes_per_tab > 0 else 'infinito'}")
    logger.info(f"Delay entre votos: {delay_min}-{delay_max}s")
    
    # Cria e inicializa o gerenciador de navegador
    browser_manager = BrowserManager(
        num_tabs=num_tabs,
        vote_url=vote_url,
        participant_name=participant_name,
        headless=headless,
        captcha_timeout=captcha_timeout,
        captcha_mode=captcha_mode,
        max_votes_per_tab=max_votes_per_tab,
        delay_min=delay_min,
        delay_max=delay_max
    )
    
    # Lista contas salvas e permite escolher
    saved_accounts = browser_manager.list_saved_accounts()
    selected_account = None
    
    if saved_accounts:
        # Encontra a conta mais recente automaticamente
        most_recent = max(saved_accounts, key=lambda x: x.get('last_used', ''))
        most_recent_email = most_recent.get('email')
        
        print(f"\n{'='*60}")
        print(f"✓ CONTAS GOOGLE SALVAS PERMANENTEMENTE ({len(saved_accounts)})")
        print(f"{'='*60}")
        print(f"Todas as contas abaixo estão salvas e disponíveis:")
        print()
        for i, account in enumerate(saved_accounts, 1):
            email = account.get('email', 'Desconhecido')
            last_used = account.get('last_used', 'Nunca')
            last_used_str = last_used[:10] if len(last_used) > 10 else last_used
            is_most_recent = email == most_recent_email
            marker = " ← ÚLTIMA USADA" if is_most_recent else ""
            print(f"  {i}. {email}{marker}")
            print(f"     Último uso: {last_used_str}")
        print(f"{'='*60}")
        print(f"ESCOLHA UMA OPÇÃO:")
        print(f"  • Digite o número da conta (1-{len(saved_accounts)}) para usar uma conta salva")
        print(f"  • Digite 'n' para fazer login com uma NOVA conta (será salva automaticamente)")
        print(f"  • Digite '0' ou Enter para usar a ÚLTIMA CONTA LOGADA automaticamente")
        print(f"     (Padrão: {most_recent_email})")
        print(f"{'='*60}")
        
        try:
            choice = input("\nSua escolha (Enter para usar última conta): ").strip().lower()
            
            if choice == '0' or choice == '':
                # Usa a conta mais recente (padrão)
                selected_account = most_recent_email
                print(f"\n✓ Usando última conta logada: {selected_account}")
            elif choice.isdigit():
                account_index = int(choice) - 1
                if 0 <= account_index < len(saved_accounts):
                    selected_account = saved_accounts[account_index].get('email')
                    print(f"\n✓ Conta selecionada: {selected_account}")
                else:
                    print(f"\n⚠ Número inválido. Usando última conta logada.")
                    selected_account = most_recent_email
            elif choice == 'n':
                print(f"\n✓ Você fará login com uma nova conta.")
                selected_account = None
            else:
                print(f"\n⚠ Opção inválida. Usando última conta logada.")
                selected_account = most_recent_email
        except (KeyboardInterrupt, EOFError):
            print(f"\n⚠ Entrada cancelada. Usando última conta logada automaticamente.")
            selected_account = most_recent_email
        except Exception as e:
            logger.error(f"Erro ao processar escolha: {e}")
            selected_account = most_recent_email
    else:
        print(f"\n{'='*60}")
        print(f"NENHUMA CONTA SALVA")
        print(f"Faça login e o bot salvará automaticamente sua conta Google.")
        print(f"{'='*60}\n")
        selected_account = None
    
    # Se não foi selecionada nenhuma conta, usa a última logada automaticamente
    if not selected_account and saved_accounts:
        most_recent = max(saved_accounts, key=lambda x: x.get('last_used', ''))
        selected_account = most_recent.get('email')
        logger.info(f"✓ Usando última conta logada automaticamente: {selected_account}")
        print(f"\n{'='*60}")
        print(f"✓ ÚLTIMA CONTA LOGADA SELECIONADA AUTOMATICAMENTE")
        print(f"  Email: {selected_account}")
        print(f"  Esta conta será carregada quando as abas abrirem")
        print(f"{'='*60}\n")
    
    # Armazena a conta selecionada para uso posterior
    browser_manager.selected_account = selected_account
    
    try:
        # Obtém o loop de eventos atual
        loop = asyncio.get_event_loop()
        
        # Sistema de pausa DESATIVADO
        # if KEYBOARD_AVAILABLE:
        #     ...
        
        # Inicia o processo de votação
        await browser_manager.start_voting()
    except KeyboardInterrupt:
        logger.info("\nInterrupção pelo usuário (Ctrl+C)")
    except Exception as e:
        logger.error(f"Erro fatal: {e}", exc_info=True)
    finally:
        # Fecha o navegador
        await browser_manager.close()
        logger.info("Bot finalizado")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Programa interrompido pelo usuário")
    except Exception as e:
        logger.error(f"Erro ao executar programa: {e}", exc_info=True)
        sys.exit(1)

