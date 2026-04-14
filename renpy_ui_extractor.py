#!/usr/bin/env python3
"""
Renpy UI Extractor + Auto-Translate
================================
Extrae y traduce textos de UI/menús/screens que Zenpy NO traduce.

Motores disponibles:
  - DeepL (--deepl KEY) - Mejor calidad, 500k chars/mes gratis
  - Google (--google) - Completamente gratis

Usage:
    python renpy_ui_extractor.py "C:/Games/Being a DIK" "es" --google
    python renpy_ui_extractor.py "C:/Games/Being a DIK" "es" --deepl TU_KEY
    
    # Con variable de entorno:
    export DEEPL_KEY="tu-key"
    python renpy_ui_extractor.py "C:/Games/Being a DIK" "es" --deepl
"""

import os
import re
import sys
import time
import argparse
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


def main():
    parser = argparse.ArgumentParser(
        description='Renpy UI Extractor + Auto-Translate'
    )
    parser.add_argument('game_path', help='Ruta al juego')
    parser.add_argument('lang', help='Código de idioma (es, en, fr...)')
    parser.add_argument('--deepl', nargs='?', const='deepl', metavar='KEY',
                    help='API Key de DeepL (o variable DEEPL_KEY)')
    parser.add_argument('--google', action='store_true',
                    help='Usar Google Translate (gratis)')
    parser.add_argument('--output', '-o', help='Ruta de salida')
    
    args = parser.parse_args()
    
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
    
    if args.google and GOOGLE_OK:
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
            print(" Usa --google (gratis) o --deepl TU_KEY")
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nArchivos generados.")


if __name__ == "__main__":
    main()