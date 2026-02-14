"""
Módulo para reconhecimento de imagens em captchas
Detecta mouse e passarinho em grids de imagens
"""
import os
import logging
import numpy as np
from PIL import Image
import cv2
import pickle

logger = logging.getLogger(__name__)

# Caminho do modelo treinado
MODEL_PATH = os.path.join("models", "captcha_model.pkl")
TRAINED_MODEL = None


def load_trained_model():
    """
    Carrega modelo treinado se existir
    
    Returns:
        Modelo treinado ou None se não existir
    """
    global TRAINED_MODEL
    if TRAINED_MODEL is not None:
        return TRAINED_MODEL
    
    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, 'rb') as f:
                TRAINED_MODEL = pickle.load(f)
            logger.info(f"Modelo treinado carregado de {MODEL_PATH}")
            return TRAINED_MODEL
        except Exception as e:
            logger.warning(f"Erro ao carregar modelo treinado: {e}")
    
    return None


def extract_features(image_array: np.ndarray) -> np.ndarray:
    """
    Extrai características de uma imagem (mesma função usada no treinamento)
    
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
        
        # Histograma de cores
        hist_r = cv2.calcHist([image_array], [0], None, [32], [0, 256])
        hist_g = cv2.calcHist([image_array], [1], None, [32], [0, 256])
        hist_b = cv2.calcHist([image_array], [2], None, [32], [0, 256])
        features.extend(hist_r.flatten())
        features.extend(hist_g.flatten())
        features.extend(hist_b.flatten())
        
        # Características de contorno
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
        
        # Estatísticas de cor
        mean_color = np.mean(image_array, axis=(0, 1))
        std_color = np.std(image_array, axis=(0, 1))
        features.extend(mean_color)
        features.extend(std_color)
        
        return np.array(features, dtype=np.float32)
        
    except Exception as e:
        logger.error(f"Erro ao extrair características: {e}")
        return np.zeros(64*64 + 32*3 + 5 + 3 + 3)


def detect_challenge_type(page_text: str) -> str:
    """
    Detecta o tipo de desafio do captcha baseado no texto
    
    Args:
        page_text: Texto da página ou do iframe do captcha
        
    Returns:
        'mouse' ou 'passarinho' ou None se não detectado
    """
    page_text_lower = page_text.lower()
    
    # Padrões para mouse
    mouse_patterns = [
        'itens comumente usados com o item mostrado',
        'itens comumente usados',
        'mouse',
        'teclado',
        'computador'
    ]
    
    # Padrões para passarinho
    passarinho_patterns = [
        'criaturas que poderiam se abrigar',
        'criaturas que poderiam',
        'passarinho',
        'pássaro',
        'ave',
        'bird'
    ]
    
    # Verifica padrões de mouse
    for pattern in mouse_patterns:
        if pattern in page_text_lower:
            logger.info(f"Tipo de desafio detectado: MOUSE (padrão: '{pattern}')")
            return 'mouse'
    
    # Verifica padrões de passarinho
    for pattern in passarinho_patterns:
        if pattern in page_text_lower:
            logger.info(f"Tipo de desafio detectado: PASSARINHO (padrão: '{pattern}')")
            return 'passarinho'
    
    logger.warning("Tipo de desafio não detectado no texto")
    return None


def detect_mouse_in_image(image_array: np.ndarray) -> bool:
    """
    Detecta se uma imagem contém um mouse de computador
    Usa modelo treinado se disponível, senão usa detecção por características
    
    Args:
        image_array: Array numpy da imagem (RGB)
        
    Returns:
        True se detectou mouse, False caso contrário
    """
    # Tenta usar modelo treinado primeiro
    model = load_trained_model()
    if model is not None:
        try:
            features = extract_features(image_array)
            features = features.reshape(1, -1)
            prediction = model.predict(features)[0]
            # 0 = mouse, 1 = passarinho, 2 = outro
            if prediction == 0:
                logger.debug("Mouse detectado usando modelo treinado")
                return True
            else:
                return False
        except Exception as e:
            logger.debug(f"Erro ao usar modelo treinado: {e}, usando detecção por características")
    
    # Fallback para detecção por características
    try:
        # Converte para escala de cinza
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        
        # Aplica threshold para destacar formas
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Encontra contornos
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return False
        
        # Encontra o maior contorno (provavelmente o objeto principal)
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Calcula características do contorno
        area = cv2.contourArea(largest_contour)
        x, y, w, h = cv2.boundingRect(largest_contour)
        aspect_ratio = w / h if h > 0 else 0
        
        # Mouse geralmente tem:
        # - Aspect ratio > 1 (mais largo que alto)
        # - Forma alongada
        # - Tamanho razoável (não muito pequeno)
        image_area = image_array.shape[0] * image_array.shape[1]
        area_ratio = area / image_area if image_area > 0 else 0
        
        # Verifica características de mouse
        is_elongated = aspect_ratio > 1.2 and aspect_ratio < 3.0
        has_reasonable_size = area_ratio > 0.1 and area_ratio < 0.8
        
        # Verifica se há linhas (possível cabo do mouse)
        edges = cv2.Canny(gray, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=20, maxLineGap=10)
        
        has_lines = lines is not None and len(lines) > 0
        
        # Mouse geralmente tem linhas (cabo) e formato alongado
        if is_elongated and has_reasonable_size:
            if has_lines:
                logger.debug("Mouse detectado: formato alongado com linhas (cabo)")
                return True
            # Mesmo sem linhas claras, formato alongado pode ser mouse
            if aspect_ratio > 1.5:
                logger.debug("Mouse detectado: formato alongado")
                return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Erro ao detectar mouse: {e}")
        return False


def detect_passarinho_in_image(image_array: np.ndarray) -> bool:
    """
    Detecta se uma imagem contém um passarinho/pássaro
    Usa modelo treinado se disponível, senão usa detecção por características
    
    Args:
        image_array: Array numpy da imagem (RGB)
        
    Returns:
        True se detectou passarinho, False caso contrário
    """
    # Tenta usar modelo treinado primeiro
    model = load_trained_model()
    if model is not None:
        try:
            features = extract_features(image_array)
            features = features.reshape(1, -1)
            prediction = model.predict(features)[0]
            # 0 = mouse, 1 = passarinho, 2 = outro
            if prediction == 1:
                logger.debug("Passarinho detectado usando modelo treinado")
                return True
            else:
                return False
        except Exception as e:
            logger.debug(f"Erro ao usar modelo treinado: {e}, usando detecção por características")
    
    # Fallback para detecção por características
    try:
        # Converte para escala de cinza
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        
        # Aplica threshold
        _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Encontra contornos
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return False
        
        # Encontra o maior contorno
        largest_contour = max(contours, key=cv2.contourArea)
        
        # Calcula características
        area = cv2.contourArea(largest_contour)
        x, y, w, h = cv2.boundingRect(largest_contour)
        aspect_ratio = w / h if h > 0 else 0
        
        # Calcula circularidade (passarinho geralmente é mais arredondado)
        perimeter = cv2.arcLength(largest_contour, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter * perimeter)
        else:
            circularity = 0
        
        image_area = image_array.shape[0] * image_array.shape[1]
        area_ratio = area / image_area if image_area > 0 else 0
        
        # Passarinho geralmente tem:
        # - Aspect ratio próximo de 1 (mais quadrado/redondo)
        # - Circularidade maior (mais arredondado)
        # - Tamanho pequeno a médio
        is_rounded = aspect_ratio > 0.7 and aspect_ratio < 1.5
        is_circular = circularity > 0.3
        has_reasonable_size = area_ratio > 0.05 and area_ratio < 0.6
        
        # Verifica cores típicas de passarinho (marrom, bege, branco)
        # Converte para HSV para melhor detecção de cor
        hsv = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
        
        # Define ranges para cores de passarinho (marrom, bege)
        # H: 0-30 (tons de marrom/bege)
        # S: 50-255 (saturação)
        # V: 50-255 (brilho)
        brown_lower = np.array([0, 50, 50])
        brown_upper = np.array([30, 255, 255])
        brown_mask = cv2.inRange(hsv, brown_lower, brown_upper)
        brown_ratio = np.sum(brown_mask > 0) / (image_array.shape[0] * image_array.shape[1])
        
        # Verifica se tem características de passarinho
        if is_rounded and has_reasonable_size:
            if is_circular:
                logger.debug("Passarinho detectado: formato arredondado e circular")
                return True
            if brown_ratio > 0.1:  # Tem cores de passarinho
                logger.debug("Passarinho detectado: formato arredondado com cores típicas")
                return True
            # Mesmo sem circularidade alta, formato arredondado pode ser passarinho
            if aspect_ratio > 0.8 and aspect_ratio < 1.3:
                logger.debug("Passarinho detectado: formato arredondado")
                return True
        
        return False
        
    except Exception as e:
        logger.debug(f"Erro ao detectar passarinho: {e}")
        return False


def detect_not_mouse_in_image(image_array: np.ndarray) -> bool:
    """
    Detecta se uma imagem NÃO é um mouse (usando modelo treinado)
    
    Args:
        image_array: Array numpy da imagem (RGB)
        
    Returns:
        True se detectou que NÃO é mouse, False caso contrário
    """
    model = load_trained_model()
    if model is not None:
        try:
            features = extract_features(image_array)
            features = features.reshape(1, -1)
            prediction = model.predict(features)[0]
            # 2 = not_mouse, 3 = not_passarinho
            if prediction == 2:
                logger.debug("Imagem identificada como 'não é mouse' usando modelo")
                return True
        except Exception as e:
            logger.debug(f"Erro ao usar modelo para 'não é mouse': {e}")
    return False


def detect_not_passarinho_in_image(image_array: np.ndarray) -> bool:
    """
    Detecta se uma imagem NÃO é um passarinho (usando modelo treinado)
    
    Args:
        image_array: Array numpy da imagem (RGB)
        
    Returns:
        True se detectou que NÃO é passarinho, False caso contrário
    """
    model = load_trained_model()
    if model is not None:
        try:
            features = extract_features(image_array)
            features = features.reshape(1, -1)
            prediction = model.predict(features)[0]
            # 2 = not_mouse, 3 = not_passarinho
            if prediction == 3:
                logger.debug("Imagem identificada como 'não é passarinho' usando modelo")
                return True
        except Exception as e:
            logger.debug(f"Erro ao usar modelo para 'não é passarinho': {e}")
    return False


def process_image_grid(images: list, challenge_type: str) -> list:
    """
    Processa um grid de imagens e retorna índices das imagens corretas
    Usa exemplos negativos para melhorar a precisão
    
    Args:
        images: Lista de arrays numpy das imagens (9 imagens para grid 3x3)
        challenge_type: Tipo de desafio ('mouse' ou 'passarinho')
        
    Returns:
        Lista de índices (0-8) das imagens que correspondem ao desafio
    """
    correct_indices = []
    
    if challenge_type == 'mouse':
        detect_positive = detect_mouse_in_image
        detect_negative = detect_not_mouse_in_image
    elif challenge_type == 'passarinho':
        detect_positive = detect_passarinho_in_image
        detect_negative = detect_not_passarinho_in_image
    else:
        logger.warning(f"Tipo de desafio desconhecido: {challenge_type}")
        return []
    
    for i, image_array in enumerate(images):
        try:
            # Primeiro verifica se é negativo (não deve ser selecionado)
            if detect_negative(image_array):
                logger.debug(f"Imagem {i} identificada como NÃO é {challenge_type} - não será selecionada")
                continue
            
            # Se não é negativo, verifica se é positivo (deve ser selecionado)
            if detect_positive(image_array):
                correct_indices.append(i)
                logger.debug(f"Imagem {i} identificada como {challenge_type}")
        except Exception as e:
            logger.debug(f"Erro ao processar imagem {i}: {e}")
            continue
    
    logger.info(f"Total de imagens corretas identificadas: {len(correct_indices)}/{len(images)}")
    return correct_indices

