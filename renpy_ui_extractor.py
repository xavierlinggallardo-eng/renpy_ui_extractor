#!/usr/bin/env python3
"""
Renpy UI Extractor + Auto-Translate
====================================
Extrae y traduce textos de UI/menús/screens que Zenpy NO traduce.

Interfaz GUI: python renpy_ui_extractor.py --gui

Motores disponibles:
  - DeepLX (--deeplx) - Completamente gratis, sin API key
  - DeepL (--deepl KEY) - Mejor calidad, 500k chars/mes gratis
  - Google (--google) - Completamente gratis

Usage:
    python renpy_ui_extractor.py --gui          # GUI
    python renpy_ui_extractor.py "path/to/game" "es" --deeplx
    python renpy_ui_extractor.py "path/to/game" "es" --google
    python renpy_ui_extractor.py "path/to/game" "es" --deepl TU_KEY
"""

import os
import re
import sys
import time
import argparse
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# DeepL
try:
    import deepl
    DEEPL_OK = True
except ImportError:
    DEEPL_OK = False

# Google Translate (gratuito)
try:
    from googletrans import Translator as GoogleTranslator
    GOOGLE_OK = True
except ImportError:
    GOOGLE_OK = False


LANG_MAP = {
    'es': 'ES', 'en': 'EN-US', 'fr': 'FR', 'de': 'DE', 'it': 'IT',
    'pt': 'PT-BR', 'ja': 'JA', 'ko': 'KO', 'zh': 'ZH', 'ru': 'RU'
}

GOOGLE_LANG_MAP = {
    'es': 'es', 'en': 'en', 'fr': 'fr', 'de': 'de', 'it': 'it',
    'pt': 'pt', 'ja': 'ja', 'ko': 'ko', 'zh': 'zh', 'ru': 'ru'
}

DEEPLX_ENDPOINT = "http://localhost:1188/translate"

DEEPLX_LANG_MAP = {
    'es': 'ES', 'en': 'EN', 'fr': 'FR', 'de': 'DE', 'it': 'IT',
    'pt': 'PT', 'ja': 'JA', 'ko': 'KO', 'zh': 'ZH', 'ru': 'RU'
}


class RenpyUIExtractor:
    """Extrae textos de UI/menús/screens"""
    
    IGNORE = [r'^skip$', r'^auto$', r'^yes$', r'^no$', r'^true$', 
            r'^false$', r'^None$', r'^\d+$', r'^[\[\]{}!@#$%^&*()_+=|<>?]+$']
    
    def __init__(self, game_path):
        self.game_path = Path(game_path).resolve()
        self.results = {}
        self.stats = {'files': 0, 'texts': 0}
    
    def extract(self):
        print(f"Buscando en: {self.game_path}")
        game_dir = self.game_path / "game"
        if not game_dir.exists():
            print(f"ERROR: No found 'game' folder")
            return {}
        
        rpy_files = list(game_dir.rglob("*.rpy"))
        print(f"Encontrados {len(rpy_files)} archivos .rpy")
        
        for fp in rpy_files:
            self._process_file(fp)
            self.stats['files'] += 1
        
        print(f"Archivos: {self.stats['files']} | Textos: {self.stats['texts']}")
        return self.results
    
    def _process_file(self, fp):
        try:
            with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                c = f.read()
        except:
            return
        
        rel = str(fp.relative_to(self.game_path))
        
        # textbutton (botones)
        for m in re.finditer(r'textbutton\s+"([^"]+)"', c):
            self._add(m.group(1), rel, 'textbutton')
        
        # menu opciones
        for m in re.finditer(r'^\s*"([^"]+)"\s*:(?:\s|#|$|\n)', c, re.MULTILINE):
            self._add(m.group(1), rel, 'menu')
        
        # screens
        for m in re.finditer(r'^screen\s+(\w+)', c, re.MULTILINE):
            self._extract_screen(c, m.end(), rel, m.group(1))
        
        # add/show text=
        for m in re.finditer(r'(?:add|show)\s+["\']?\w+["\']?\s*,\s*.*?text\s*=\s*"([^"]+)"', c):
            self._add(m.group(1), rel, 'add_text')
        
        # screen text lines
        for m in re.finditer(r'^\s+(text|label|hbox|vbox)\s+"([^"]+)"', c, re.MULTILINE):
            if len(m.group(2)) > 2:
                self._add(m.group(2), rel, 'screen')
    
    def _extract_screen(self, c, pos, rel, sn):
        lines = c[pos:].split('\n')
        indent = None
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                break
        if indent is None:
            return
        
        for line in lines:
            if not line.strip():
                continue
            cur = len(line) - len(line.lstrip())
            if cur <= indent:
                break
            
            for m in re.finditer(r'textbutton\s+"([^"]+)"', line):
                self._add(m.group(1), rel, f'screen_{sn}')
            for m in re.finditer(r'text\s+"([^"]+)"', line):
                if len(m.group(1)) > 2:
                    self._add(m.group(1), rel, f'screen_{sn}')
            for m in re.finditer(r'label\s+"([^"]+)"', line):
                self._add(m.group(1), rel, f'screen_{sn}')
    
    def _add(self, text, src, typ):
        text = text.strip()
        if not text or len(text) < 2:
            return
        
        for p in self.IGNORE:
            if re.match(p, text, re.IGNORECASE):
                return
        
        key = text.lower().strip()
        if key not in self.results:
            self.results[key] = {'original': text, 'source': src, 'type': typ, 'translated': ''}
            self.stats['texts'] += 1


