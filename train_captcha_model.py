"""
Script para coletar imagens do captcha e treinar modelo de reconhecimento
"""
import os
import json
import logging
import asyncio
import numpy as np
from pathlib import Path
from PIL import Image
import cv2
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
import pickle
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretórios para armazenar imagens de treinamento
TRAIN_DIR = "training_images"
MOUSE_DIR = os.path.join(TRAIN_DIR, "mouse")
PASSARINHO_DIR = os.path.join(TRAIN_DIR, "passarinho")
NOT_MOUSE_DIR = os.path.join(TRAIN_DIR, "not_mouse")
NOT_PASSARINHO_DIR = os.path.join(TRAIN_DIR, "not_passarinho")
OTHER_DIR = os.path.join(TRAIN_DIR, "other")
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "captcha_model.pkl")

# Cria diretórios se não existirem
for dir_path in [TRAIN_DIR, MOUSE_DIR, PASSARINHO_DIR, NOT_MOUSE_DIR, NOT_PASSARINHO_DIR, OTHER_DIR, MODEL_DIR]:
    os.makedirs(dir_path, exist_ok=True)


def extract_features(image_array: np.ndarray) -> np.ndarray:
    """
    Extrai características de uma imagem para treinamento
    
    Args:
        image_array: Array numpy da imagem (RGB)
        
    Returns:
        Array de características
    """
    try:
        features = []
        
        # Converte para escala de cinza
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        
        # Redimensiona para tamanho fixo (64x64) para normalização
        resized = cv2.resize(gray, (64, 64))
        features.extend(resized.flatten())
        
        # Características adicionais
        # 1. Histograma de cores
        hist_r = cv2.calcHist([image_array], [0], None, [32], [0, 256])
        hist_g = cv2.calcHist([image_array], [1], None, [32], [0, 256])
        hist_b = cv2.calcHist([image_array], [2], None, [32], [0, 256])
        features.extend(hist_r.flatten())
        features.extend(hist_g.flatten())
        features.extend(hist_b.flatten())
        
        # 2. Características de contorno
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest_contour)
            x, y, w, h = cv2.boundingRect(largest_contour)
            aspect_ratio = w / h if h > 0 else 0
            perimeter = cv2.arcLength(largest_contour, True)
            circularity = 4 * np.pi * area / (perimeter * perimeter) if perimeter > 0 else 0
            
            features.extend([area, aspect_ratio, circularity, w, h])
        else:
            features.extend([0, 0, 0, 0, 0])
        
        # 3. Estatísticas de cor
        mean_color = np.mean(image_array, axis=(0, 1))
        std_color = np.std(image_array, axis=(0, 1))
        features.extend(mean_color)
        features.extend(std_color)
        
        return np.array(features, dtype=np.float32)
        
    except Exception as e:
        logger.error(f"Erro ao extrair características: {e}")
        return np.zeros(64*64 + 32*3 + 5 + 3 + 3)  # Retorna array de zeros com tamanho fixo


def load_training_images() -> tuple:
    """
    Carrega imagens de treinamento das pastas
    
    Returns:
        (X, y) onde X são as características e y são os labels
    """
    X = []
    y = []
    
    # Mapeamento de pastas para labels
    # Labels: 0 = mouse, 1 = passarinho, 2 = not_mouse, 3 = not_passarinho, 4 = outro
    label_map = {
        MOUSE_DIR: 0,  # 0 = mouse (deve ser selecionado quando desafio é mouse)
        PASSARINHO_DIR: 1,  # 1 = passarinho (deve ser selecionado quando desafio é passarinho)
        NOT_MOUSE_DIR: 2,  # 2 = não é mouse (NÃO deve ser selecionado quando desafio é mouse)
        NOT_PASSARINHO_DIR: 3,  # 3 = não é passarinho (NÃO deve ser selecionado quando desafio é passarinho)
        OTHER_DIR: 4  # 4 = outro
    }
    
    for folder, label in label_map.items():
        if not os.path.exists(folder):
            continue
            
        image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        logger.info(f"Carregando {len(image_files)} imagens de {folder}")
        
        for img_file in image_files:
            try:
                img_path = os.path.join(folder, img_file)
                img = Image.open(img_path)
                img_array = np.array(img.convert('RGB'))
                
                features = extract_features(img_array)
                X.append(features)
                y.append(label)
            except Exception as e:
                logger.warning(f"Erro ao carregar {img_file}: {e}")
    
    return np.array(X), np.array(y)


