"""
Módulo para detecção e tratamento de captcha hCaptcha
"""
import logging
import asyncio
from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Importações opcionais para modo automático
try:
    import io
    import numpy as np
    from PIL import Image
    from image_recognition import detect_challenge_type, process_image_grid
    IMAGE_RECOGNITION_AVAILABLE = True
except ImportError as e:
    IMAGE_RECOGNITION_AVAILABLE = False
    logger.debug(f"Bibliotecas de reconhecimento de imagem não disponíveis: {e}")


class CaptchaHandler:
    """Gerencia detecção e resolução de captcha"""
    
    def __init__(self, timeout: int = 300, auto_solve: bool = False):
        """
        Args:
            timeout: Tempo máximo de espera para resolução do captcha (segundos)
            auto_solve: Se True, tenta resolver automaticamente usando reconhecimento de imagem
        """
        self.timeout = timeout
        self.auto_solve = auto_solve
    
    async def wait_for_captcha(self, page: Page) -> bool:
        """
        Aguarda o aparecimento do captcha na página
        
        Args:
            page: Página do Playwright
            
        Returns:
            True se captcha apareceu, False caso contrário
        """
        try:
            # Aguarda o iframe do hCaptcha aparecer
            captcha_selectors = [
                'iframe[title*="hCaptcha"]',
                'iframe[src*="hcaptcha.com"]',
                'iframe[data-hcaptcha-widget-id]'
            ]
            
            captcha_iframe = None
            for selector in captcha_selectors:
                try:
                    captcha_iframe = await page.wait_for_selector(selector, timeout=5000, state='visible')
                    if captcha_iframe:
                        logger.info(f"✓ Captcha detectado usando seletor: {selector}")
                        # Tenta clicar automaticamente no checkbox "Sou humano"
                        await self._click_captcha_checkbox(page, captcha_iframe)
                        return True
                except:
                    continue
            
            # Verifica se há textarea de captcha
            try:
                await page.wait_for_selector('textarea[name="h-captcha-response"]', timeout=2000)
                logger.info("✓ Captcha detectado via textarea")
                return True
            except:
                pass
            
            return False
        except Exception as e:
            logger.error(f"Erro ao detectar captcha: {e}")
            return False
    
    async def _click_captcha_checkbox(self, page: Page, iframe_element) -> bool:
        """
        Tenta clicar automaticamente no checkbox "Sou humano" do captcha
        
        Args:
            page: Página do Playwright
            iframe_element: Elemento do iframe do captcha
            
        Returns:
            True se conseguiu clicar, False caso contrário
        """
        try:
            logger.info("Tentando clicar automaticamente no checkbox 'Sou humano'...")
            
            # Aguarda o iframe carregar completamente
            await asyncio.sleep(2)
            
            # Método 1: Tentar encontrar o frame do iframe
            try:
                # Obtém o widget-id do iframe
                widget_id = await iframe_element.get_attribute('data-hcaptcha-widget-id')
                
                # Aguarda os frames carregarem
                await asyncio.sleep(1)
                
                # Procura o frame do captcha
                frames = page.frames
                captcha_frame = None
                for frame in frames:
                    if 'hcaptcha' in frame.url.lower():
                        captcha_frame = frame
                        break
                
                if captcha_frame:
                    logger.debug(f"Frame do captcha encontrado: {captcha_frame.url}")
                    
                    # Tenta encontrar e clicar no checkbox dentro do frame
                    checkbox_selectors = [
                        '#checkbox',
                        '.checkbox',
                        '[id*="checkbox"]',
                        '[class*="checkbox"]',
                        'input[type="checkbox"]',
                        'div[role="checkbox"]',
                        '[aria-label*="human"]',
                        '[aria-label*="humano"]',
                        '[aria-checked="false"]',
                        'label[for*="checkbox"]'
                    ]
                    
                    for selector in checkbox_selectors:
                        try:
                            checkbox = await captcha_frame.query_selector(selector)
                            if checkbox:
                                is_visible = await checkbox.is_visible()
                                if is_visible:
                                    await checkbox.click(timeout=3000)
                                    logger.info("✓ Checkbox 'Sou humano' clicado automaticamente via frame!")
                                    await asyncio.sleep(2)
                                    # Verifica se apareceu o desafio de imagens e foca a aba
                                    await self._handle_image_challenge(page, iframe_element)
                                    return True
                        except Exception as e:
                            logger.debug(f"Tentativa com seletor {selector} falhou: {e}")
                            continue
            except Exception as e:
                logger.debug(f"Erro ao tentar usar frame: {e}")
            
            # Método 2: Usar frame_locator (API mais moderna do Playwright)
            try:
                frame_locator = page.frame_locator('iframe[title*="hCaptcha"]')
                
                checkbox_selectors = [
                    '#checkbox',
                    '.checkbox',
                    '[id*="checkbox"]',
                    '[class*="checkbox"]',
                    'input[type="checkbox"]',
                    'div[role="checkbox"]'
                ]
                
                for selector in checkbox_selectors:
                    try:
                        checkbox = frame_locator.locator(selector).first
                        if await checkbox.is_visible(timeout=2000):
                            await checkbox.click(timeout=3000)
                            logger.info("✓ Checkbox 'Sou humano' clicado automaticamente via frame_locator!")
                            await asyncio.sleep(2)
                            # Verifica se apareceu o desafio de imagens e foca a aba
                            await self._handle_image_challenge(page, iframe_element)
                            return True
                    except:
                        continue
            except Exception as e:
                logger.debug(f"Erro ao tentar usar frame_locator: {e}")
            
            # Método 3: Clicar por coordenadas no centro do iframe
            try:
                iframe_box = await iframe_element.bounding_box()
                if iframe_box:
                    # Clica no centro-esquerda do iframe (onde geralmente está o checkbox)
                    x = iframe_box['x'] + (iframe_box['width'] * 0.25)  # 25% da largura (lado esquerdo)
                    y = iframe_box['y'] + (iframe_box['height'] * 0.5)   # Centro vertical
                    await page.mouse.click(x, y)
                    logger.info("✓ Clicado na área do checkbox do captcha (coordenadas)")
                    await asyncio.sleep(2)
                    # Verifica se apareceu o desafio de imagens e foca a aba
                    await self._handle_image_challenge(page, iframe_element)
                    return True
            except Exception as e:
                logger.debug(f"Erro ao clicar por coordenadas: {e}")
            
            logger.warning("⚠ Não foi possível clicar automaticamente no checkbox. Será necessário clicar manualmente.")
            return False
                
        except Exception as e:
            logger.debug(f"Erro ao tentar automatizar clique no captcha: {e}")
            return False
    
    async def _handle_image_challenge(self, page: Page, iframe_element) -> None:
        """
        Detecta se apareceu o desafio de imagens e tenta resolver automaticamente ou foca a aba para resolução manual
        
        Args:
            page: Página do Playwright
            iframe_element: Elemento do iframe do captcha
        """
        try:
            # Aguarda um pouco para o desafio aparecer
            await asyncio.sleep(3)
            
            # Verifica se apareceu o desafio de imagens
            # O desafio de imagens geralmente tem um iframe maior ou elementos específicos
            try:
                # Verifica se o iframe cresceu (indicando que apareceu o desafio)
                iframe_box = await iframe_element.bounding_box()
                if iframe_box and iframe_box['height'] > 200:  # Desafio de imagens é maior
                    logger.info("Desafio de imagens detectado!")
                    
                    # Se auto_solve está habilitado, tenta resolver automaticamente
                    if self.auto_solve:
                        logger.info("Tentando resolver automaticamente...")
                        solved = await self._solve_image_challenge(page, iframe_element)
                        if solved:
                            logger.info("✓ Desafio de imagens resolvido automaticamente!")
                            return
                        else:
                            logger.warning("⚠ Não foi possível resolver automaticamente. Focando aba para resolução manual...")
                    
                    # Se não resolveu automaticamente ou auto_solve está desabilitado, foca para manual
                    await self._focus_tab_for_manual_solution(page, iframe_element)
                    return
                
                # Verifica se há elementos indicando desafio de imagens dentro do frame
                frames = page.frames
                for frame in frames:
                    if 'hcaptcha' in frame.url.lower():
                        try:
                            # Procura por elementos que indicam desafio de imagens
                            challenge_elements = await frame.query_selector_all('img, [class*="challenge"], [class*="image"], [class*="grid"]')
                            if len(challenge_elements) > 5:  # Desafio de imagens tem várias imagens
                                logger.info("Desafio de imagens detectado!")
                                
                                # Se auto_solve está habilitado, tenta resolver automaticamente
                                if self.auto_solve:
                                    logger.info("Tentando resolver automaticamente...")
                                    solved = await self._solve_image_challenge(page, iframe_element)
                                    if solved:
                                        logger.info("✓ Desafio de imagens resolvido automaticamente!")
                                        return
                                    else:
                                        logger.warning("⚠ Não foi possível resolver automaticamente. Focando aba para resolução manual...")
                                
                                # Se não resolveu automaticamente ou auto_solve está desabilitado, foca para manual
                                await self._focus_tab_for_manual_solution(page, iframe_element)
                                return
                        except:
                            continue
                
                # Verifica se há texto indicando desafio
                try:
                    page_text = await page.inner_text('body')
                    if any(keyword in page_text.lower() for keyword in ['toque em', 'selecione', 'imagens', 'itens comumente']):
                        logger.info("Desafio de imagens detectado (via texto)!")
                        
                        # Se auto_solve está habilitado, tenta resolver automaticamente
                        if self.auto_solve:
                            logger.info("Tentando resolver automaticamente...")
                            solved = await self._solve_image_challenge(page, iframe_element)
                            if solved:
                                logger.info("✓ Desafio de imagens resolvido automaticamente!")
                                return
                            else:
                                logger.warning("⚠ Não foi possível resolver automaticamente. Focando aba para resolução manual...")
                        
                        # Se não resolveu automaticamente ou auto_solve está desabilitado, foca para manual
                        await self._focus_tab_for_manual_solution(page, iframe_element)
                        return
                except:
                    pass
                    
            except Exception as e:
                logger.debug(f"Erro ao verificar desafio de imagens: {e}")
                
        except Exception as e:
            logger.debug(f"Erro ao processar desafio de imagens: {e}")
    
    async def _solve_image_challenge(self, page: Page, iframe_element) -> bool:
        """
        Tenta resolver automaticamente o desafio de imagens do captcha
        
        Args:
            page: Página do Playwright
            iframe_element: Elemento do iframe do captcha
            
        Returns:
            True se conseguiu resolver, False caso contrário
        """
        if not IMAGE_RECOGNITION_AVAILABLE:
            logger.warning("Bibliotecas de reconhecimento de imagem não estão instaladas!")
            logger.warning("Instale com: pip install pillow opencv-python numpy scikit-learn")
            return False
        
        try:
            logger.info("Iniciando resolução automática do desafio de imagens...")
            
            # Encontra o frame do captcha
            frames = page.frames
            captcha_frame = None
            for frame in frames:
                if 'hcaptcha' in frame.url.lower():
                    captcha_frame = frame
                    break
            
            if not captcha_frame:
                logger.warning("Frame do captcha não encontrado")
                return False
            
            # Aguarda o desafio carregar completamente
            await asyncio.sleep(2)
            
            # Obtém o texto do desafio para detectar o tipo
            try:
                challenge_text = await captcha_frame.inner_text('body')
                challenge_type = detect_challenge_type(challenge_text)
                
                if not challenge_type:
                    logger.warning("Tipo de desafio não detectado")
                    return False
                
                logger.info(f"Tipo de desafio detectado: {challenge_type}")
            except Exception as e:
                logger.warning(f"Erro ao detectar tipo de desafio: {e}")
                return False
            
            # Encontra todas as imagens do grid (geralmente 9 imagens em grid 3x3)
            try:
                # Aguarda as imagens aparecerem
                await asyncio.sleep(2)
                
                # Procura por imagens no grid
                image_selectors = [
                    'img[class*="challenge"]',
                    'img[class*="image"]',
                    'img[class*="grid"]',
                    '.challenge-image',
                    '.grid-image',
                    '[class*="challenge"] img',
                    '[class*="grid"] img'
                ]
                
                images = []
                for selector in image_selectors:
                    try:
                        image_elements = await captcha_frame.query_selector_all(selector)
                        if len(image_elements) >= 9:  # Grid geralmente tem 9 imagens
                            images = image_elements
                            logger.info(f"Encontradas {len(images)} imagens usando seletor: {selector}")
                            break
                    except:
                        continue
                
                # Se não encontrou com seletores específicos, tenta encontrar todas as imagens
                if len(images) < 9:
                    try:
                        all_images = await captcha_frame.query_selector_all('img')
                        # Filtra imagens que parecem ser do grid (tamanho razoável)
                        images = []
                        for img in all_images:
                            try:
                                box = await img.bounding_box()
                                if box and box['width'] > 50 and box['height'] > 50:
                                    images.append(img)
                            except:
                                continue
                        if len(images) >= 9:
                            logger.info(f"Encontradas {len(images)} imagens (filtradas)")
                    except:
                        pass
                
                if len(images) < 9:
                    logger.warning(f"Não foram encontradas imagens suficientes no grid. Encontradas: {len(images)}")
                    return False
                
                # Limita a 9 imagens (grid 3x3)
                images = images[:9]
                
            except Exception as e:
                logger.error(f"Erro ao encontrar imagens do grid: {e}")
                return False
            
            # Captura screenshots de cada imagem e converte para arrays numpy
            image_arrays = []
            for i, img_element in enumerate(images):
                try:
                    # Captura screenshot da imagem
                    screenshot_bytes = await img_element.screenshot()
                    
                    # Converte para PIL Image
                    pil_image = Image.open(io.BytesIO(screenshot_bytes))
                    
                    # Converte para array numpy RGB
                    img_array = np.array(pil_image.convert('RGB'))
                    image_arrays.append(img_array)
                    
                    logger.debug(f"Imagem {i} capturada: {img_array.shape}")
                except Exception as e:
                    logger.warning(f"Erro ao capturar imagem {i}: {e}")
                    # Adiciona array vazio como fallback
                    image_arrays.append(None)
            
            # Remove imagens None
            image_arrays = [img for img in image_arrays if img is not None]
            
            if len(image_arrays) < 9:
                logger.warning(f"Não foi possível capturar todas as imagens. Capturadas: {len(image_arrays)}")
                return False
            
            # Processa o grid para identificar imagens corretas
            correct_indices = process_image_grid(image_arrays, challenge_type)
            
            if not correct_indices:
                logger.warning("Nenhuma imagem correta identificada")
                return False
            
            logger.info(f"Imagens corretas identificadas: {correct_indices}")
            
            # Clica nas imagens corretas
            for idx in correct_indices:
                try:
                    if idx < len(images):
                        await images[idx].click(timeout=3000)
                        logger.debug(f"Imagem {idx} clicada")
                        await asyncio.sleep(0.5)  # Pequeno delay entre cliques
                except Exception as e:
                    logger.warning(f"Erro ao clicar na imagem {idx}: {e}")
            
            # Aguarda um pouco antes de clicar no botão "Verificar"
            await asyncio.sleep(1)
            
            # Procura e clica no botão "Verificar"
            verify_button_selectors = [
                'button[class*="verify"]',
                'button[class*="submit"]',
                'button:has-text("Verificar")',
                'button:has-text("Verify")',
                '[class*="verify-button"]',
                '[class*="submit-button"]',
                'button[type="submit"]'
            ]
            
            verify_clicked = False
            for selector in verify_button_selectors:
                try:
                    verify_button = await captcha_frame.query_selector(selector)
                    if verify_button:
                        is_visible = await verify_button.is_visible()
                        if is_visible:
                            await verify_button.click(timeout=3000)
                            logger.info("✓ Botão 'Verificar' clicado")
                            verify_clicked = True
                            break
                except:
                    continue
            
            if not verify_clicked:
                logger.warning("Botão 'Verificar' não encontrado")
                return False
            
            # Aguarda confirmação de que o captcha foi resolvido
            await asyncio.sleep(3)
            
            # Verifica se o captcha foi resolvido
            resolved = await self.is_captcha_resolved(page)
            if resolved:
                logger.info("✓ Captcha resolvido com sucesso!")
                return True
            else:
                logger.warning("Captcha não foi resolvido após clicar em Verificar")
                return False
            
        except Exception as e:
            logger.error(f"Erro ao resolver desafio de imagens: {e}", exc_info=True)
            return False
    
    async def _focus_tab_for_manual_solution(self, page: Page, iframe_element) -> None:
        """
        Foca a aba e faz scroll para o captcha ficar visível para resolução manual
        
        Args:
            page: Página do Playwright
            iframe_element: Elemento do iframe do captcha
        """
        try:
            # Foca a aba
            await page.bring_to_front()
            logger.info("Aba focada para resolução manual do captcha")
            
            # Faz scroll para o captcha ficar visível
            try:
                await iframe_element.scroll_into_view_if_needed()
                logger.info("Scroll realizado para mostrar o captcha")
            except:
                # Fallback: scroll manual
                try:
                    iframe_box = await iframe_element.bounding_box()
                    if iframe_box:
                        await page.evaluate(f"window.scrollTo({{top: {iframe_box['y'] - 100}, behavior: 'smooth'}})")
                except:
                    pass
            
            # Aguarda um pouco para garantir que a aba está visível
            await asyncio.sleep(0.5)
            
            # Exibe mensagem no terminal
            print(f"\n{'='*60}")
            print(f"ATENCAO: Desafio de imagens detectado!")
            print(f"Por favor, resolva o captcha manualmente na aba focada.")
            print(f"{'='*60}\n")
            
        except Exception as e:
            logger.debug(f"Erro ao focar aba: {e}")
    
    async def wait_for_captcha_solution(self, page: Page) -> bool:
        """
        Aguarda a resolução manual do captcha
        
        Args:
            page: Página do Playwright
            
        Returns:
            True se captcha foi resolvido, False se timeout
        """
        logger.info("Aguardando resolução manual do captcha...")
        logger.info("Por favor, resolva o captcha na página do navegador.")
        
        start_time = asyncio.get_event_loop().time()
        last_log_time = 0
        challenge_focused = False  # Flag para evitar focar múltiplas vezes
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            
            if elapsed > self.timeout:
                logger.warning(f"✗ Timeout aguardando resolução do captcha ({self.timeout}s)")
                return False
            
            # Verifica se apareceu o desafio de imagens e foca a aba (apenas uma vez)
            if not challenge_focused:
                try:
                    captcha_iframe = await page.query_selector('iframe[title*="hCaptcha"]')
                    if captcha_iframe:
                        iframe_box = await captcha_iframe.bounding_box()
                        if iframe_box and iframe_box['height'] > 200:
                            # Desafio de imagens detectado
                            await self._focus_tab_for_manual_solution(page, captcha_iframe)
                            challenge_focused = True
                except:
                    pass
            
            # Verifica se há resposta no textarea do captcha
            try:
                # Tenta encontrar textarea por name
                textarea = await page.query_selector('textarea[name="h-captcha-response"]')
                if textarea:
                    value = await textarea.input_value()
                    if value and len(value) > 0:
                        logger.info("✓ Captcha resolvido! Token encontrado no textarea (name)")
                        # Aguarda um pouco para garantir que a página processou
                        await asyncio.sleep(1)
                        return True
                
                # Tenta encontrar textarea por ID (pode variar)
                textareas = await page.query_selector_all('textarea[id*="h-captcha-response"]')
                for textarea in textareas:
                    try:
                        value = await textarea.input_value()
                        if value and len(value) > 0:
                            logger.info("✓ Captcha resolvido! Token encontrado no textarea (ID)")
                            await asyncio.sleep(1)
                            return True
                    except:
                        continue
                
                # Verifica se o atributo data-hcaptcha-response do iframe foi preenchido
                captcha_iframes = await page.query_selector_all('iframe[data-hcaptcha-widget-id]')
                for iframe in captcha_iframes:
                    try:
                        response_attr = await iframe.get_attribute('data-hcaptcha-response')
                        if response_attr and len(response_attr) > 0:
                            logger.info("✓ Captcha resolvido! Token encontrado no atributo do iframe")
                            await asyncio.sleep(1)
                            return True
                    except:
                        continue
                
                # Verifica se há mudança na página indicando que o captcha foi processado
                # Procura por mensagem de confirmação de voto
                try:
                    page_text = await page.inner_text('body')
                    if "Seu voto" in page_text or "seu voto foi registrado" in page_text.lower():
                        logger.info("✓ Captcha resolvido! Confirmação de voto detectada na página")
                        return True
                except:
                    pass
                
                # Verifica se o iframe do captcha desapareceu ou ficou invisível
                captcha_iframe = await page.query_selector('iframe[title*="hCaptcha"]')
                if captcha_iframe:
                    is_visible = await captcha_iframe.is_visible()
                    if not is_visible:
                        # Se o iframe desapareceu, verifica se há confirmação
                        try:
                            await asyncio.sleep(1)
                            page_text = await page.inner_text('body')
                            if "Seu voto" in page_text:
                                logger.info("✓ Captcha resolvido! Iframe desapareceu e confirmação detectada")
                                return True
                        except:
                            pass
                
            except Exception as e:
                logger.debug(f"Erro ao verificar captcha: {e}")
            
            # Mostra progresso a cada 10 segundos
            if int(elapsed) - last_log_time >= 10:
                remaining = int(self.timeout - elapsed)
                logger.info(f"⏳ Aguardando resolução do captcha... ({remaining}s restantes)")
                last_log_time = int(elapsed)
            
            # Aguarda um pouco antes de verificar novamente
            await asyncio.sleep(1)
    
    async def is_captcha_resolved(self, page: Page) -> bool:
        """
        Verifica se o captcha já foi resolvido
        
        Args:
            page: Página do Playwright
            
        Returns:
            True se captcha está resolvido, False caso contrário
        """
        try:
            # Verifica textarea de resposta
            textarea = await page.query_selector('textarea[name="h-captcha-response"]')
            if textarea:
                value = await textarea.input_value()
                if value and len(value) > 0:
                    return True
            
            # Verifica textareas por ID
            textareas = await page.query_selector_all('textarea[id*="h-captcha-response"]')
            for textarea in textareas:
                value = await textarea.input_value()
                if value and len(value) > 0:
                    return True
            
            return False
        except:
            return False