class DeepLTranslator:
    """Traductor DeepL (API de pago con plan gratuito)"""
    
    def __init__(self, api_key):
        self.translator = deepl.Translator(api_key)
    
    def translate(self, texts, target_lang):
        results = {}
        target = LANG_MAP.get(target_lang, target_lang.upper())
        
        print(f"Traduciendo {len(texts)} textos con DeepL...")
        
        for i, text in enumerate(texts):
            try:
                result = self.translator.translate_text(
                    text, source_lang='EN', target_lang=target
                )
                results[text] = result.text
                
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(texts)}")
                
                time.sleep(0.02)
                
            except Exception as e:
                print(f"Error: {e}")
                results[text] = text
        
        return results


class DeepLXTranslator:
    """Traductor DeepLX gratuito (sin API key)"""
    
    def __init__(self, endpoint=None):
        self.endpoint = endpoint or DEEPLX_ENDPOINT
        print(f"Usando DeepLX: {self.endpoint}")
    
    def translate(self, texts, target_lang):
        import urllib.request
        import urllib.parse
        import json
        
        results = {}
        target = DEEPLX_LANG_MAP.get(target_lang, target_lang.upper())
        
        print(f"Traduciendo {len(texts)} textos con DeepLX (gratis)...")
        
        for i, text in enumerate(texts):
            try:
                data = json.dumps({
                    "text": text,
                    "source_lang": "EN",
                    "target_lang": target
                }).encode('utf-8')
                
                req = urllib.request.Request(
                    self.endpoint,
                    data=data,
                    headers={'Content-Type': 'application/json'}
                )
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    result = json.loads(response.read())
                    if result.get('code') == 200:
                        results[text] = result.get('data', text)
                    else:
                        results[text] = text
                
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(texts)}")
                
                time.sleep(0.3)  # Rate limit
                
            except Exception as e:
                print(f"Error: {e}")
                results[text] = text
        
        return results


class GoogleTranslatorFree:
    """Traductor Google Gratuito (sin API key)"""
    
    def __init__(self):
        self.translator = GoogleTranslator()
    
    def translate(self, texts, target_lang):
        results = {}
        target = GOOGLE_LANG_MAP.get(target_lang, target_lang)
        
        print(f"Traduciendo {len(texts)} textos con Google (gratis)...")
        
        for i, text in enumerate(texts):
            try:
                result = self.translator.translate(text, dest=target, src='en')
                results[text] = result.text
                
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(texts)}")
                
                # Rate limit para evitar bloqueo
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error: {e}")
                results[text] = text
        
        return results