def train_model():
    """
    Treina o modelo de reconhecimento
    """
    logger.info("Carregando imagens de treinamento...")
    X, y = load_training_images()
    
    if len(X) == 0:
        logger.error("Nenhuma imagem de treinamento encontrada!")
        logger.info(f"Coloque imagens nas pastas:")
        logger.info(f"  - {MOUSE_DIR} (imagens de mouse)")
        logger.info(f"  - {PASSARINHO_DIR} (imagens de passarinho)")
        logger.info(f"  - {OTHER_DIR} (outras imagens)")
        return False
    
    logger.info(f"Total de imagens carregadas: {len(X)}")
    logger.info(f"  - Mouse (positivo): {np.sum(y == 0)}")
    logger.info(f"  - Passarinho (positivo): {np.sum(y == 1)}")
    logger.info(f"  - Não é Mouse (negativo): {np.sum(y == 2)}")
    logger.info(f"  - Não é Passarinho (negativo): {np.sum(y == 3)}")
    logger.info(f"  - Outros: {np.sum(y == 4)}")
    
    # Divide em treino e teste
    if len(X) > 1:
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    else:
        X_train, X_test, y_train, y_test = X, X, y, y
    
    # Treina modelo (Random Forest funciona bem para este tipo de problema)
    logger.info("Treinando modelo (Random Forest)...")
    model = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    
    # Avalia modelo
    if len(X_test) > 0:
        accuracy = model.score(X_test, y_test)
        logger.info(f"Precisão do modelo: {accuracy:.2%}")
    
    # Salva modelo
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    
    logger.info(f"Modelo salvo em {MODEL_PATH}")
    return True


async def collect_images_from_captcha():
    """
    Coleta imagens do captcha interativamente
    O usuário deve resolver o captcha manualmente e classificar as imagens
    """
    logger.info("=" * 60)
    logger.info("COLETOR DE IMAGENS DO CAPTCHA")
    logger.info("=" * 60)
    logger.info("Este script irá:")
    logger.info("1. Abrir o navegador na página de votação")
    logger.info("2. Quando aparecer o captcha, você deve resolver manualmente")
    logger.info("3. As imagens do captcha serão salvas para classificação")
    logger.info("=" * 60)
    
    # Carrega configuração
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
        vote_url = config.get('vote_url')
    except:
        logger.error("Erro ao carregar config.json")
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
        
        logger.info("Aguardando captcha aparecer...")
        logger.info("Quando o captcha aparecer, resolva-o manualmente.")
        logger.info("As imagens serão coletadas automaticamente.")
        
        collection_count = 0
        
        while True:
            try:
                # Procura pelo iframe do captcha
                captcha_iframe = await page.query_selector('iframe[title*="hCaptcha"]')
                
                if captcha_iframe:
                    iframe_box = await captcha_iframe.bounding_box()
                    if iframe_box and iframe_box['height'] > 200:
                        # Desafio de imagens detectado
                        logger.info("Desafio de imagens detectado! Coletando imagens...")
                        
                        # Encontra o frame do captcha
                        frames = page.frames
                        captcha_frame = None
                        for frame in frames:
                            if 'hcaptcha' in frame.url.lower():
                                captcha_frame = frame
                                break
                        
                        if captcha_frame:
                            # Encontra todas as imagens
                            image_elements = await captcha_frame.query_selector_all('img')
                            
                            if len(image_elements) >= 9:
                                logger.info(f"Encontradas {len(image_elements)} imagens")
                                
                                # Salva imagens temporariamente
                                temp_images = []
                                for i, img_element in enumerate(image_elements[:9]):
                                    try:
                                        screenshot_bytes = await img_element.screenshot()
                                        temp_images.append(screenshot_bytes)
                                    except:
                                        pass
                                
                                if len(temp_images) == 9:
                                    # Pergunta ao usuário qual tipo de desafio é
                                    print("\n" + "=" * 60)
                                    print("TIPO DE DESAFIO:")
                                    print("1. Mouse")
                                    print("2. Passarinho")
                                    print("3. Outro")
                                    print("=" * 60)
                                    
                                    choice = input("Escolha o tipo (1/2/3): ").strip()
                                    
                                    if choice == "1":
                                        folder = MOUSE_DIR
                                        challenge_type = "mouse"
                                    elif choice == "2":
                                        folder = PASSARINHO_DIR
                                        challenge_type = "passarinho"
                                    else:
                                        folder = OTHER_DIR
                                        challenge_type = "other"
                                    
                                    # Salva imagens
                                    for i, img_bytes in enumerate(temp_images):
                                        img_path = os.path.join(folder, f"{challenge_type}_{collection_count}_{i}.png")
                                        with open(img_path, 'wb') as f:
                                            f.write(img_bytes)
                                    
                                    collection_count += 1
                                    logger.info(f"✓ {len(temp_images)} imagens salvas em {folder}")
                                    logger.info(f"Total coletado: {collection_count} grids")
                                    
                                    print("\n" + "=" * 60)
                                    print("IMAGENS SALVAS!")
                                    print(f"Pasta: {folder}")
                                    print(f"Total de grids coletados: {collection_count}")
                                    print("=" * 60 + "\n")
                                    
                                    # Aguarda o captcha ser resolvido
                                    logger.info("Aguardando resolução do captcha...")
                                    await asyncio.sleep(5)
                                    
                                    # Verifica se foi resolvido
                                    try:
                                        textarea = await page.query_selector('textarea[name="h-captcha-response"]')
                                        if textarea:
                                            value = await textarea.input_value()
                                            if value and len(value) > 0:
                                                logger.info("✓ Captcha resolvido! Continuando...")
                                                await asyncio.sleep(3)
                                    except:
                                        pass
                
                await asyncio.sleep(2)
                
            except KeyboardInterrupt:
                logger.info("\nColeta interrompida pelo usuário")
                break
            except Exception as e:
                logger.debug(f"Erro: {e}")
                await asyncio.sleep(1)
        
        await browser.close()
        logger.info(f"\nColeta finalizada! Total de grids coletados: {collection_count}")
        logger.info(f"Imagens salvas em: {TRAIN_DIR}")


