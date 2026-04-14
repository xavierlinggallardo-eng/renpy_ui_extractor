#!/usr/bin/env python3
"""
Renpy UI Extractor + Auto-Translate (DeepL)
========================================
Extrae y traduce textos de UI, menús, screens que Zenpy NO traduce.

Usage:
    python renpy_ui_extractor.py "ruta/al/juego" "es" [--deepl KEY]
    
Ejemplo:
    python renpy_ui_extractor.py "C:/Games/Being a DIK" "es" --deepl

Requiere: pip install deepl
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

# DeepL
try:
    import deepl
    DEEPL_OK = True
except ImportError:
    DEEPL_OK = False


LANG_MAP = {
    'es': 'ES', 'en': 'EN-US', 'fr': 'FR', 'de': 'DE', 'it': 'IT',
    'pt': 'PT-BR', 'ja': 'JA', 'ko': 'KO', 'zh': 'ZH', 'ru': 'RU'
}


class RenpyUIExtractor:
    """Extrae textos de UI/menús/screens que Zenpy no traduce"""
    
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
        
        # textbutton
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
    """Traductor DeepL"""
    
    def __init__(self, api_key):
        self.translator = deepl.Translator(api_key)
    
    def translate(self, texts, target_lang, source_lang='EN'):
        """Traduce lista de textos"""
        results = {}
        target = LANG_MAP.get(target_lang, target_lang.upper())
        
        print(f"Traduciendo {len(texts)} textos a {target_lang}...")
        
        for i, text in enumerate(texts):
            try:
                result = self.translator.translate_text(
                    text, source_lang=source_lang, target_lang=target
                )
                results[text] = result.text
                
                if (i + 1) % 20 == 0:
                    print(f"  {i+1}/{len(texts)}...")
                
                # Rate limiting para versión libre
                time.sleep(0.02)
                
            except Exception as e:
                print(f"Error translating '{text[:20]}...': {e}")
                results[text] = text
        
        return results


def generate_translation_file(results, out_path, lang):
    """Genera archivo de traducción Ren'Py"""
    
    if not results:
        print("No texts found")
        return
    
    lines = [
        f"# Extra translation strings - {lang}",
        f"# Generated by Renpy UI Extractor + DeepL",
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
    parser = argparse.ArgumentParser(description='Renpy UI Extractor + DeepL Translator')
    parser.add_argument('game_path', help='Ruta al juego')
    parser.add_argument('lang', help='Código de idioma (es, en, fr...)')
    parser.add_argument('--deepl', nargs='?', const='deepl', metavar='KEY',
                    help='API Key de DeepL (o variable DEEPL_KEY)')
    parser.add_argument('--output', '-o', help='Ruta de salida')
    
    args = parser.parse_args()
    
    # Get DeepL key
   deepl_key = None
    if args.deepl:
        if args.deepl == 'deepl':
            deepl_key = os.environ.get('DEEPL_KEY', os.environ.get('DEEPL_API_KEY'))
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
    
    if deepl_key and DEEPL_OK:
        # Translate with DeepL
        print(f"\nTraduciendo con DeepL...")
        translator = DeepLTranslator(deepl_key)
        
        texts = [d['original'] for d in ext.results.values()]
        translations = translator.translate(texts, args.lang, 'EN')
        
        # Apply translations
        for key, data in ext.results.items():
            orig = data['original']
            if orig in translations:
                data['translated'] = translations[orig]
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nTraducción completa!")
        
    else:
        # Just extract, no translation
        if not deepl_key:
            print("\nNo DeepL key provided. Solo extrayendo.")
            print(" 提供 API key con --deepl TU_KEY para traducir")
        elif not DEEPL_OK:
            print("\nDeepL no instalado.")
            print(" Instala con: pip install deepl")
        
        generate_translation_file(ext.results, out_path, lang_name)
        print(f"\nArchivos generados. Tradúcelos manualmente.")


if __name__ == "__main__":
    main()