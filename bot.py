"""
Classe principal do bot de votação BBB
"""
import logging
import asyncio
import random
import time
from playwright.async_api import Page, Browser, BrowserContext
from captcha_handler import CaptchaHandler

logger = logging.getLogger(__name__)


class BBBVoteBot:
    """Bot para automatizar votos no Big Brother Brasil"""
    
    # Estados possíveis da página
    STATE_VOTING = "voting"
    STATE_CONFIRMATION = "confirmation"
    STATE_ERROR = "error"
    STATE_LOGIN_REQUIRED = "login_required"
    STATE_UNKNOWN = "unknown"
    
    def __init__(self, page: Page, participant_name: str, captcha_timeout: int = 300, 
                 captcha_mode: str = 'manual', delay_min: int = 2, delay_max: int = 5, 
                 vote_callback=None, tab_number: int = 0, browser_manager=None):
        """
        Args:
            page: Página do Playwright
            participant_name: Nome do participante para votar
            captcha_timeout: Timeout para resolução do captcha
            captcha_mode: Modo de resolução do captcha ('auto' ou 'manual')
            delay_min: Delay mínimo entre votos (segundos)
            delay_max: Delay máximo entre votos (segundos)
            vote_callback: Função callback chamada quando um voto é completado (recebe tab_number)
            tab_number: Número da aba (para identificação)
            browser_manager: Referência ao BrowserManager para verificar pausa
        """
        self.page = page
        self.participant_name = participant_name
        auto_solve = (captcha_mode == 'auto')
        self.captcha_handler = CaptchaHandler(captcha_timeout, auto_solve=auto_solve)
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.vote_count = 0
        self.vote_callback = vote_callback
        self.tab_number = tab_number
        self.browser_manager = browser_manager
        self.slow_operation_threshold = 30  # Segundos para considerar operação lenta
        self.last_confirmation_detected = False  # Flag para evitar contar o mesmo voto duas vezes
    
    async def _ensure_element_visible(self, element) -> bool:
        """
        Garante que um elemento esteja visível e na viewport
        
        Args:
            element: Elemento do Playwright
            
        Returns:
            True se elemento está visível e na viewport, False caso contrário
        """
        try:
            if not element:
                logger.debug("Elemento é None, não é possível garantir visibilidade")
                return False
            
            # Verifica se está visível
            if not await element.is_visible():
                logger.debug("Elemento não está visível")
                return False
            
            # Faz scroll para garantir que está na viewport
            try:
                await element.scroll_into_view_if_needed()
                logger.debug("Scroll realizado para garantir elemento na viewport")
                # Pequeno delay após scroll para garantir que a página processou
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.debug(f"Erro ao fazer scroll: {e}")
                # Tenta scroll manual
                try:
                    box = await element.bounding_box()
                    if box:
                        await self.page.evaluate(f"window.scrollTo({{top: {box['y'] - 100}, behavior: 'smooth'}})")
                        await asyncio.sleep(0.3)
                except:
                    pass
            
            # Verifica novamente se está visível após scroll
            if not await element.is_visible():
                logger.warning("Elemento ainda não está visível após scroll")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Erro ao garantir visibilidade do elemento: {e}")
            return False
    
    async def detect_page_state(self) -> str:
        """
        Detecta o estado atual da página com timeout para detectar lentidão
        
        Returns:
            Estado da página (STATE_VOTING, STATE_CONFIRMATION, STATE_ERROR, STATE_UNKNOWN)
        """
        start_time = time.time()
        try:
            logger.debug("Iniciando detecção de estado da página...")
            # Aguarda um pouco para garantir que a página carregou
            await asyncio.sleep(0.5)
            
            # Verifica URL atual
            current_url = self.page.url
            logger.debug(f"URL atual: {current_url}")
            
            # Verifica se está em página de login (Globo ou Google)
            login_indicators = [
                "authx.globoid.globo.com",
                "accounts.google.com",
                "goidc.globo.com",
                "/login",
                "login-callback",
                "Fazer Login",
                "Sign in"
            ]
            
            # Verifica URL
            current_url_lower = current_url.lower()
            for indicator in login_indicators:
                if indicator.lower() in current_url_lower:
                    logger.warning(f"⚠ Página de login detectada na URL: {indicator}")
                    return self.STATE_LOGIN_REQUIRED
            
            # Verifica elementos na página que indicam login
            try:
                page_text = await self.page.inner_text('body')
                page_text_lower = page_text.lower()
                
                login_keywords = [
                    "fazer login",
                    "entrar com conta globo",
                    "escolha uma conta",
                    "sign in with google",
                    "fazer login com o google",
                    "use sua conta google",
                    "prosseguir para globo.com"
                ]
                
                for keyword in login_keywords:
                    if keyword in page_text_lower:
                        logger.warning(f"⚠ Página de login detectada (texto: '{keyword}')")
                        return self.STATE_LOGIN_REQUIRED
            except Exception as e:
                logger.debug(f"Erro ao verificar texto da página para login: {e}")
            
            # Verifica se há mensagem de erro VISÍVEL na página
            # Procura por elementos que indicam erro real (não apenas texto no HTML)
            error_keywords = [
                "algo deu errado",
                "erro na verificação",
                "votação encerrada",
                "parece que você está em mais de um dispositivo",
                "estamos com muitos acessos agora",
                "erro na verificação do usuário"
            ]
            
            has_visible_error = False
            error_message = ""
            
            # Procura em elementos h1, h2, h3 e elementos com classes de erro
            try:
                # Primeiro tenta encontrar elementos com classes de erro
                error_elements = await self.page.query_selector_all('[class*="error"], [class*="Error"], [id*="error"], [id*="Error"]')
                for elem in error_elements:
                    if await elem.is_visible():
                        text = await elem.inner_text()
                        text_lower = text.lower()
                        for keyword in error_keywords:
                            if keyword in text_lower:
                                has_visible_error = True
                                error_message = text[:200]
                                logger.warning(f"Erro visível detectado em elemento com classe de erro: {text[:100]}")
                                break
                        if has_visible_error:
                            break
                
                # Se não encontrou, procura em títulos (h1, h2, h3)
                if not has_visible_error:
                    headings = await self.page.query_selector_all('h1, h2, h3')
                    for heading in headings:
                        if await heading.is_visible():
                            text = await heading.inner_text()
                            text_lower = text.lower()
                            for keyword in error_keywords:
                                if keyword in text_lower:
                                    has_visible_error = True
                                    error_message = text[:200]
                                    logger.warning(f"Erro visível detectado em título: {text[:100]}")
                                    break
                            if has_visible_error:
                                break
            except Exception as e:
                logger.debug(f"Erro ao verificar elementos de erro: {e}")
            
            if has_visible_error:
                logger.warning(f"⚠ Estado de erro detectado: {error_message[:100]}")
                return self.STATE_ERROR
            
            # Verifica se há confirmação de voto (verifica elementos visíveis primeiro)
            try:
                logger.debug("Verificando estado de confirmação...")
                # Procura por elementos que indicam confirmação de voto
                confirmation_elements = await self.page.query_selector_all('h1, [class*="success"], [class*="Success"]')
                logger.debug(f"Encontrados {len(confirmation_elements)} elementos de confirmação")
                for elem in confirmation_elements:
                    if await elem.is_visible():
                        text = await elem.inner_text()
                        logger.debug(f"Texto do elemento de confirmação: {text[:100]}")
                        if "Seu voto" in text or "seu voto" in text.lower():
                            logger.info("✓ Estado de confirmação detectado (elemento visível com 'Seu voto')")
                            return self.STATE_CONFIRMATION
            except Exception as e:
                logger.debug(f"Erro ao verificar elementos de confirmação: {e}")
            
            # Verifica botão "Votar Novamente"
            logger.debug("Verificando botão 'Votar Novamente'...")
            confirmation_selectors = [
                'button[aria-label*="Votar novamente"]',
                'button[aria-label*="Votar Novamente"]',
                'button[aria-label*="votar novamente"]'
            ]
            
            for selector in confirmation_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element:
                        is_visible = await element.is_visible()
                        logger.debug(f"Botão 'Votar Novamente' encontrado com seletor: {selector}, visível: {is_visible}")
                        if is_visible:
                            logger.info("✓ Estado de confirmação detectado (botão 'Votar Novamente' encontrado)")
                            return self.STATE_CONFIRMATION
                except Exception as e:
                    logger.debug(f"Erro ao verificar seletor {selector}: {e}")
                    continue
            
            # Verifica se há botões de votação (estado de votação ativa)
            try:
                logger.debug(f"Verificando estado de votação para participante: {self.participant_name}")
                # Primeiro, verifica se há botão com aria-label exato do participante configurado
                exact_selector = f'button[aria-label="{self.participant_name}"]'
                logger.debug(f"Tentando encontrar botão com seletor exato: {exact_selector}")
                exact_button = await self.page.query_selector(exact_selector)
                if exact_button:
                    is_visible = await exact_button.is_visible()
                    logger.debug(f"Botão exato encontrado, visível: {is_visible}")
                    if is_visible:
                        logger.info(f"✓ Estado de votação ativa detectado (botão exato encontrado: {self.participant_name})")
                        return self.STATE_VOTING
                else:
                    logger.debug("Botão exato não encontrado, tentando fallback...")
                
                # Fallback: Procura por botões com aria-label contendo o nome do participante (visíveis)
                logger.debug("Buscando botões com aria-label contendo nome do participante...")
                buttons = await self.page.query_selector_all('button[aria-label]')
                logger.debug(f"Encontrados {len(buttons)} botões com aria-label")
                for button in buttons:
                    # Verifica se o botão está visível
                    if await button.is_visible():
                        aria_label = await button.get_attribute('aria-label')
                        logger.debug(f"Botão visível encontrado com aria-label: {aria_label}")
                        if aria_label and self.participant_name in aria_label:
                            logger.info(f"✓ Estado de votação ativa detectado (botão visível: {aria_label})")
                            return self.STATE_VOTING
                
                # Verifica se há texto indicando votação em elementos visíveis
                try:
                    logger.debug("Verificando texto em elementos h1...")
                    h1_elements = await self.page.query_selector_all('h1')
                    logger.debug(f"Encontrados {len(h1_elements)} elementos h1")
                    for h1 in h1_elements:
                        if await h1.is_visible():
                            text = await h1.inner_text()
                            logger.debug(f"Texto do h1 visível: {text[:100]}")
                            if "quem você quer eliminar" in text.lower():
                                logger.info("✓ Estado de votação ativa detectado (via h1 visível)")
                                return self.STATE_VOTING
                except Exception as e:
                    logger.debug(f"Erro ao verificar h1: {e}")
            except Exception as e:
                logger.debug(f"Erro ao verificar estado de votação: {e}")
            
            logger.warning("⚠ Estado desconhecido da página")
            return self.STATE_UNKNOWN
            
        except Exception as e:
            logger.error(f"Erro ao detectar estado da página: {e}")
            return self.STATE_UNKNOWN
        finally:
            # Verifica se operação demorou muito (lentidão detectada)
            elapsed = time.time() - start_time
            if elapsed > self.slow_operation_threshold:
                logger.warning(f"⚠ Operação demorou {elapsed:.1f}s (limite: {self.slow_operation_threshold}s) - Site está lento!")
                # Sistema de pausa automática desativado
    
    async def find_participant_button(self):
        """
        Localiza o botão do participante usando estratégia robusta com múltiplos fallbacks
        Monitora tempo para detectar lentidão
        
        Returns:
            Elemento do botão ou None se não encontrado
        """
        start_time = time.time()
        logger.debug(f"Procurando botão do participante: {self.participant_name}")
        
        # Prioridade 1: aria-label exato com espera explícita
        try:
            selector = f'button[aria-label="{self.participant_name}"]'
            logger.debug(f"Tentando seletor exato: {selector}")
            try:
                # Espera explícita pelo elemento aparecer
                button = await self.page.wait_for_selector(selector, timeout=5000, state='visible')
                if button:
                    # Garante que está visível e na viewport
                    if await self._ensure_element_visible(button):
                        # Verifica se está habilitado
                        is_enabled = await button.is_enabled()
                        if is_enabled:
                            logger.info(f"✓ Botão encontrado usando aria-label exato: {selector} (habilitado)")
                            return button
                        else:
                            logger.warning(f"Botão encontrado mas está desabilitado: {selector}")
                    else:
                        logger.warning(f"Botão encontrado mas não está visível: {selector}")
            except Exception as e:
                logger.debug(f"Espera explícita falhou para seletor exato: {e}")
        except Exception as e:
            logger.debug(f"Falha ao tentar aria-label exato: {e}")
        
        # Fallback 1: aria-label contendo o nome com espera
        try:
            selector = f'button[aria-label*="{self.participant_name}"]'
            logger.debug(f"Tentando seletor parcial: {selector}")
            try:
                button = await self.page.wait_for_selector(selector, timeout=3000, state='visible')
                if button:
                    if await self._ensure_element_visible(button):
                        is_enabled = await button.is_enabled()
                        if is_enabled:
                            logger.info(f"✓ Botão encontrado usando aria-label parcial: {selector} (habilitado)")
                            return button
                        else:
                            logger.warning(f"Botão encontrado mas está desabilitado: {selector}")
            except Exception as e:
                logger.debug(f"Espera explícita falhou para seletor parcial: {e}")
        except Exception as e:
            logger.debug(f"Falha ao tentar aria-label parcial: {e}")
        
        # Fallback 2: Busca todos os botões e filtra por texto interno
        try:
            logger.debug("Tentando buscar botões por texto interno")
            buttons = await self.page.query_selector_all('button')
            logger.debug(f"Encontrados {len(buttons)} botões na página")
            for button in buttons:
                try:
                    text_content = await button.inner_text()
                    if self.participant_name.lower() in text_content.lower():
                        if await self._ensure_element_visible(button):
                            is_enabled = await button.is_enabled()
                            if is_enabled:
                                logger.info(f"✓ Botão encontrado filtrando por texto interno (habilitado)")
                                return button
                except:
                    continue
        except Exception as e:
            logger.debug(f"Falha ao filtrar botões por texto: {e}")
        
        # Fallback 3: XPath
        try:
            xpath = f'//button[contains(., "{self.participant_name}")]'
            logger.debug(f"Tentando XPath: {xpath}")
            button = await self.page.query_selector(f'xpath={xpath}')
            if button:
                if await self._ensure_element_visible(button):
                    is_enabled = await button.is_enabled()
                    if is_enabled:
                        logger.info(f"✓ Botão encontrado usando XPath (habilitado)")
                        return button
        except Exception as e:
            logger.debug(f"Falha ao tentar XPath: {e}")
        
        logger.error(f"✗ Botão do participante '{self.participant_name}' não encontrado após todas as tentativas")
        
        # Verifica se operação demorou muito
        elapsed = time.time() - start_time
        if elapsed > self.slow_operation_threshold:
            logger.warning(f"⚠ Busca de botão demorou {elapsed:.1f}s (limite: {self.slow_operation_threshold}s) - Site está lento!")
            # Sistema de pausa automática desativado
        
        return None
    
    async def vote(self) -> bool:
        """
        Executa o voto no participante com monitoramento de lentidão
        
        Returns:
            True se voto foi executado com sucesso, False caso contrário
        """
        start_time = time.time()
        try:
            logger.info(f"Iniciando processo de voto para: {self.participant_name}")
            
            # Localiza o botão do participante
            button = await self.find_participant_button()
            if not button:
                logger.error("✗ Não foi possível encontrar o botão do participante")
                return False
            
            # Garante que o botão está visível e na viewport
            logger.debug("Garantindo que botão está visível e na viewport...")
            if not await self._ensure_element_visible(button):
                logger.error("✗ Botão não está visível após tentativas de scroll")
                return False
            
            # Verifica se o botão está habilitado
            is_enabled = await button.is_enabled()
            if not is_enabled:
                logger.error("✗ Botão encontrado mas está desabilitado")
                return False
            
            logger.info(f"✓ Botão encontrado, visível e habilitado. Clicando em: {self.participant_name}")
            
            # Clica no botão
            try:
                await button.click(timeout=5000)
                logger.info("✓ Clique executado no botão")
            except Exception as e:
                logger.error(f"✗ Erro ao clicar no botão: {e}")
                return False
            
            # Aguarda um pouco para a página processar o clique
            await asyncio.sleep(1)
            
            # Verifica se o clique funcionou procurando pela mensagem de confirmação
            logger.debug("Verificando se clique foi confirmado...")
            confirmation_message = f"Você selecionou a opção {self.participant_name}"
            confirmation_found = False
            
            # Aguarda até 5 segundos pela mensagem de confirmação
            for attempt in range(5):
                try:
                    page_content = await self.page.content()
                    page_text = await self.page.inner_text('body')
                    
                    if confirmation_message in page_text or f"Você selecionou a opção" in page_text:
                        logger.info(f"✓ Clique confirmado! Mensagem encontrada: '{confirmation_message}'")
                        confirmation_found = True
                        break
                except:
                    pass
                
                await asyncio.sleep(1)
            
            if not confirmation_found:
                logger.warning("⚠ Mensagem de confirmação do clique não encontrada, mas continuando...")
            
            # Aguarda o captcha aparecer
            logger.info("Aguardando captcha aparecer...")
            captcha_appeared = await self.captcha_handler.wait_for_captcha(self.page)
            if not captcha_appeared:
                logger.warning("⚠ Captcha não apareceu após clicar no botão. Verificando se voto foi processado...")
                # Aguarda mais um pouco - às vezes o captcha demora para aparecer
                await asyncio.sleep(3)
                # Tenta detectar novamente
                captcha_appeared = await self.captcha_handler.wait_for_captcha(self.page)
                if not captcha_appeared:
                    # Verifica se o voto foi processado sem captcha
                    state = await self.detect_page_state()
                    if state == self.STATE_CONFIRMATION:
                        logger.info("✓ Voto confirmado sem captcha")
                        return True
                    logger.error("✗ Captcha não apareceu e voto não foi confirmado")
                    return False
            
            logger.info("✓ Captcha detectado! Aguardando resolução manual...")
            logger.info("Por favor, clique em 'Sou humano' e resolva o captcha na página do navegador.")
            
            # Aguarda resolução manual do captcha
            resolved = await self.captcha_handler.wait_for_captcha_solution(self.page)
            if not resolved:
                logger.error("✗ Captcha não foi resolvido dentro do timeout")
                return False
            
            logger.info("✓ Captcha resolvido! Voto processado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"✗ Erro ao executar voto: {e}", exc_info=True)
            return False
        finally:
            # Verifica se operação demorou muito
            elapsed = time.time() - start_time
            if elapsed > self.slow_operation_threshold:
                logger.warning(f"⚠ Processo de voto demorou {elapsed:.1f}s (limite: {self.slow_operation_threshold}s) - Site está lento!")
                # Sistema de pausa automática desativado
    
    async def click_vote_again(self) -> bool:
        """
        Localiza e clica no botão "Votar Novamente"
        
        Returns:
            True se botão foi clicado, False caso contrário
        """
        try:
            # Prioridade 1: aria-label contendo "Votar novamente" ou "Votar Novamente"
            selectors = [
                'button[aria-label*="Votar novamente"]',
                'button[aria-label*="Votar Novamente"]',
                'button[aria-label*="votar novamente"]'
            ]
            
            for selector in selectors:
                try:
                    button = await self.page.query_selector(selector)
                    if button:
                        logger.info(f"Botão 'Votar Novamente' encontrado: {selector}")
                        await button.click()
                        await asyncio.sleep(2)  # Aguarda página atualizar
                        return True
                except:
                    continue
            
            # Fallback 1: Busca todos os botões e filtra por texto
            try:
                buttons = await self.page.query_selector_all('button')
                for button in buttons:
                    text_content = await button.inner_text()
                    if "votar" in text_content.lower() and "novamente" in text_content.lower():
                        logger.info("Botão 'Votar Novamente' encontrado por texto")
                        await button.click()
                        await asyncio.sleep(2)
                        return True
            except Exception as e:
                logger.debug(f"Falha ao buscar por texto: {e}")
            
            # Fallback 2: XPath
            try:
                xpath = '//button[contains(text(), "Votar") and contains(text(), "Novamente")]'
                button = await self.page.query_selector(f'xpath={xpath}')
                if button:
                    logger.info("Botão 'Votar Novamente' encontrado por XPath")
                    await button.click()
                    await asyncio.sleep(2)
                    return True
            except Exception as e:
                logger.debug(f"Falha ao usar XPath: {e}")
            
            logger.error("Botão 'Votar Novamente' não encontrado")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar em 'Votar Novamente': {e}")
            return False
    
    async def run_vote_loop(self, max_votes: int = -1):
        """
        Loop principal de votação com verificação de pausa
        
        Args:
            max_votes: Número máximo de votos (-1 para infinito)
        """
        logger.info(f"Iniciando loop de votação para {self.participant_name}")
        
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        while True:
            try:
                # Verifica se a aba está na página correta antes de votar
                if self.browser_manager:
                    # Primeiro verifica se está em página de login
                    current_url = self.page.url.lower()
                    login_urls = [
                        "authx.globoid.globo.com",
                        "accounts.google.com",
                        "goidc.globo.com"
                    ]
                    
                    is_login_page = any(login_url in current_url for login_url in login_urls)
                    
                    if is_login_page:
                        logger.warning(f"⚠ Aba {self.tab_number} está em página de login. Aguardando login...")
                        # Detecta como login necessário para tratamento adequado
                        state = self.STATE_LOGIN_REQUIRED
                    elif not await self.browser_manager.check_all_tabs_on_vote_page():
                        logger.warning(f"Aba {self.tab_number} não está na página de votação. Aguardando...")
                        await asyncio.sleep(2)
                        continue
                    else:
                        # Se não está em login e está na página correta, continua normalmente
                        state = None
                
                # Se detectou login necessário, trata imediatamente sem verificar limite
                if state == self.STATE_LOGIN_REQUIRED:
                    # O tratamento do login está abaixo no código
                    pass
                else:
                    # Verifica limite de votos apenas se não estiver em login
                    if max_votes > 0 and self.vote_count >= max_votes:
                        logger.info(f"Limite de votos atingido: {self.vote_count}/{max_votes}")
                        break
                
                # Detecta estado da página (só se não foi detectado login antes)
                if state is None:
                    state = await self.detect_page_state()
                logger.info(f"Estado da página: {state} (Votos realizados: {self.vote_count})")
                
                # Reseta contador de erros se estado não for erro
                if state != self.STATE_ERROR:
                    consecutive_errors = 0
                
                if state == self.STATE_VOTING:
                    # Reseta flag de confirmação quando volta para estado de votação
                    # (indica que um novo ciclo de voto começou)
                    if self.last_confirmation_detected:
                        self.last_confirmation_detected = False
                    
                    # Executa o voto (mas NÃO conta ainda - só conta quando aparecer confirmação)
                    success = await self.vote()
                    if success:
                        logger.info(f"Voto executado, aguardando confirmação... (Aba {self.tab_number})")
                    else:
                        logger.warning("Falha ao executar voto")
                        await asyncio.sleep(5)  # Aguarda antes de tentar novamente
                
                elif state == self.STATE_CONFIRMATION:
                    # VOTO CONFIRMADO! Tela de "Votar Novamente" apareceu
                    # Só agora contamos o voto como válido (e só uma vez)
                    if not self.last_confirmation_detected:
                        self.vote_count += 1
                        self.last_confirmation_detected = True  # Marca que já contou este voto
                        logger.info(f"✓ VOTO #{self.vote_count} CONFIRMADO! (Aba {self.tab_number}) - Tela 'Votar Novamente' detectada")
                        
                        # Chama callback para atualizar contador global
                        if self.vote_callback:
                            await self.vote_callback(self.tab_number)
                    else:
                        logger.debug("Confirmação já foi contada, aguardando clique em 'Votar Novamente'...")
                    
                    # Clica em "Votar Novamente"
                    logger.info("Clicando em 'Votar Novamente'...")
                    clicked = await self.click_vote_again()
                    if clicked:
                        # Reseta flag após clicar (próxima confirmação será um novo voto)
                        self.last_confirmation_detected = False
                        # Aguarda página atualizar
                        await asyncio.sleep(3)
                    else:
                        logger.warning("Não foi possível clicar em 'Votar Novamente'")
                        await asyncio.sleep(5)
                
                elif state == self.STATE_LOGIN_REQUIRED:
                    logger.warning("=" * 60)
                    logger.warning("⚠ LOGIN NECESSÁRIO DETECTADO!")
                    logger.warning(f"Aba {self.tab_number} está em página de login.")
                    logger.warning("O bot parou de tentar votar até que o login seja feito.")
                    logger.warning("Por favor, faça login na aba do navegador.")
                    logger.warning("O bot aguardará até que você esteja autenticado...")
                    logger.warning("=" * 60)
                    
                    # Aguarda até que o login seja feito e volte para página de votação
                    max_wait_login = 300  # 5 minutos
                    wait_interval = 3  # Verifica a cada 3 segundos
                    waited_time = 0
                    
                    while waited_time < max_wait_login:
                        await asyncio.sleep(wait_interval)
                        waited_time += wait_interval
                        
                        # Verifica se ainda está em página de login
                        new_state = await self.detect_page_state()
                        
                        if new_state != self.STATE_LOGIN_REQUIRED:
                            # Verifica se voltou para página de votação
                            if self.browser_manager:
                                if await self.browser_manager.check_all_tabs_on_vote_page():
                                    logger.info("✓ Login detectado! Voltou para página de votação.")
                                    # Salva a conta se detectar email (usa método público)
                                    if self.browser_manager:
                                        try:
                                            # Aguarda um pouco para garantir que a página carregou
                                            await asyncio.sleep(2)
                                            # O browser_manager salvará automaticamente quando detectar autenticação
                                        except Exception as e:
                                            logger.debug(f"Erro ao processar login: {e}")
                                    break
                                else:
                                    logger.debug(f"Ainda não está na página de votação. Estado: {new_state}")
                            else:
                                logger.info("✓ Login detectado! Continuando...")
                                break
                        else:
                            if waited_time % 30 == 0:  # Avisa a cada 30 segundos
                                remaining = max_wait_login - waited_time
                                logger.info(f"Aguardando login... ({remaining}s restantes)")
                    
                    if waited_time >= max_wait_login:
                        logger.error("⚠ Timeout aguardando login. Continuando de qualquer forma...")
                    else:
                        logger.info("✓ Login concluído! Retomando votação...")
                    await asyncio.sleep(2)  # Aguarda um pouco antes de continuar
                
                elif state == self.STATE_ERROR:
                    consecutive_errors += 1
                    logger.error(f"Erro detectado na página ({consecutive_errors}/{max_consecutive_errors}). Aguardando antes de tentar novamente...")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error(f"Muitos erros consecutivos ({consecutive_errors}). Verifique a autenticação ou a conexão.")
                        await asyncio.sleep(30)  # Aguarda mais tempo antes de continuar
                        consecutive_errors = 0  # Reseta para tentar novamente
                    
                    # Tenta recarregar a página
                    try:
                        logger.info("Recarregando página...")
                        await self.page.reload(wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(5)
                        # Verifica novamente o estado após recarregar
                        new_state = await self.detect_page_state()
                        logger.info(f"Estado após recarregar: {new_state}")
                    except Exception as e:
                        logger.error(f"Erro ao recarregar página: {e}")
                        await asyncio.sleep(10)
                
                else:
                    logger.warning(f"Estado desconhecido: {state}. Aguardando...")
                    # Tenta recarregar se estado desconhecido persistir
                    try:
                        await self.page.reload(wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(3)
                    except:
                        pass
                    await asyncio.sleep(5)
                
                # Delay aleatório entre iterações
                if state != self.STATE_CONFIRMATION:  # Não delay após clicar em "Votar Novamente"
                    delay = random.uniform(self.delay_min, self.delay_max)
                    logger.debug(f"Aguardando {delay:.1f}s antes da próxima iteração")
                    await asyncio.sleep(delay)
                
            except Exception as e:
                logger.error(f"Erro no loop de votação: {e}")
                await asyncio.sleep(5)
        
        logger.info("Loop de votação finalizado")