def classify_images_manually():
    """
    Permite classificar manualmente imagens já coletadas
    """
    logger.info("=" * 60)
    logger.info("CLASSIFICADOR DE IMAGENS")
    logger.info("=" * 60)
    
    # Procura por imagens não classificadas
    unclassified_dir = os.path.join(TRAIN_DIR, "unclassified")
    os.makedirs(unclassified_dir, exist_ok=True)
    
    unclassified_images = [f for f in os.listdir(unclassified_dir) 
                          if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not unclassified_images:
        logger.info("Nenhuma imagem não classificada encontrada.")
        logger.info(f"Coloque imagens em {unclassified_dir} para classificar")
        return
    
    logger.info(f"Encontradas {len(unclassified_images)} imagens para classificar")
    
    for img_file in unclassified_images:
        img_path = os.path.join(unclassified_dir, img_file)
        
        try:
            # Abre a imagem
            img = Image.open(img_path)
            img.show()
            
            print("\n" + "=" * 60)
            print(f"Imagem: {img_file}")
            print("1. Mouse")
            print("2. Passarinho")
            print("3. Outro")
            print("4. Pular")
            print("=" * 60)
            
            choice = input("Escolha (1/2/3/4): ").strip()
            
            if choice == "1":
                dest_folder = MOUSE_DIR
            elif choice == "2":
                dest_folder = PASSARINHO_DIR
            elif choice == "3":
                dest_folder = OTHER_DIR
            else:
                continue
            
            # Move imagem para pasta correta
            dest_path = os.path.join(dest_folder, img_file)
            os.rename(img_path, dest_path)
            logger.info(f"✓ {img_file} movido para {dest_folder}")
            
        except Exception as e:
            logger.error(f"Erro ao processar {img_file}: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "collect":
            # Coleta imagens do captcha
            asyncio.run(collect_images_from_captcha())
        elif command == "classify":
            # Classifica imagens manualmente
            classify_images_manually()
        elif command == "train":
            # Treina o modelo
            train_model()
        else:
            print("Comandos disponíveis:")
            print("  python train_captcha_model.py collect  - Coleta imagens do captcha")
            print("  python train_captcha_model.py classify  - Classifica imagens manualmente")
            print("  python train_captcha_model.py train    - Treina o modelo")
    else:
        print("=" * 60)
        print("SISTEMA DE TREINAMENTO DE CAPTCHA")
        print("=" * 60)
        print("\nComandos disponíveis:")
        print("  1. python train_captcha_model.py collect  - Coleta imagens do captcha automaticamente")
        print("  2. python train_captcha_model.py classify - Classifica imagens manualmente")
        print("  3. python train_captcha_model.py train   - Treina o modelo com as imagens coletadas")
        print("\nFluxo recomendado:")
        print("  1. Execute 'collect' para coletar imagens do captcha")
        print("  2. Execute 'classify' se precisar classificar manualmente")
        print("  3. Execute 'train' para treinar o modelo")
        print("  4. O modelo treinado será usado automaticamente pelo bot")
        print("=" * 60)

