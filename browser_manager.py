"""
Gerenciador de múltiplas abas/contextos do navegador
"""
import logging
import asyncio
import os
import json
import re
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from bot import BBBVoteBot

logger = logging.getLogger(__name__)


class BrowserManager:
    """Gerencia múltiplas instâncias do navegador para votação paralela"""
    
    def __init__(self, num_tabs: int, vote_url: str, participant_name: str, 
                 headless: bool = False, captcha_timeout: int = 300,
                 captcha_mode: str = 'manual', max_votes_per_tab: int = -1, 
                 delay_min: int = 2, delay_max: int = 5,
                 storage_state_path: str = "auth_cache.json"):
        """
        Args:
            num_tabs: Número de abas simultâneas
            vote_url: URL da página de votação
            participant_name: Nome do participante para votar
            headless: Se True, executa em modo headless
            captcha_timeout: Timeout para resolução do captcha
            captcha_mode: Modo de resolução do captcha ('auto' ou 'manual')
            max_votes_per_tab: Número máximo de votos por aba (-1 para infinito)
            delay_min: Delay mínimo entre votos
            delay_max: Delay máximo entre votos
            storage_state_path: Caminho para arquivo de cache de autenticação
        """
        self.num_tabs = num_tabs
        self.vote_url = vote_url
        self.participant_name = participant_name
        self.headless = headless
        self.captcha_timeout = captcha_timeout
        self.captcha_mode = captcha_mode
        self.max_votes_per_tab = max_votes_per_tab
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.storage_state_path = storage_state_path
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None  # Contexto compartilhado
        self.pages: List[Page] = []
        self.bots: List[BBBVoteBot] = []
        
        # Contador global de votos (soma de todas as abas)
        self.vote_counter_path = "vote_counter.json"
        self.vote_stats_path = "votos_estatisticas.json"  # Arquivo intuitivo com estatísticas
        self.total_votes = self._load_vote_counter()
        self.vote_lock = None  # Será inicializado quando necessário
        # Inicialização da sessão será feita em start_voting()
        self.session_start_time = None
        self.session_start_votes = 0
        # Mapeamento de bot -> task para monitoramento e recuperação
        self.bot_tasks_map = {}
        
        # Sistema de pausa (DESATIVADO)
        # self.is_paused = False
        # self.pause_lock = asyncio.Lock()
        # self.pause_reason = None
        
        # URL esperada da página de votação (usada para verificação)
        self.expected_vote_url = vote_url  # Usa a URL do config
        
        # Sistema de múltiplas contas Google
        self.accounts_index_path = "google_accounts.json"
        self.accounts_dir = "google_accounts"
        self.current_account_email = None
        self.selected_account = None  # Conta selecionada pelo usuário ao iniciar
        self._ensure_accounts_dir()
    
    def _load_vote_counter(self) -> int:
        """
        Carrega o contador de votos do arquivo JSON
        
        Returns:
            Número total de votos salvos, ou 0 se arquivo não existe
        """
        try:
            if os.path.exists(self.vote_counter_path):
                with open(self.vote_counter_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    total = data.get('total_votes', 0)
                    logger.info(f"Contador de votos carregado: {total} votos")
                    return total
        except Exception as e:
            logger.warning(f"Erro ao carregar contador de votos: {e}")
        return 0
    
    def _save_vote_counter(self):
        """
        Salva o contador de votos em arquivo JSON (compatibilidade)
        """
        try:
            data = {
                'total_votes': self.total_votes,
                'last_updated': datetime.now().isoformat(),
                'votes_per_tab': [bot.vote_count for bot in self.bots] if self.bots else []
            }
            with open(self.vote_counter_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f"Contador de votos salvo: {self.total_votes} votos")
        except Exception as e:
            logger.error(f"Erro ao salvar contador de votos: {e}")
    
    def _load_vote_stats(self) -> dict:
        """
        Carrega estatísticas de votos do arquivo intuitivo
        
        Returns:
            Dicionário com estatísticas de votos
        """
        try:
            if os.path.exists(self.vote_stats_path):
                with open(self.vote_stats_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao carregar estatísticas de votos: {e}")
        return {
            'total_historico': 0,
            'sessoes': [],
            'ultima_atualizacao': None
        }
    
    def _save_vote_stats(self):
        """
        Salva estatísticas de votos em arquivo JSON intuitivo e bem formatado
        """
        try:
            # Carrega estatísticas existentes
            stats = self._load_vote_stats()
            
            # Calcula votos da sessão atual
            votes_per_tab = [bot.vote_count for bot in self.bots] if self.bots else []
            session_votes = sum(votes_per_tab)
            session_start_votes = getattr(self, 'session_start_votes', 0)
            votes_this_session = self.total_votes - session_start_votes
            
            # Atualiza total histórico (sempre usa o maior valor)
            stats['total_historico'] = max(stats.get('total_historico', 0), self.total_votes)
            
            # Adiciona sessão atual (se houver votos e sessão foi inicializada)
            if (votes_this_session > 0 or session_votes > 0) and self.session_start_time:
                session_info = {
                    'data_inicio': self.session_start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'data_fim': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'votos_na_sessao': votes_this_session,
                    'votos_por_aba': votes_per_tab,
                    'total_ao_final': self.total_votes,
                    'participante': self.participant_name,
                    'numero_abas': len(votes_per_tab) if votes_per_tab else 0
                }
                
                # Adiciona à lista de sessões (mantém últimas 100 sessões)
                sessions = stats.get('sessoes', [])
                # Verifica se já existe uma sessão com a mesma data de início (evita duplicatas)
                session_exists = any(
                    s.get('data_inicio') == session_info['data_inicio'] 
                    for s in sessions
                )
                if not session_exists:
                    sessions.append(session_info)
                else:
                    # Atualiza sessão existente
                    for i, s in enumerate(sessions):
                        if s.get('data_inicio') == session_info['data_inicio']:
                            sessions[i] = session_info
                            break
                
                # Mantém apenas as últimas 100 sessões
                if len(sessions) > 100:
                    sessions = sessions[-100:]
                stats['sessoes'] = sessions
            
            # Atualiza última atualização
            stats['ultima_atualizacao'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Estatísticas gerais
            stats['estatisticas_gerais'] = {
                'total_votos_historico': stats['total_historico'],
                'total_sessoes': len(stats.get('sessoes', [])),
                'votos_na_sessao_atual': votes_this_session,
                'votos_por_aba_atual': votes_per_tab,
                'total_votos_atual': self.total_votes
            }
            
            # Salva arquivo bem formatado e intuitivo
            with open(self.vote_stats_path, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Estatísticas de votos salvas: {self.total_votes} votos totais")
        except Exception as e:
            logger.error(f"Erro ao salvar estatísticas de votos: {e}")
    
    def _ensure_accounts_dir(self):
        """Cria diretório para contas Google se não existir"""
        try:
            os.makedirs(self.accounts_dir, exist_ok=True)
        except Exception as e:
            logger.error(f"Erro ao criar diretório de contas: {e}")
    
    def _get_account_filename(self, email: str) -> str:
        """
        Gera nome de arquivo seguro para a conta
        
        Args:
            email: Email da conta
            
        Returns:
            Nome do arquivo
        """
        # Remove caracteres especiais do email para nome de arquivo
        safe_email = email.replace('@', '_at_').replace('.', '_')
        return os.path.join(self.accounts_dir, f"{safe_email}.json")
    
    def _load_accounts_index(self) -> dict:
        """
        Carrega índice de contas salvas
        
        Returns:
            Dicionário com informações das contas
        """
        try:
            if os.path.exists(self.accounts_index_path):
                with open(self.accounts_index_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"Erro ao carregar índice de contas: {e}")
        return {'accounts': []}
    
    def _save_accounts_index(self, accounts_data: dict):
        """
        Salva índice de contas
        
        Args:
            accounts_data: Dicionário com informações das contas
        """
        try:
            with open(self.accounts_index_path, 'w', encoding='utf-8') as f:
                json.dump(accounts_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Erro ao salvar índice de contas: {e}")
    
    async def _detect_account_email(self) -> Optional[str]:
        """
        Detecta o email da conta Google logada
        
        Returns:
            Email da conta ou None se não encontrado
        """
        try:
            if not self.pages or not self.context:
                return None
            
            page = self.pages[0]
            
            # Tenta detectar email de várias formas
            # 1. Verifica cookies do Google
            try:
                cookies = await self.context.cookies()
                for cookie in cookies:
                    # Cookies do Google geralmente contêm email
                    if 'email' in cookie['name'].lower() or 'user' in cookie['name'].lower():
                        value = cookie.get('value', '')
                        if '@' in value and '.' in value:
                            # Extrai email do cookie
                            parts = value.split('@')
                            if len(parts) == 2:
                                email = value
                                logger.info(f"Email detectado via cookie: {email}")
                                return email
            except Exception as e:
                logger.debug(f"Erro ao verificar cookies para email: {e}")
            
            # 2. Verifica localStorage
            try:
                storage = await page.evaluate("""() => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }""")
                
                # Procura por email no localStorage
                for key, value in storage.items():
                    if isinstance(value, str) and '@' in value and '.' in value:
                        # Verifica se parece um email
                        parts = value.split('@')
                        if len(parts) == 2 and '.' in parts[1]:
                            email = value
                            logger.info(f"Email detectado via localStorage: {email}")
                            return email
            except Exception as e:
                logger.debug(f"Erro ao verificar localStorage para email: {e}")
            
            # 3. Tenta encontrar na página (se estiver na página do Google)
            try:
                # Procura por elementos que podem conter email
                email_selectors = [
                    '[data-email]',
                    '[data-user-email]',
                    '.email',
                    '[class*="email"]',
                    '[id*="email"]',
                    # Seletores específicos da página de seleção do Google
                    'div[data-identifier]',
                    '[aria-label*="@"]',
                    'span[dir="ltr"]'  # Google usa isso para emails
                ]
                
                for selector in email_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for elem in elements:
                            # Tenta obter email de atributos
                            email_attr = await elem.get_attribute('data-email') or await elem.get_attribute('data-identifier')
                            if email_attr and '@' in email_attr:
                                parts = email_attr.split('@')
                                if len(parts) == 2 and '.' in parts[1]:
                                    email = email_attr.strip()
                                    logger.info(f"Email detectado via atributo: {email}")
                                    return email
                            
                            # Tenta obter do texto
                            text = await elem.inner_text()
                            if '@' in text and '.' in text:
                                # Extrai email do texto (pode ter outros caracteres)
                                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
                                if email_match:
                                    email = email_match.group(1)
                                    logger.info(f"Email detectado via texto: {email}")
                                    return email
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Erro ao verificar elementos da página para email: {e}")
            
            # 4. Verifica URL atual (pode conter email)
            try:
                current_url = page.url
                if '@' in current_url:
                    # Tenta extrair email da URL
                    import re
                    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', current_url)
                    if email_match:
                        email = email_match.group(1)
                        logger.info(f"Email detectado via URL: {email}")
                        return email
            except Exception as e:
                logger.debug(f"Erro ao verificar URL para email: {e}")
            
            return None
        except Exception as e:
            logger.error(f"Erro ao detectar email da conta: {e}")
            return None
    
    # Sistema de pausa DESATIVADO
    # async def pause(self, reason: str = "manual"):
    #     """Pausa o bot - DESATIVADO"""
    #     pass
    # 
    # async def resume(self):
    #     """Despausa o bot - DESATIVADO"""
    #     pass
    
    async def _recover_stopped_tabs(self):
        """
        Detecta e recupera abas que pararam de votar mas estão na página correta
        Reinicia o loop de votação se a task terminou ou está travada
        """
        try:
            if not self.context or not self.bots:
                return
            
            # Verifica cada bot e sua task
            for bot in self.bots:
                try:
                    page = bot.page
                    current_url = page.url.lower()
                    
                    # Verifica se está na página de votação
                    if self.expected_vote_url in current_url:
                        # Verifica se a task do bot ainda está rodando
                        task = self.bot_tasks_map.get(bot)
                        if task:
                            # Se a task terminou (done), reinicia
                            if task.done():
                                logger.warning(f"⚠ Aba {bot.tab_number} parou de votar! Reiniciando loop...")
                                try:
                                    # Cancela task antiga se ainda não foi coletada
                                    if not task.cancelled():
                                        task.cancel()
                                    
                                    # Cria nova task
                                    new_task = asyncio.create_task(
                                        bot.run_vote_loop(max_votes=self.max_votes_per_tab)
                                    )
                                    self.bot_tasks_map[bot] = new_task
                                    logger.info(f"✓ Loop de votação reiniciado para aba {bot.tab_number}")
                                    
                                    print(f"\n{'='*60}")
                                    print(f"🔄 ABA {bot.tab_number} RECUPERADA!")
                                    print(f"  Loop de votação reiniciado automaticamente")
                                    print(f"{'='*60}\n")
                                except Exception as e:
                                    logger.error(f"Erro ao reiniciar loop da aba {bot.tab_number}: {e}")
                        
                        # Verifica se a página está responsiva
                        try:
                            await page.evaluate("document.readyState", timeout=5000)
                        except:
                            logger.warning(f"Aba {bot.tab_number} parece estar travada. Tentando recarregar...")
                            try:
                                await page.reload(wait_until='domcontentloaded', timeout=30000)
                                await asyncio.sleep(2)
                                logger.info(f"✓ Aba {bot.tab_number} recarregada")
                            except Exception as e:
                                logger.debug(f"Erro ao recarregar aba {bot.tab_number}: {e}")
                        
                except Exception as e:
                    logger.debug(f"Erro ao verificar aba {bot.tab_number}: {e}")
        except Exception as e:
            logger.error(f"Erro ao recuperar abas paradas: {e}")
    
    async def _detect_and_add_new_tabs(self):
        """
        Detecta novas abas abertas manualmente e cria bots para elas
        """
        try:
            if not self.context:
                return
            
            # Obtém todas as páginas do contexto
            all_pages = self.context.pages
            
            # Encontra páginas que não estão na lista de páginas gerenciadas
            managed_pages = set(self.pages)
            new_pages = [p for p in all_pages if p not in managed_pages]
            
            for new_page in new_pages:
                try:
                    # Verifica se está na página de votação
                    current_url = new_page.url.lower()
                    if self.expected_vote_url in current_url:
                        # Nova aba detectada na página de votação!
                        new_tab_number = len(self.bots) + 1
                        logger.info(f"🆕 Nova aba detectada na página de votação! Criando bot para aba {new_tab_number}...")
                        
                        # Adiciona à lista de páginas
                        self.pages.append(new_page)
                        
                        # Cria bot para esta nova aba
                        bot = BBBVoteBot(
                            page=new_page,
                            participant_name=self.participant_name,
                            captcha_timeout=self.captcha_timeout,
                            captcha_mode=self.captcha_mode,
                            delay_min=self.delay_min,
                            delay_max=self.delay_max,
                            vote_callback=self._on_vote_completed,
                            tab_number=new_tab_number,
                            browser_manager=self
                        )
                        self.bots.append(bot)
                        
                        # Inicia o loop de votação para esta nova aba
                        logger.info(f"✓ Bot criado para nova aba {new_tab_number}. Iniciando votação...")
                        task = asyncio.create_task(bot.run_vote_loop(max_votes=self.max_votes_per_tab))
                        
                        # Adiciona ao mapeamento de tasks
                        if not hasattr(self, 'bot_tasks_map'):
                            self.bot_tasks_map = {}
                        self.bot_tasks_map[bot] = task
                        
                        print(f"\n{'='*60}")
                        print(f"🆕 NOVA ABA DETECTADA E ADICIONADA!")
                        print(f"  Aba número: {new_tab_number}")
                        print(f"  Total de abas ativas: {len(self.bots)}")
                        print(f"{'='*60}\n")
                    else:
                        # Está em outra página, aguarda ou navega para página de votação
                        logger.debug(f"Nova aba detectada mas não está na página de votação. URL: {new_page.url[:60]}...")
                        # Opcional: navega automaticamente para página de votação
                        try:
                            await new_page.goto(self.vote_url, wait_until='domcontentloaded', timeout=30000)
                            await asyncio.sleep(2)
                            # Tenta adicionar novamente após navegar
                            if self.expected_vote_url in new_page.url.lower():
                                await self._detect_and_add_new_tabs()  # Recursivo para adicionar esta aba
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"Erro ao processar nova aba: {e}")
        except Exception as e:
            logger.error(f"Erro ao detectar novas abas: {e}")
    
    async def check_all_tabs_on_vote_page(self) -> bool:
        """
        Verifica se todas as abas estão na página de votação correta
        (não em páginas de login)
        
        Returns:
            True se todas as abas estão na URL correta, False caso contrário
        """
        try:
            if not self.pages:
                return False
            
            # URL base para comparação (sem parâmetros de query)
            expected_base = self.expected_vote_url.split('?')[0]
            
            # Indicadores de páginas de login
            login_indicators = [
                "authx.globoid.globo.com",
                "accounts.google.com",
                "goidc.globo.com",
                "/login",
                "login-callback"
            ]
            
            # Verifica todas as abas
            for i, page in enumerate(self.pages):
                try:
                    current_url = page.url
                    current_url_lower = current_url.lower()
                    current_base = current_url.split('?')[0]
                    
                    # Verifica se está em página de login
                    for login_indicator in login_indicators:
                        if login_indicator.lower() in current_url_lower:
                            logger.debug(f"Aba {i+1} está em página de login: {login_indicator}")
                            return False
                    
                    # Verifica se a URL base corresponde à página de votação
                    if expected_base not in current_base and current_base not in expected_base:
                        logger.debug(f"Aba {i+1} não está na página de votação.")
                        logger.debug(f"  Esperado: {expected_base[:60]}...")
                        logger.debug(f"  Atual: {current_base[:60]}...")
                        return False
                except Exception as e:
                    logger.debug(f"Erro ao verificar URL da aba {i+1}: {e}")
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Erro ao verificar páginas: {e}")
            return False
    
    async def initialize(self):
        """Inicializa o navegador e cria as abas com contexto compartilhado"""
        try:
            self.playwright = await async_playwright().start()
            
            # Inicia o navegador (Chromium)
            logger.info(f"Iniciando navegador (headless={self.headless})...")
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']  # Tenta evitar detecção
            )
            
            # Tenta carregar estado de autenticação salvo
            storage_state = None
            
            # Se uma conta específica foi selecionada, tenta carregá-la
            if self.selected_account:
                account_file = self._get_account_filename(self.selected_account)
                if os.path.exists(account_file):
                    storage_state = account_file
                    self.current_account_email = self.selected_account
                    logger.info(f"Carregando conta selecionada: {self.current_account_email}")
                else:
                    logger.warning(f"Arquivo da conta selecionada não encontrado: {account_file}")
                    self.selected_account = None  # Reseta se arquivo não existe
            
            # Se não há conta selecionada, tenta carregar arquivo padrão ou conta mais recente
            if not storage_state:
                # Primeiro verifica contas salvas (prioridade)
                saved_accounts = self.list_saved_accounts()
                if saved_accounts:
                    # Carrega a conta mais recente (última logada)
                    most_recent = max(saved_accounts, key=lambda x: x.get('last_used', ''))
                    account_file = most_recent.get('file')
                    if account_file and os.path.exists(account_file):
                        storage_state = account_file
                        self.current_account_email = most_recent.get('email')
                        logger.info(f"✓ Carregando última conta logada automaticamente: {self.current_account_email}")
                        print(f"\n{'='*60}")
                        print(f"✓ ÚLTIMA CONTA LOGADA CARREGADA")
                        print(f"  Email: {self.current_account_email}")
                        print(f"{'='*60}\n")
                    else:
                        logger.warning(f"Arquivo da conta mais recente não encontrado: {account_file}")
                
                # Fallback: tenta arquivo padrão se não encontrou contas salvas
                if not storage_state and os.path.exists(self.storage_state_path):
                    try:
                        storage_state = self.storage_state_path
                        logger.info(f"Carregando autenticação salva de {self.storage_state_path}")
                    except Exception as e:
                        logger.warning(f"Erro ao carregar autenticação salva: {e}")
                        storage_state = None
                
                if not storage_state:
                    logger.info("Nenhuma autenticação salva encontrada. Será necessário fazer login.")
            
            # Cria um ÚNICO contexto compartilhado para todas as abas
            # Isso permite que cookies e sessão sejam compartilhados entre todas as abas
            logger.info("Criando contexto compartilhado...")
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                storage_state=storage_state  # Carrega autenticação salva se existir
            )
            
            # Cria múltiplas páginas (abas) no mesmo contexto
            logger.info(f"Criando {self.num_tabs} abas no contexto compartilhado...")
            for i in range(self.num_tabs):
                page = await self.context.new_page()
                self.pages.append(page)
                
                # Cria bot para esta página
                bot = BBBVoteBot(
                    page=page,
                    participant_name=self.participant_name,
                    captcha_timeout=self.captcha_timeout,
                    captcha_mode=self.captcha_mode,
                    delay_min=self.delay_min,
                    delay_max=self.delay_max,
                    vote_callback=self._on_vote_completed,  # Callback para contador global
                    tab_number=i+1,  # Número da aba (1-indexed)
                    browser_manager=self  # Passa referência para verificar pausa
                )
                self.bots.append(bot)
                
                logger.info(f"Aba {i+1}/{self.num_tabs} criada")
            
            logger.info("Navegador inicializado com sucesso - todas as abas compartilham a mesma sessão")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar navegador: {e}")
            raise
    
    async def start_voting(self):
        """Inicia o processo de votação em todas as abas em paralelo"""
        if not self.browser:
            await self.initialize()
        
        # Inicializa estatísticas da sessão
        self.session_start_time = datetime.now()
        self.session_start_votes = self.total_votes
        logger.info(f"Iniciando nova sessão. Votos no início: {self.session_start_votes}")
        
        # Navega para a URL em todas as abas
        logger.info(f"Navegando para {self.vote_url} em todas as abas...")
        navigation_tasks = [page.goto(self.vote_url, wait_until='domcontentloaded', timeout=60000) for page in self.pages]
        await asyncio.gather(*navigation_tasks, return_exceptions=True)
        
        # Aguarda um pouco para páginas carregarem
        await asyncio.sleep(3)
        
        # Verifica se todas as abas estão na página correta
        logger.info("Verificando se todas as abas estão na página de votação...")
        max_retries = 10
        retry_count = 0
        
        while retry_count < max_retries:
            if await self.check_all_tabs_on_vote_page():
                logger.info("✓ Todas as abas estão na página de votação!")
                break
            else:
                retry_count += 1
                logger.warning(f"Algumas abas não estão na página correta. Tentativa {retry_count}/{max_retries}")
                # Tenta navegar novamente para as abas que não estão corretas
                for i, page in enumerate(self.pages):
                    try:
                        current_url = page.url
                        if self.expected_vote_url not in current_url:
                            logger.info(f"Recarregando aba {i+1}...")
                            await page.goto(self.vote_url, wait_until='domcontentloaded', timeout=30000)
                    except Exception as e:
                        logger.debug(f"Erro ao recarregar aba {i+1}: {e}")
                await asyncio.sleep(2)
        
        if not await self.check_all_tabs_on_vote_page():
            logger.error("⚠ Nem todas as abas estão na página de votação após tentativas. Continuando de qualquer forma...")
        else:
            logger.info("✓ Todas as abas confirmadas na página de votação!")
        
        # Verifica se já está autenticado
        is_authenticated = await self._check_authentication()
        
        if not is_authenticated:
            logger.info("=" * 60)
            logger.info("IMPORTANTE: Autentique-se na primeira aba!")
            logger.info("Todas as abas compartilham a mesma sessão de autenticação.")
            logger.info("A autenticação será salva automaticamente quando detectada.")
            logger.info("Aguardando até 60 segundos para você autenticar...")
            logger.info("=" * 60)
            
            # Verifica periodicamente se o login foi feito
            max_wait_time = 60  # 60 segundos
            check_interval = 2  # Verifica a cada 2 segundos
            waited_time = 0
            
            while waited_time < max_wait_time:
                await asyncio.sleep(check_interval)
                waited_time += check_interval
                
                is_authenticated = await self._check_authentication()
                if is_authenticated:
                    # Detecta email e salva conta
                    account_email = await self._detect_account_email()
                    await self.save_auth_cache(account_email)
                    logger.info("✓ Login detectado! Conta Google salva com sucesso!")
                    break
                else:
                    if waited_time % 10 == 0:  # Avisa a cada 10 segundos
                        remaining = max_wait_time - waited_time
                        logger.info(f"Aguardando autenticação... ({remaining}s restantes)")
            
            # Verifica uma última vez
            if not is_authenticated:
                is_authenticated = await self._check_authentication()
                if is_authenticated:
                    account_email = await self._detect_account_email()
                    await self.save_auth_cache(account_email)
                    logger.info("✓ Login detectado! Conta Google salva com sucesso!")
                else:
                    logger.warning("Login não detectado. Continuando sem autenticação salva.")
        else:
            # Detecta qual conta está sendo usada
            account_email = await self._detect_account_email()
            if account_email:
                logger.info(f"✓ Autenticação encontrada! Conta: {account_email}")
                # Salva/atualiza a conta atual
                await self.save_auth_cache(account_email)
            else:
                logger.info("✓ Autenticação encontrada! Usando sessão salva.")
        
        # Inicia loops de votação em paralelo
        logger.info("Iniciando loops de votação em paralelo...")
        print(f"\n{'='*60}")
        print(f"BBB VOTE BOT INICIADO")
        print(f"Contador de votos inicializado. Total: {self.total_votes}")
        print(f"Numero de abas: {self.num_tabs}")
        print(f"Bot só votará se todas as abas estiverem na página de votação")
        print(f"{'='*60}\n")
        # Armazena mapeamento de bot -> task para monitoramento
        self.bot_tasks_map = {}  # Mapeia bot -> task para poder reiniciar se necessário
        
        # Cria tasks de votação para cada bot
        vote_tasks = []
        for bot in self.bots:
            task = asyncio.create_task(bot.run_vote_loop(max_votes=self.max_votes_per_tab))
            vote_tasks.append(task)
            self.bot_tasks_map[bot] = task
        
        # Tarefa para verificar se todas as abas estão na página correta e detectar novas abas (a cada 30 segundos)
        async def periodic_url_check():
            while True:
                await asyncio.sleep(30)  # 30 segundos
                try:
                    # 1. Verifica e recupera abas paradas
                    await self._recover_stopped_tabs()
                    
                    # 2. Detecta e adiciona novas abas
                    await self._detect_and_add_new_tabs()
                    
                    # 3. Verifica se todas as abas estão na página correta
                    if not await self.check_all_tabs_on_vote_page():
                        logger.warning("⚠ Algumas abas não estão na página de votação!")
                        # Tenta corrigir navegando novamente
                        for i, page in enumerate(self.pages):
                            try:
                                current_url = page.url
                                if self.expected_vote_url not in current_url:
                                    logger.info(f"Recarregando aba {i+1} para página de votação...")
                                    await page.goto(self.vote_url, wait_until='domcontentloaded', timeout=30000)
                                    await asyncio.sleep(1)
                            except Exception as e:
                                logger.debug(f"Erro ao recarregar aba {i+1}: {e}")
                except Exception as e:
                    logger.error(f"Erro no monitoramento periódico: {e}")
        
        # Tarefa para salvar autenticação periodicamente (a cada 2 minutos)
        async def periodic_auth_save():
            while True:
                await asyncio.sleep(120)  # 2 minutos - salva mais frequentemente
                if await self._check_authentication():
                    account_email = await self._detect_account_email()
                    if account_email:
                        await self.save_auth_cache(account_email)
                        logger.debug(f"Conta Google salva periodicamente: {account_email}")
                    else:
                        # Tenta salvar mesmo sem detectar email
                        await self.save_auth_cache()
                        logger.debug("Sessão salva periodicamente (email não detectado)")
        
        # Tarefa para exibir estatísticas periodicamente (a cada 20 segundos)
        async def periodic_stats():
            while True:
                await asyncio.sleep(20)  # 20 segundos
                await self._log_statistics()
        
        url_check_task = asyncio.create_task(periodic_url_check())
        save_task = asyncio.create_task(periodic_auth_save())
        stats_task = asyncio.create_task(periodic_stats())
        
        try:
            await asyncio.gather(*vote_tasks, return_exceptions=True)
        except KeyboardInterrupt:
            logger.info("Interrupção recebida. Finalizando...")
        except Exception as e:
            logger.error(f"Erro durante votação: {e}", exc_info=True)
        finally:
            url_check_task.cancel()
            save_task.cancel()
            stats_task.cancel()
            try:
                await url_check_task
                await save_task
                await stats_task
            except asyncio.CancelledError:
                pass
            # Exibe estatísticas finais
            await self._log_statistics()
    
    async def save_auth_cache(self, account_email: Optional[str] = None):
        """
        Salva o estado de autenticação (cookies, localStorage) em arquivo
        Se account_email não for fornecido, tenta detectar automaticamente
        
        Args:
            account_email: Email da conta (opcional, será detectado se não fornecido)
        """
        try:
            if not self.context:
                return False
            
            # Detecta email se não fornecido
            if not account_email:
                account_email = await self._detect_account_email()
            
            if account_email:
                # Salva em arquivo específico da conta
                account_file = self._get_account_filename(account_email)
                await self.context.storage_state(path=account_file)
                
                # Atualiza índice de contas
                accounts_index = self._load_accounts_index()
                account_info = {
                    'email': account_email,
                    'last_used': datetime.now().isoformat(),
                    'file': account_file
                }
                
                # Verifica se conta já existe no índice
                account_exists = False
                for i, acc in enumerate(accounts_index.get('accounts', [])):
                    if acc.get('email') == account_email:
                        accounts_index['accounts'][i] = account_info
                        account_exists = True
                        break
                
                if not account_exists:
                    accounts_index.setdefault('accounts', []).append(account_info)
                
                self._save_accounts_index(accounts_index)
                self.current_account_email = account_email
                
                logger.info(f"✓ Conta Google salva permanentemente: {account_email}")
                logger.info(f"  Arquivo: {account_file}")
                logger.info(f"  Total de contas salvas: {len(accounts_index.get('accounts', []))}")
                
                # Só mostra mensagem destacada na primeira vez ou quando é nova conta
                if not account_exists:
                    print(f"\n{'='*60}")
                    print(f"✓ NOVA CONTA GOOGLE SALVA: {account_email}")
                    print(f"  Total de contas salvas: {len(accounts_index.get('accounts', []))}")
                    print(f"  Esta conta estará disponível na próxima execução!")
                    print(f"{'='*60}\n")
                
                return True
            else:
                # Fallback: salva no arquivo padrão se não conseguir detectar email
                await self.context.storage_state(path=self.storage_state_path)
                logger.warning(f"Email não detectado, salvando em {self.storage_state_path}")
                return True
        except Exception as e:
            logger.error(f"Erro ao salvar autenticação: {e}")
            return False
    
    async def load_account(self, account_email: str) -> bool:
        """
        Carrega uma conta Google específica
        
        Args:
            account_email: Email da conta a carregar
            
        Returns:
            True se conta foi carregada com sucesso
        """
        try:
            account_file = self._get_account_filename(account_email)
            
            if not os.path.exists(account_file):
                logger.error(f"Arquivo de conta não encontrado: {account_file}")
                return False
            
            # Se o contexto já existe, fecha e recria com a nova conta
            if self.context:
                await self.context.close()
            
            # Cria novo contexto com a conta salva
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                storage_state=account_file
            )
            
            # Recria as páginas no novo contexto
            self.pages = []
            for i in range(self.num_tabs):
                page = await self.context.new_page()
                self.pages.append(page)
            
            # Atualiza referência do browser_manager nos bots
            for bot in self.bots:
                bot.page = self.pages[bot.tab_number - 1]
            
            self.current_account_email = account_email
            logger.info(f"✓ Conta carregada: {account_email}")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar conta: {e}")
            return False
    
    def list_saved_accounts(self) -> List[dict]:
        """
        Lista todas as contas Google salvas
        
        Returns:
            Lista de dicionários com informações das contas
        """
        accounts_index = self._load_accounts_index()
        return accounts_index.get('accounts', [])
    
    async def _check_authentication(self) -> bool:
        """Verifica se o usuário está autenticado"""
        try:
            if not self.pages or not self.context:
                return False
            
            page = self.pages[0]
            
            # 1. Verifica cookies de autenticação
            try:
                cookies = await self.context.cookies()
                auth_cookies = ['glbid', 'glbId', 'GLBID', 'session', 'auth', 'token', 'user', 'login', 'account']
                for cookie in cookies:
                    cookie_name_lower = cookie['name'].lower()
                    if any(auth_name in cookie_name_lower for auth_name in auth_cookies):
                        logger.debug(f"Cookie de autenticação encontrado: {cookie['name']}")
                        return True
            except Exception as e:
                logger.debug(f"Erro ao verificar cookies: {e}")
            
            # 2. Verifica localStorage para tokens de autenticação
            try:
                storage = await page.evaluate("""() => {
                    const items = {};
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        items[key] = localStorage.getItem(key);
                    }
                    return items;
                }""")
                
                # Procura por chaves que indicam autenticação
                auth_keys = ['token', 'auth', 'user', 'login', 'session', 'glb']
                if isinstance(storage, dict):
                    for key, value in storage.items():
                        key_lower = key.lower()
                        if any(auth_key in key_lower for auth_key in auth_keys) and value:
                            logger.debug(f"Token de autenticação encontrado no localStorage: {key}")
                            return True
            except Exception as e:
                logger.debug(f"Erro ao verificar localStorage: {e}")
            
            # 3. Verifica elementos na página que indicam login
            try:
                # Procura por botões de logout, nome de usuário, ou elementos que só aparecem quando logado
                selectors = [
                    'button[aria-label*="sair"]',
                    'button[aria-label*="Sair"]',
                    'button[aria-label*="logout"]',
                    '[class*="user"]',
                    '[class*="profile"]',
                    '[id*="user"]',
                    '[id*="profile"]'
                ]
                
                for selector in selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element and await element.is_visible():
                            logger.debug(f"Elemento de usuário logado encontrado: {selector}")
                            return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Erro ao verificar elementos de página: {e}")
            
            # 4. Verifica texto na página que indica login
            try:
                page_content = await page.content()
                page_text = await page.inner_text('body')
                page_text_lower = page_text.lower()
                
                # Padrões que indicam usuário logado
                auth_indicators = [
                    'olá,', 'olá ', 'bem-vindo', 'bem vindo',
                    'sair', 'logout', 'minha conta', 'perfil',
                    'você está logado', 'logado como'
                ]
                
                for indicator in auth_indicators:
                    if indicator in page_text_lower:
                        logger.debug(f"Indicador de autenticação encontrado: '{indicator}'")
                        return True
            except Exception as e:
                logger.debug(f"Erro ao verificar texto da página: {e}")
            
            return False
        except Exception as e:
            logger.debug(f"Erro ao verificar autenticação: {e}")
            return False
    
    async def _on_vote_completed(self, tab_number: int):
        """
        Callback chamado quando um voto é completado (quando aparece "Votar Novamente")
        
        Args:
            tab_number: Número da aba que completou o voto
        """
        # Inicializa o lock se ainda não foi inicializado
        if self.vote_lock is None:
            self.vote_lock = asyncio.Lock()
        
        async with self.vote_lock:
            # Obtém os votos por aba (já incrementado no bot)
            votes_per_tab = [bot.vote_count for bot in self.bots]
            
            # Calcula o total baseado na soma das abas (fonte única da verdade)
            calculated_total = sum(votes_per_tab)
            
            # Atualiza total_votes com a soma real das abas (não incrementa diretamente)
            # Isso garante que total_votes sempre seja igual à soma das abas
            old_total = self.total_votes
            self.total_votes = calculated_total
            
            # Log se houve correção
            if old_total != calculated_total:
                logger.info(f"Contador atualizado: {old_total} → {calculated_total} (soma das abas)")
            
            # Salva contador em arquivo (compatibilidade)
            self._save_vote_counter()
            
            # Salva estatísticas detalhadas (arquivo intuitivo)
            self._save_vote_stats()
            
            # Exibe no terminal de forma destacada
            votes_this_session = self.total_votes - getattr(self, 'session_start_votes', 0)
            print(f"\n{'='*60}")
            print(f"VOTO #{self.total_votes} CONFIRMADO! (Aba {tab_number})")
            print(f"TOTAL HISTÓRICO: {self.total_votes} votos")
            print(f"Votos nesta sessão: {votes_this_session}")
            print(f"Votos por aba: {votes_per_tab}")
            print(f"Soma das abas: {calculated_total} ✓")
            print(f"{'='*60}\n")
            logger.info(f"📊 VOTO #{self.total_votes} confirmado! (Aba {tab_number}) | Total: {self.total_votes} votos | Sessão: {votes_this_session}")
    
    async def _log_statistics(self):
        """Exibe estatísticas de votação"""
        # Inicializa o lock se ainda não foi inicializado
        if self.vote_lock is None:
            self.vote_lock = asyncio.Lock()
        
        async with self.vote_lock:
            votes_per_tab = [bot.vote_count for bot in self.bots]
            calculated_total = sum(votes_per_tab)
            
            # Sincroniza total_votes com a soma real das abas
            if calculated_total != self.total_votes:
                logger.warning(f"Corrigindo contador nas estatísticas: Total estava {self.total_votes}, mas soma das abas é {calculated_total}")
                self.total_votes = calculated_total
                self._save_vote_counter()
            
            # Exibe no terminal de forma destacada
            print(f"\n{'='*60}")
            print(f"ESTATISTICAS DE VOTACAO")
            print(f"   Total de votos: {self.total_votes}")
            print(f"   Votos por aba: {votes_per_tab}")
            print(f"   Soma das abas: {calculated_total} {'✓' if calculated_total == self.total_votes else '⚠'}")
            print(f"   Media por aba: {sum(votes_per_tab) / len(votes_per_tab) if votes_per_tab else 0:.1f}")
            print(f"{'='*60}\n")
            logger.info("=" * 60)
            logger.info(f"📊 ESTATÍSTICAS DE VOTAÇÃO")
            logger.info(f"   Total de votos: {self.total_votes}")
            logger.info(f"   Votos por aba: {votes_per_tab}")
            logger.info(f"   Soma das abas: {calculated_total}")
            logger.info(f"   Média por aba: {sum(votes_per_tab) / len(votes_per_tab) if votes_per_tab else 0:.1f}")
            logger.info("=" * 60)
    
    async def close(self):
        """Fecha o navegador e todas as abas, salvando autenticação antes"""
        try:
            # Salva autenticação antes de fechar (garante que todas as contas estão salvas)
            if self.context:
                account_email = await self._detect_account_email()
                if account_email:
                    await self.save_auth_cache(account_email)
                    logger.info(f"✓ Sessão da conta {account_email} salva permanentemente antes de fechar")
                else:
                    # Tenta salvar mesmo sem detectar email
                    await self.save_auth_cache()
                    logger.info("✓ Sessão salva antes de fechar")
            
            # Salva contador final
            self._save_vote_counter()
            
            # Salva estatísticas finais da sessão
            self._save_vote_stats()
            
            # Exibe estatísticas finais
            await self._log_statistics()
            
            # Exibe resumo da sessão
            votes_this_session = self.total_votes - getattr(self, 'session_start_votes', 0)
            if votes_this_session > 0:
                print(f"\n{'='*60}")
                print(f"RESUMO DA SESSAO")
                print(f"  Votos nesta sessão: {votes_this_session}")
                print(f"  Total histórico: {self.total_votes} votos")
                print(f"  Estatísticas salvas em: {self.vote_stats_path}")
                print(f"{'='*60}\n")
            
            # Lista todas as contas salvas
            saved_accounts = self.list_saved_accounts()
            if saved_accounts:
                print(f"\n{'='*60}")
                print(f"CONTAS SALVAS PERMANENTEMENTE ({len(saved_accounts)}):")
                for account in saved_accounts:
                    email = account.get('email', 'Desconhecido')
                    print(f"  ✓ {email}")
                print(f"{'='*60}")
                print(f"Todas as contas estarão disponíveis na próxima execução!")
                print(f"{'='*60}\n")
            
            # Fecha contexto (se usamos launch_persistent_context, fecha o browser também)
            if self.context:
                logger.info("Fechando contexto do navegador...")
                await self.context.close()
                logger.info("Contexto fechado")
            # Só fecha browser se não usamos launch_persistent_context
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Navegador fechado")
        except Exception as e:
            logger.error(f"Erro ao fechar navegador: {e}")

