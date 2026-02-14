"""
Script para coletar automaticamente imagens do captcha durante a votação
Salva todas as imagens do grid quando o captcha aparece
"""
import os
import json
import logging
import asyncio
import io
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretório para imagens não classificadas
UNCLASSIFIED_DIR = os.path.join("training_images", "unclassified")
os.makedirs(UNCLASSIFIED_DIR, exist_ok=True)


async def collect_captcha_images():
    """
    Coleta imagens do captcha automaticamente durante a votação
    """
    logger.info("=" * 60)
    logger.info("COLETOR AUTOMÁTICO DE IMAGENS DO CAPTCHA")
    logger.info("=" * 60)
    logger.info("Este script irá:")
    logger.info("1. Abrir o navegador na página de votação")
    logger.info("2. Quando aparecer o captcha, coletar automaticamente as 9 imagens")
    logger.info("3. Salvar em training_images/unclassified/")
    logger.info("4. Você pode classificar depois usando inserir_imagens_captcha.py")
    logger.info("=" * 60)
    
    # Carrega configuração
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        vote_url = config.get('vote_url')
        if not vote_url:
            logger.error("URL de votação não encontrada no config.json")
            return
    except Exception as e:
        logger.error(f"Erro ao carregar config.json: {e}")
        return
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        logger.info(f"Navegando para {vote_url}...")
        await page.goto(vote_url, wait_until='domcontentloaded')
        await asyncio.sleep(3)
        
        logger.info("\n" + "=" * 60)
        logger.info("AGUARDANDO CAPTCHA...")
        logger.info("Quando o captcha aparecer, as imagens serão coletadas automaticamente.")
        logger.info("Pressione Ctrl+C para parar.")
        logger.info("=" * 60 + "\n")
        
        collection_count = 0
        last_collection_time = 0
        
        try:
            while True:
                try:
                    # Procura pelo iframe do captcha
                    captcha_iframe = await page.query_selector('iframe[title*="hCaptcha"]')
                    
                    if captcha_iframe:
                        iframe_box = await captcha_iframe.bounding_box()
                        if iframe_box and iframe_box['height'] > 200:
                            # Desafio de imagens detectado
                            current_time = asyncio.get_event_loop().time()
                            
                            # Evita coletar múltiplas vezes do mesmo captcha (aguarda 5 segundos)
                            if current_time - last_collection_time < 5:
                                await asyncio.sleep(1)
                                continue
                            
                            logger.info("✓ Desafio de imagens detectado! Coletando...")
                            
                            # Encontra o frame do captcha
                            frames = page.frames
                            captcha_frame = None
                            for frame in frames:
                                if 'hcaptcha' in frame.url.lower():
                                    captcha_frame = frame
                                    break
                            
                            if captcha_frame:
                                # Aguarda um pouco para garantir que as imagens carregaram
                                await asyncio.sleep(2)
                                
                                # Encontra todas as imagens do grid
                                image_elements = await captcha_frame.query_selector_all('img')
                                
                                # Filtra imagens que parecem ser do grid (tamanho razoável)
                                grid_images = []
                                for img in image_elements:
                                    try:
                                        box = await img.bounding_box()
                                        if box and box['width'] > 50 and box['height'] > 50:
                                            grid_images.append(img)
                                    except:
                                        continue
                                
                                # Limita a 9 imagens (grid 3x3)
                                if len(grid_images) >= 9:
                                    grid_images = grid_images[:9]
                                    
                                    # Obtém o texto do desafio para identificar o tipo
                                    try:
                                        challenge_text = await captcha_frame.inner_text('body')
                                        challenge_type = "unknown"
                                        
                                        if 'mouse' in challenge_text.lower() or 'teclado' in challenge_text.lower() or 'itens comumente usados' in challenge_text.lower():
                                            challenge_type = "mouse"
                                        elif 'passarinho' in challenge_text.lower() or 'pássaro' in challenge_text.lower() or 'criaturas que poderiam' in challenge_text.lower():
                                            challenge_type = "passarinho"
                                        
                                        # Timestamp para nome único
                                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                        
                                        # Salva cada imagem
                                        saved_count = 0
                                        for i, img_element in enumerate(grid_images):
                                            try:
                                                screenshot_bytes = await img_element.screenshot()
                                                
                                                # Nome do arquivo: tipo_timestamp_posicao.png
                                                filename = f"{challenge_type}_{timestamp}_{i+1}.png"
                                                filepath = os.path.join(UNCLASSIFIED_DIR, filename)
                                                
                                                with open(filepath, 'wb') as f:
                                                    f.write(screenshot_bytes)
                                                
                                                saved_count += 1
                                            except Exception as e:
                                                logger.warning(f"Erro ao salvar imagem {i+1}: {e}")
                                        
                                        if saved_count == 9:
                                            collection_count += 1
                                            last_collection_time = current_time
                                            logger.info(f"✓ Grid #{collection_count} coletado! ({saved_count} imagens)")
                                            logger.info(f"  Tipo detectado: {challenge_type}")
                                            logger.info(f"  Salvas em: {UNCLASSIFIED_DIR}")
                                            logger.info(f"  Total coletado: {collection_count} grids\n")
                                        else:
                                            logger.warning(f"⚠ Apenas {saved_count}/9 imagens foram salvas")
                                    
                                    except Exception as e:
                                        logger.warning(f"Erro ao obter tipo de desafio: {e}")
                                
                                else:
                                    logger.debug(f"Aguardando grid completo... ({len(grid_images)}/9 imagens)")
                    
                    await asyncio.sleep(1)
                
                except KeyboardInterrupt:
                    logger.info("\n" + "=" * 60)
                    logger.info("Coleta interrompida pelo usuário")
                    logger.info(f"Total de grids coletados: {collection_count}")
                    logger.info(f"Imagens salvas em: {UNCLASSIFIED_DIR}")
                    logger.info("=" * 60)
                    logger.info("\nPróximo passo:")
                    logger.info("Execute: python inserir_imagens_captcha.py")
                    logger.info("Para classificar as imagens coletadas")
                    logger.info("=" * 60 + "\n")
                    break
                
                except Exception as e:
                    logger.debug(f"Erro no loop: {e}")
                    await asyncio.sleep(1)
        
        finally:
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(collect_captcha_images())
    except KeyboardInterrupt:
        logger.info("\nPrograma interrompido pelo usuário")