def generate_translation_file(results, out_path, lang):
    """Genera archivo de traducción Ren'Py"""
    
    if not results:
        print("No texts found")
        return
    
    lines = [
        f"# Extra translation strings - {lang}",
        f"# Generated by Renpy UI Extractor",
        f"# Total: {len(results)}",
        "",
        f"translate {lang} strings:",
        ""
    ]
    
    for key, data in sorted(results.items()):
        orig = data['original'].replace('\\', '\\\\').replace('"', '\\"')
        trans = data.get('translated', '') or orig
        lines.append(f'    old "{orig}"')
        lines.append(f'    new "{trans}"')
        lines.append("")
    
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"Generado: {out}")
    return out


class GUIController:
    def __init__(self, root):
        self.root = root
        self.root.title("Renpy UI Extractor")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.game_path = tk.StringVar(value=os.getcwd())
        self.target_lang = tk.StringVar(value="es")
        self.engine = tk.StringVar(value="deeplx")
        self.deeplx_endpoint = tk.StringVar(value=DEEPLX_ENDPOINT)
        self.status = tk.StringVar(value="Listo")
        self.progress = tk.DoubleVar(value=0)
        
        self._build_ui()
    
    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="📁 Ruta del Juego:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0,5))
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0,15))
        ttk.Entry(path_frame, textvariable=self.game_path, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="📂", command=self._browse_folder, width=5).pack(side=tk.LEFT, padx=(5,0))
        
        ttk.Label(main_frame, text="🌍 Idioma objetivo:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0,5))
        lang_frame = ttk.Frame(main_frame)
        lang_frame.pack(fill=tk.X, pady=(0,15))
        for code, name in [("es","Español"),("en","English"),("fr","Français"),("de","Deutsch"),("it","Italiano"),("pt","Português"),("ja","日本語"),("ko","한국어"),("zh","中文")]:
            ttk.Radiobutton(lang_frame, text=name, value=code, variable=self.target_lang).pack(side=tk.LEFT, padx=5)
        
        ttk.Label(main_frame, text="🔧 Motor de traducción:", font=("Arial", 11, "bold")).pack(anchor=tk.W, pady=(0,5))
        engine_frame = ttk.Frame(main_frame)
        engine_frame.pack(fill=tk.X, pady=(0,10))
        ttk.Radiobutton(engine_frame, text="DeepLX (gratis)", value="deeplx", variable=self.engine, command=self._toggle_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(engine_frame, text="Google (gratis)", value="google", variable=self.engine, command=self._toggle_endpoint).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(engine_frame, text="DeepL (API)", value="deepl", variable=self.engine, command=self._toggle_endpoint).pack(side=tk.LEFT, padx=5)
        
        self.endpoint_frame = ttk.Frame(main_frame)
        self.endpoint_frame.pack(fill=tk.X, pady=(0,15))
        ttk.Label(self.endpoint_frame, text="Endpoint:").pack(side=tk.LEFT)
        ttk.Entry(self.endpoint_frame, textvariable=self.deeplx_endpoint, width=45).pack(side=tk.LEFT, padx=5)
        
        self.deepl_key_frame = ttk.Frame(main_frame)
        self.deepl_key_frame.pack(fill=tk.X, pady=(0,15))
        ttk.Label(self.deepl_key_frame, text="DeepL Key:").pack(side=tk.LEFT)
        self.deepl_key_var = tk.StringVar()
        ttk.Entry(self.deepl_key_frame, textvariable=self.deepl_key_var, width=40, show="*").pack(side=tk.LEFT, padx=5)
        self._toggle_endpoint()
        
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(10,5))
        
        self.status_label = ttk.Label(main_frame, textvariable=self.status, font=("Arial", 10))
        self.status_label.pack(anchor=tk.W, pady=(0,15))
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="🚀 Extraer y Traducir", command=self._start_translation, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📄 Solo Extraer", command=self._extract_only).pack(side=tk.LEFT, padx=5)
        
        style = ttk.Style()
        style.configure("Accent.TButton", font=("Arial", 11, "bold"))
    
    def _toggle_endpoint(self):
        if self.engine.get() == "deeplx":
            self.endpoint_frame.pack(fill=tk.X, pady=(0,15))
            self.deepl_key_frame.pack_forget()
        elif self.engine.get() == "deepl":
            self.endpoint_frame.pack_forget()
            self.deepl_key_frame.pack(fill=tk.X, pady=(0,15))
        else:
            self.endpoint_frame.pack_forget()
            self.deepl_key_frame.pack_forget()
    
    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.game_path.get())
        if folder:
            self.game_path.set(folder)
    
    def _start_translation(self):
        if not self.game_path.get():
            messagebox.showerror("Error", "Selecciona la ruta del juego")
            return
        
        self.status.set("Extrayendo textos...")
        self.progress.set(10)
        self.root.update()
        
        thread = threading.Thread(target=self._translate_worker)
        thread.daemon = True
        thread.start()
    
    def _translate_worker(self):
        try:
            game_path = self.game_path.get()
            target_lang = self.target_lang.get()
            
            ext = RenpyUIExtractor(game_path)
            ext.extract()
            
            if not ext.results:
                self.root.after(0, lambda: self.status.set("No se encontraron textos"))
                return
            
            self.root.after(0, lambda: self.status.set(f"Traduciendo {len(ext.results)} textos..."))
            self.root.after(0, lambda: self.progress.set(30))
            
            texts = [d['original'] for d in ext.results.values()]
            translations = {}
            
            engine = self.engine.get()
            if engine == "deeplx":
                translator = DeepLXTranslator(self.deeplx_endpoint.get())
                translations = translator.translate(texts, target_lang)
            elif engine == "google":
                if not GOOGLE_OK:
                    self.root.after(0, lambda: messagebox.showerror("Error", "googletrans no instalado"))
                    return
                translator = GoogleTranslatorFree()
                translations = translator.translate(texts, target_lang)
            elif engine == "deepl":
                if not DEEPL_OK:
                    self.root.after(0, lambda: messagebox.showerror("Error", "deepl no instalado"))
                    return
                if not self.deepl_key_var.get():
                    self.root.after(0, lambda: messagebox.showerror("Error", "Ingresa tu API Key de DeepL"))
                    return
                translator = DeepLTranslator(self.deepl_key_var.get())
                translations = translator.translate(texts, target_lang)
            
            for key, data in ext.results.items():
                orig = data['original']
                if orig in translations:
                    data['translated'] = translations[orig]
            
            lang_name = {"es":"spanish","en":"english","fr":"french","de":"german","it":"italian","pt":"portuguese","ja":"japanese","ko":"korean","zh":"chinese"}.get(target_lang, target_lang)
            out_path = os.path.join(game_path, f"game/tl/{target_lang}/strings.rpy")
            generate_translation_file(ext.results, out_path, lang_name)
            
            self.root.after(0, lambda: self.progress.set(100))
            self.root.after(0, lambda: self.status.set(f"✅ Completado! {len(ext.results)} textos traducidos"))
            self.root.after(0, lambda: messagebox.showinfo("Éxito", f"Traducción generada:\n{out_path}"))
            
        except Exception as e:
            self.root.after(0, lambda: self.status.set(f"❌ Error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
    
    def _extract_only(self):
        if not self.game_path.get():
            messagebox.showerror("Error", "Selecciona la ruta del juego")
            return
        
        self.status.set("Extrayendo textos...")
        self.root.update()
        
        ext = RenpyUIExtractor(self.game_path.get())
        ext.extract()
        
        lang = self.target_lang.get()
        lang_name = {"es":"spanish","en":"english","fr":"french","de":"german","it":"italian","pt":"portuguese","ja":"japanese","ko":"korean","zh":"chinese"}.get(lang, lang)
        out_path = os.path.join(self.game_path.get(), f"game/tl/{lang}/strings.rpy")
        generate_translation_file(ext.results, out_path, lang_name)
        
        self.status.set(f"✅ {len(ext.results)} textos extraídos")
        messagebox.showinfo("Éxito", f"Archivo generado:\n{out_path}")


def run_gui():
    root = tk.Tk()
    app = GUIController(root)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(
        description='Renpy UI Extractor + Auto-Translate'
    )
    parser.add_argument('--gui', action='store_true',
                    help='Abrir interfaz GUI')
    parser.add_argument('game_path', nargs='?', help='Ruta al juego')
    parser.add_argument('lang', nargs='?', help='Código de idioma (es, en, fr...)')
    parser.add_argument('--deepl', nargs='?', const='deepl', metavar='KEY',
                    help='API Key de DeepL (o variable DEEPL_KEY)')
    parser.add_argument('--deeplx', action='store_true',
                    help='Usar DeepLX (gratis, sin API key)')
    parser.add_argument('--endpoint', default=DEEPLX_ENDPOINT,
                    help='Endpoint de DeepLX')
    parser.add_argument('--google', action='store_true',
                    help='Usar Google Translate (gratis)')
    parser.add_argument('--output', '-o', help='Ruta de salida')
    
    args = parser.parse_args()
    
    if args.gui or (not args.game_path and not args.lang):
        run_gui()
        return
    
    # Get DeepL key
    deepl_key = None
    if args.deepl:
        if args.deepl == 'deepl':
            deepl_key = os.environ.get('DEEPL_KEY')
        else:
            deepl_key = args.deepl
    
    # Output path
    out_path = args.output
    if not out_path:
        out_path = f"game/tl/{args.lang}/strings.rpy"
    if not os.path.isabs(out_path):
        out_path = os.path.join(args.game_path, out_path)
    
    print("="*50)
    print(" Renpy UI Extractor + Auto-Translate")
    print("="*50)
    
    # Extract
    ext = RenpyUIExtractor(args.game_path)
    ext.extract()
    
    if not ext.results:
        print("No texts found!")
        return
    
    lang_name = {'es': 'spanish', 'en': 'english', 'fr': 'french'}.get(args.lang, args.lang)
    
    # Translate
    translator = None
    
    if args.deeplx:
        # DeepLX (gratis, sin API key)
        print(f"\nUsando DeepLX (gratis)...")
        translator = DeepLXTranslator(args.endpoint)
        texts = [d['original'] for d in ext.results.values()]
        translations = translator.translate(texts, args.lang)
        
        for key, data in ext.results.items():
            orig = data['original']
            if orig in translations:
                data['translated'] = translations[orig]
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nTraducción completa!")
        
    elif args.google and GOOGLE_OK:
        # Google Translate (gratis)
        print(f"\nUsando Google Translate...")
        translator = GoogleTranslatorFree()
        texts = [d['original'] for d in ext.results.values()]
        translations = translator.translate(texts, args.lang)
        
        for key, data in ext.results.items():
            orig = data['original']
            if orig in translations:
                data['translated'] = translations[orig]
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nTraducción completa!")
        
    elif deepl_key and DEEPL_OK:
        # DeepL
        print(f"\nUsando DeepL...")
        translator = DeepLTranslator(deepl_key)
        texts = [d['original'] for d in ext.results.values()]
        translations = translator.translate(texts, args.lang)
        
        for key, data in ext.results.items():
            orig = data['original']
            if orig in translations:
                data['translated'] = translations[orig]
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nTraducción completa!")
        
    else:
        # Ninguno seleccionado
        if args.google and not GOOGLE_OK:
            print("\nGoogle Translate no instalado.")
            print(" Instala con: pip install googletrans")
        elif deepl_key and not DEEPL_OK:
            print("\nDeepL no instalado.")
            print(" Instala con: pip install deepl")
        else:
            print("\nSin traductor automático.")
            print(" Usa --deeplx (gratis), --google (gratis), o --deepl TU_KEY")
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nArchivos generados.")


if __name__ == "__main__":
    main()