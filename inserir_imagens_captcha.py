"""
Script simplificado para inserir e classificar imagens do captcha manualmente
"""
import os
import shutil
import logging
from pathlib import Path
from PIL import Image
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Diretórios para armazenar imagens de treinamento
TRAIN_DIR = "training_images"
MOUSE_DIR = os.path.join(TRAIN_DIR, "mouse")
PASSARINHO_DIR = os.path.join(TRAIN_DIR, "passarinho")
OTHER_DIR = os.path.join(TRAIN_DIR, "other")
NOT_MOUSE_DIR = os.path.join(TRAIN_DIR, "not_mouse")  # Imagens que NÃO são mouse
NOT_PASSARINHO_DIR = os.path.join(TRAIN_DIR, "not_passarinho")  # Imagens que NÃO são passarinho
UNCLASSIFIED_DIR = os.path.join(TRAIN_DIR, "unclassified")

# Cria diretórios se não existirem
for dir_path in [TRAIN_DIR, MOUSE_DIR, PASSARINHO_DIR, OTHER_DIR, NOT_MOUSE_DIR, NOT_PASSARINHO_DIR, UNCLASSIFIED_DIR]:
    os.makedirs(dir_path, exist_ok=True)


class ImageClassifier:
    """Interface gráfica para classificar imagens do captcha"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Classificador de Imagens - Captcha BBB")
        self.root.geometry("800x700")
        
        self.current_image_path = None
        self.current_image = None
        self.image_files = []
        self.current_index = 0
        
        self.setup_ui()
        self.load_unclassified_images()
    
    def setup_ui(self):
        """Configura a interface gráfica"""
        # Título
        title_frame = tk.Frame(self.root)
        title_frame.pack(pady=10)
        
        title_label = tk.Label(
            title_frame, 
            text="Classificador de Imagens do Captcha",
            font=("Arial", 16, "bold")
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_frame,
            text="Cole as imagens nesta pasta:",
            font=("Arial", 9),
            fg="gray"
        )
        subtitle_label.pack()
        
        # Mostra caminho da pasta (clicável para abrir)
        path_text = os.path.abspath(UNCLASSIFIED_DIR)
        path_label = tk.Label(
            title_frame,
            text=path_text,
            font=("Arial", 8),
            fg="blue",
            cursor="hand2"
        )
        path_label.pack()
        path_label.bind("<Button-1>", lambda e: os.startfile(os.path.abspath(UNCLASSIFIED_DIR)))
        
        # Frame para imagem
        image_frame = tk.Frame(self.root, bg="white", relief=tk.SUNKEN, borderwidth=2)
        image_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.image_label = tk.Label(
            image_frame,
            text="Nenhuma imagem carregada",
            bg="white",
            font=("Arial", 12)
        )
        self.image_label.pack(expand=True)
        
        # Informações
        info_frame = tk.Frame(self.root)
        info_frame.pack(pady=5)
        
        self.info_label = tk.Label(
            info_frame,
            text="",
            font=("Arial", 10)
        )
        self.info_label.pack()
        
        # Botões de classificação
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        # Botão Mouse
        mouse_btn = tk.Button(
            button_frame,
            text="🖱️ MOUSE",
            command=lambda: self.classify_image("mouse"),
            bg="#4CAF50",
            fg="white",
            font=("Arial", 12, "bold"),
            width=15,
            height=2
        )
        mouse_btn.pack(side=tk.LEFT, padx=10)
        
        # Botão Passarinho
        passarinho_btn = tk.Button(
            button_frame,
            text="🐦 PASSARINHO",
            command=lambda: self.classify_image("passarinho"),
            bg="#2196F3",
            fg="white",
            font=("Arial", 12, "bold"),
            width=15,
            height=2
        )
        passarinho_btn.pack(side=tk.LEFT, padx=10)
        
        # Botão Outro
        other_btn = tk.Button(
            button_frame,
            text="❌ OUTRO",
            command=lambda: self.classify_image("other"),
            bg="#FF9800",
            fg="white",
            font=("Arial", 12, "bold"),
            width=15,
            height=2
        )
        other_btn.pack(side=tk.LEFT, padx=10)
        
        # Frame para botões de "não selecionar"
        negative_frame = tk.Frame(self.root)
        negative_frame.pack(pady=10)
        
        negative_label = tk.Label(
            negative_frame,
            text="Imagens que NÃO devem ser selecionadas:",
            font=("Arial", 9),
            fg="gray"
        )
        negative_label.pack()
        
        negative_buttons_frame = tk.Frame(negative_frame)
        negative_buttons_frame.pack(pady=5)
        
        # Botão NÃO é Mouse
        not_mouse_btn = tk.Button(
            negative_buttons_frame,
            text="🚫 NÃO É MOUSE",
            command=lambda: self.classify_image("not_mouse"),
            bg="#F44336",
            fg="white",
            font=("Arial", 10, "bold"),
            width=18,
            height=1
        )
        not_mouse_btn.pack(side=tk.LEFT, padx=5)
        
        # Botão NÃO é Passarinho
        not_passarinho_btn = tk.Button(
            negative_buttons_frame,
            text="🚫 NÃO É PASSARINHO",
            command=lambda: self.classify_image("not_passarinho"),
            bg="#E91E63",
            fg="white",
            font=("Arial", 10, "bold"),
            width=18,
            height=1
        )
        not_passarinho_btn.pack(side=tk.LEFT, padx=5)
        
        # Botões de navegação
        nav_frame = tk.Frame(self.root)
        nav_frame.pack(pady=10)
        
        prev_btn = tk.Button(
            nav_frame,
            text="◀ Anterior",
            command=self.prev_image,
            font=("Arial", 10),
            width=12
        )
        prev_btn.pack(side=tk.LEFT, padx=5)
        
        skip_btn = tk.Button(
            nav_frame,
            text="⏭ Pular",
            command=self.skip_image,
            font=("Arial", 10),
            width=12
        )
        skip_btn.pack(side=tk.LEFT, padx=5)
        
        next_btn = tk.Button(
            nav_frame,
            text="Próximo ▶",
            command=self.next_image,
            font=("Arial", 10),
            width=12
        )
        next_btn.pack(side=tk.LEFT, padx=5)
        
        # Botões de ação
        action_frame = tk.Frame(self.root)
        action_frame.pack(pady=10)
        
        import_btn = tk.Button(
            action_frame,
            text="📁 Importar de Pasta",
            command=self.import_images,
            font=("Arial", 10),
            width=18
        )
        import_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_btn = tk.Button(
            action_frame,
            text="🔄 Atualizar",
            command=self.load_unclassified_images,
            font=("Arial", 10),
            width=18
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        help_btn = tk.Button(
            action_frame,
            text="❓ Ajuda",
            command=self.import_from_clipboard,
            font=("Arial", 10),
            width=18
        )
        help_btn.pack(side=tk.LEFT, padx=5)
        
        stats_btn = tk.Button(
            action_frame,
            text="📊 Estatísticas",
            command=self.show_stats,
            font=("Arial", 10),
            width=18
        )
        stats_btn.pack(side=tk.LEFT, padx=5)
    
    def load_unclassified_images(self):
        """Carrega imagens não classificadas"""
        if not os.path.exists(UNCLASSIFIED_DIR):
            return
        
        self.image_files = [
            f for f in os.listdir(UNCLASSIFIED_DIR)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))
        ]
        
        if self.image_files:
            self.current_index = 0
            self.load_current_image()
        else:
            self.image_label.config(
                text="Nenhuma imagem não classificada encontrada.\n\nClique em 'Importar Imagens' para adicionar.",
                image=""
            )
            self.info_label.config(text="")
    
    def load_current_image(self):
        """Carrega a imagem atual"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return
        
        self.current_image_path = os.path.join(UNCLASSIFIED_DIR, self.image_files[self.current_index])
        
        try:
            # Carrega e redimensiona imagem
            img = Image.open(self.current_image_path)
            
            # Redimensiona mantendo proporção (max 600x600)
            max_size = 600
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Converte para PhotoImage
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
            
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Mantém referência
            
            # Atualiza informações
            total = len(self.image_files)
            self.info_label.config(
                text=f"Imagem {self.current_index + 1} de {total} | {self.image_files[self.current_index]}"
            )
            
        except Exception as e:
            logger.error(f"Erro ao carregar imagem: {e}")
            messagebox.showerror("Erro", f"Erro ao carregar imagem: {e}")
    
    def classify_image(self, category: str):
        """Classifica a imagem atual"""
        if not self.current_image_path:
            return
        
        try:
            # Determina pasta de destino
            if category == "mouse":
                dest_dir = MOUSE_DIR
            elif category == "passarinho":
                dest_dir = PASSARINHO_DIR
            elif category == "not_mouse":
                dest_dir = NOT_MOUSE_DIR
            elif category == "not_passarinho":
                dest_dir = NOT_PASSARINHO_DIR
            else:
                dest_dir = OTHER_DIR
            
            # Move imagem para pasta correta
            filename = os.path.basename(self.current_image_path)
            dest_path = os.path.join(dest_dir, filename)
            
            # Se já existe, adiciona número
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(dest_path):
                new_filename = f"{base_name}_{counter}{ext}"
                dest_path = os.path.join(dest_dir, new_filename)
                counter += 1
            
            shutil.move(self.current_image_path, dest_path)
            logger.info(f"Imagem movida: {filename} -> {dest_dir}")
            
            # Remove da lista
            self.image_files.pop(self.current_index)
            
            # Ajusta índice se necessário
            if self.current_index >= len(self.image_files):
                self.current_index = max(0, len(self.image_files) - 1)
            
            # Carrega próxima imagem
            if self.image_files:
                self.load_current_image()
            else:
                self.image_label.config(
                    text="✓ Todas as imagens foram classificadas!\n\nImporte mais imagens para continuar.",
                    image=""
                )
                self.info_label.config(text="")
                messagebox.showinfo("Sucesso", "Todas as imagens foram classificadas!")
        
        except Exception as e:
            logger.error(f"Erro ao classificar imagem: {e}")
            messagebox.showerror("Erro", f"Erro ao classificar imagem: {e}")
    
    def prev_image(self):
        """Vai para imagem anterior"""
        if self.image_files:
            self.current_index = max(0, self.current_index - 1)
            self.load_current_image()
    
    def next_image(self):
        """Vai para próxima imagem"""
        if self.image_files:
            self.current_index = min(len(self.image_files) - 1, self.current_index + 1)
            self.load_current_image()
    
    def skip_image(self):
        """Pula imagem atual (mantém não classificada)"""
        if self.image_files:
            self.next_image()
    
    def import_images(self):
        """Importa imagens de uma pasta"""
        folder = filedialog.askdirectory(title="Selecione pasta com imagens do captcha")
        
        if not folder:
            return
        
        try:
            imported = 0
            image_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
            
            for filename in os.listdir(folder):
                if filename.lower().endswith(image_extensions):
                    src_path = os.path.join(folder, filename)
                    dest_path = os.path.join(UNCLASSIFIED_DIR, filename)
                    
                    # Se já existe, adiciona número
                    counter = 1
                    base_name, ext = os.path.splitext(filename)
                    while os.path.exists(dest_path):
                        new_filename = f"{base_name}_{counter}{ext}"
                        dest_path = os.path.join(UNCLASSIFIED_DIR, new_filename)
                        counter += 1
                    
                    shutil.copy2(src_path, dest_path)
                    imported += 1
            
            messagebox.showinfo("Sucesso", f"{imported} imagem(ns) importada(s)!")
            self.load_unclassified_images()
        
        except Exception as e:
            logger.error(f"Erro ao importar imagens: {e}")
            messagebox.showerror("Erro", f"Erro ao importar imagens: {e}")
    
    def import_from_clipboard(self):
        """Importa imagens da área de transferência ou permite colar na pasta"""
        messagebox.showinfo(
            "Como Importar Imagens",
            "Para inserir imagens manualmente:\n\n"
            "1. Copie as imagens do captcha (screenshots ou imagens salvas)\n"
            "2. Cole as imagens na pasta:\n"
            f"   {os.path.abspath(UNCLASSIFIED_DIR)}\n\n"
            "OU\n\n"
            "3. Use o botão 'Importar Imagens' para selecionar uma pasta\n\n"
            "Depois clique em 'Atualizar' para ver as novas imagens."
        )
    
    def show_stats(self):
        """Mostra estatísticas das imagens classificadas"""
        try:
            mouse_count = len([f for f in os.listdir(MOUSE_DIR) 
                              if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists(MOUSE_DIR) else 0
            passarinho_count = len([f for f in os.listdir(PASSARINHO_DIR) 
                                   if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists(PASSARINHO_DIR) else 0
            not_mouse_count = len([f for f in os.listdir(NOT_MOUSE_DIR) 
                                  if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists(NOT_MOUSE_DIR) else 0
            not_passarinho_count = len([f for f in os.listdir(NOT_PASSARINHO_DIR) 
                                       if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists(NOT_PASSARINHO_DIR) else 0
            other_count = len([f for f in os.listdir(OTHER_DIR) 
                              if f.lower().endswith(('.png', '.jpg', '.jpeg'))]) if os.path.exists(OTHER_DIR) else 0
            unclassified_count = len(self.image_files)
            
            total = mouse_count + passarinho_count + not_mouse_count + not_passarinho_count + other_count + unclassified_count
            
            stats_text = f"""ESTATÍSTICAS DE IMAGENS

IMAGENS POSITIVAS (devem ser selecionadas):
📁 Mouse: {mouse_count} imagens
🐦 Passarinho: {passarinho_count} imagens

IMAGENS NEGATIVAS (NÃO devem ser selecionadas):
🚫 Não é Mouse: {not_mouse_count} imagens
🚫 Não é Passarinho: {not_passarinho_count} imagens

OUTRAS:
❌ Outros: {other_count} imagens
📋 Não classificadas: {unclassified_count} imagens

TOTAL: {total} imagens

Recomendação: 
- Colete 50-100 imagens positivas de cada tipo
- Colete também imagens negativas para melhorar a precisão"""
            
            messagebox.showinfo("Estatísticas", stats_text)
        
        except Exception as e:
            logger.error(f"Erro ao calcular estatísticas: {e}")
            messagebox.showerror("Erro", f"Erro ao calcular estatísticas: {e}")


def main():
    """Função principal"""
    root = tk.Tk()
    app = ImageClassifier(root)
    root.mainloop()


if __name__ == "__main__":
    main()

