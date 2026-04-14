#!/usr/bin/env python3
"""
Renpy UI & Screen Text Extractor
=================================
Extrae textos de menús, screens, UI y mensajes que Zenpy NO traduce.
Los textos extraídos pueden luego ser traducidos manualmente o con otro motor.

Uso:
    python renpy_ui_extractor.py "ruta/al/juego" "es" "game/tl/espanol/strings.rpy"
    
Argumentos:
    1. Ruta al juego (carpeta del juego, no la carpeta game)
    2. Código de idioma (ej: es, en, fr, ja, ko, zh)
    3. (opcional) Ruta de salida para el archivo de traducción
"""

import os
import re
import sys
from pathlib import Path
from collections import defaultdict


class RenpyUIExtractor:
    """Extrae textos de UI, menús, screens y elementos no-dialogue de Ren'Py"""
    
    # Textos que deben ignorarse (comunes en código Ren'Py)
    IGNORE_PATTERNS = [
        r'^skip$',
        r'^auto$', 
        r'^yes$',
        r'^no$',
        r'^true$',
        r'^false$',
        r'^None$',
        r'^\d+$',
        r'^{.*}$',  # Solo tags de texto
        r'^\[.*\]$',  # Solo variables
    ]
    
    def __init__(self, game_path):
        self.game_path = Path(game_path).resolve()
        self.results = {}
        self.stats = {
            'files_processed': 0,
            'texts_found': 0,
            'duplicates_removed': 0
        }
    
    def extract(self):
        """Ejecuta la extracción completa"""
        print(f"🔍 Buscando en: {self.game_path}")
        
        game_dir = self.game_path / "game"
        if not game_dir.exists():
            print(f"❌ ERROR: No se encontró la carpeta 'game'")
            return {}
        
        # Buscar TODOS los archivos .rpy
        rpy_files = list(game_dir.rglob("*.rpy"))
        print(f"📁 Encontrados {len(rpy_files)} archivos .rpy")
        
        for rpy_file in rpy_files:
            self._process_file(rpy_file)
            self.stats['files_processed'] += 1
        
        # Limpiar resultados
        self._clean_results()
        
        print(f"\n📊 ESTADÍSTICAS:")
        print(f"   - Archivos procesados: {self.stats['files_processed']}")
        print(f"   - Textos encontrados: {self.stats['texts_found']}")
        print(f"   - Duplicados removidos: {self.stats['duplicates_removed']}")
        
        return dict(self.results)
    
    def _process_file(self, file_path):
        """Procesa un archivo .rpy individual"""
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            return
        
        rel_path = str(file_path.relative_to(self.game_path))
        
        # ========== PATRONES DE EXTRACCIÓN ==========
        
        # 1. Textbutton en screens (menús, botones)
        for match in re.finditer(r'textbutton\s+"([^"]+)"', content):
            self._add_text(match.group(1), rel_path, 'textbutton')
        
        # 2. Text en screens (no diálogos)
        # Excluir líneas que parecen ser diálogos (empiejan con indentation seguida de texto)
        for match in re.finditer(r'(?:^|\n)(\s*)text\s+"([^"]+)"', content, re.MULTILINE):
            text = match.group(2)
            indent = len(match.group(1))
            # Solo procesar si no es diálogo (indent < 8 espacios típicamente)
            if indent < 8 and not text.startswith('{'):
                self._add_text(text, rel_path, 'screen_text')
        
        # 3. Opciones de menú (menu: ... "opción":)
        for match in re.finditer(r'^\s*"([^"]+)"\s*:(?:\s|#|$)', content, re.MULTILINE):
            text = match.group(1)
            # Verificar que es una opción de menú real
            if not self._is_character_dialogue(content, match.start()):
                self._add_text(text, rel_path, 'menu_option')
        
        # 4. Labels de pantalla (para mensajes, phone screens, etc)
        for match in re.finditer(r'^screen\s+(\w+)', content, re.MULTILINE):
            screen_name = match.group(1)
            # No procesar screens del sistema
            if not screen_name.startswith('_'):
                self._extract_screen_content(content, match.end(), rel_path, screen_name)
        
        # 5. Text en add/displayable
        for match in re.finditer(r'(?:add|show)\s+["\']?(\w+)["\']?\s*,\s*["\']?text["\']?\s*=\s*"([^"]+)"', content):
            self._add_text(match.group(2), rel_path, 'add_text')
        
        # 6. Strings en vbox/hbox/frame/etc
        for match in re.finditer(r'(?:vbox|hbox|frame|fixed|grid)\s*:\s*\n\s*text\s+"([^"]+)"', content):
            self._add_text(match.group(1), rel_path, 'container_text')
        
        # 7. Text en viewport/scrollbar
        for match in re.finditer(r'(?:viewport|scrollbar|bar)\s*[{\s]', content):
            # Buscar texto después
            pass
        
        # 8. Text en window (para mensajes)
        for match in re.finditer(r'window\s*:\s*\n\s*text\s+"([^"]+)"', content):
            self._add_text(match.group(1), rel_path, 'window_text')
        
        # 9. Strings en Python code dentro de screens
        python_pattern = r'["\']([A-Z][a-zA-Z\s]{2,30})["\']'
        for match in re.finditer(python_pattern, content):
            text = match.group(1)
            # Verificar que es texto visible, no variable
            if not text.startswith('{') and not text.startswith('['):
                self._add_text(text, rel_path, 'python_string')
    
    def _extract_screen_content(self, content, start_pos, rel_path, screen_name):
        """Extrae textos específicos de una screen"""
        lines = content[start_pos:].split('\n')
        
        # Encontrar el indent de la screen
        screen_indent = None
        for i, line in enumerate(lines):
            if line.strip():
                screen_indent = len(line) - len(line.lstrip())
                break
        
        if screen_indent is None:
            return
        
        # Buscar textos mientras estamos dentro de la screen
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            
            current_indent = len(line) - len(line.lstrip())
            
            # Si alcanzamos menor indent, salimos de la screen
            if current_indent <= screen_indent and stripped:
                break
            
            # Extraer textos de esta línea
            # textbutton "texto"
            for match in re.finditer(r'textbutton\s+"([^"]+)"', line):
                self._add_text(match.group(1), rel_path, f'screen_{screen_name}')
            
            # text "texto"
            for match in re.finditer(r'text\s+"([^"]+)"', line):
                if len(match.group(1)) > 2:
                    self._add_text(match.group(1), rel_path, f'screen_{screen_name}')
            
            # label "texto"
            for match in re.finditer(r'label\s+"([^"]+)"', line):
                self._add_text(match.group(1), rel_path, f'screen_{screen_name}')
            
            # text para mensajes
            if 'text ' in line and '"' in line:
                for match in re.findall(r'"([^"]{3,})"', line):
                    if not match.startswith('{') and not match.startswith('['):
                        self._add_text(match, rel_path, f'screen_{screen_name}')
    
    def _is_character_dialogue(self, content, position):
        """Determina si una cadena es diálogo de personaje"""
        # Obtener las 200 líneas anteriores para verificar contexto
        start = max(0, position - 3000)
        context = content[start:position]
        
        # Si hay $ antes, es código Python (probablemente no diálogo)
        if '$' in context[-500:]:
            return False
        
        # Si hay "character" antes, podría ser diálogo
        # otherwise es opción de menú
        lines = context.split('\n')
        last_lines = [l for l in lines if l.strip()][-5:] if lines else []
        
        return False  # Por defecto, asumir que es menú
    
    def _add_text(self, text, source, text_type):
        """Agrega un texto a los resultados"""
        text = text.strip()
        
        # Ignorar textos muy cortos o patrones no-textuales
        if not text or len(text) < 2:
            return
        
        # Verificar patrones a ignorar
        for pattern in self.IGNORE_PATTERNS:
            if re.match(pattern, text, re.IGNORECASE):
                return
        
        # Ignorar si contiene solo variables de Ren'Py
        if re.match(r'^[\[\]{}!@#$%^&*()_+=|<>?]+$', text):
            return
        
        # Ignorar si parece ser ruta de archivo
        if '/' in text or '\\' in text or '.png' in text.lower() or '.jpg' in text.lower():
            return
        
        # Crear key única
        key = text.lower().strip()
        
        if key not in self.results:
            self.results[key] = {
                'original': text,
                'source': source,
                'type': text_type,
                'translated': ''
            }
            self.stats['texts_found'] += 1
    
    def _clean_results(self):
        """Limpia y organiza los resultados"""
        # Por ahora solo contar duplicados
        pass
    
    def generate_translation_file(self, output_path, target_lang='spanish'):
        """Genera el archivo de traducción en formato Ren'Py"""
        
        if not self.results:
            print("⚠️ No se encontraron textos para traducir")
            return None
        
        # Crear contenido
        lines = [
            f"# Extra translation strings - {target_lang}",
            f"# Generado por Renpy UI Extractor",
            f"# Total de textos: {len(self.results)}",
            "",
            f"translate {target_lang} strings:",
            ""
        ]
        
        # Agrupar por tipo
        by_type = defaultdict(list)
        for data in self.results.values():
            by_type[data['type']].append(data)
        
        # Agregar por tipo
        for text_type, items in sorted(by_type.items()):
            lines.append(f"    # === {text_type} ===")
            for item in items:
                original = item['original'].replace('\\', '\\\\').replace('"', '\\"')
                lines.append(f'    old "{original}"')
                lines.append(f'    new ""')
                lines.append("")
        
        # Guardar
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        content = '\n'.join(lines)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✅ Archivo generado: {output_file}")
        
        # También generar un archivo para traducir manualmente
        self._generate_translation_template(output_file.parent)
        
        return output_file
    
    def _generate_translation_template(self, output_dir):
        """Genera template para traducción manual"""
        
        template_path = output_dir / "strings_to_translate.txt"
        
        lines = []
        for data in self.results.values():
            if data['type'] in ['textbutton', 'menu_option', 'screen_text']:
                lines.append(f"{data['original']}")
        
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        print(f"📝 Template para traducir: {template_path}")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\nEjemplos:")
        print('  python renpy_ui_extractor.py "C:/Games/Being a DIK" "es"')
        print('  python renpy_ui_extractor.py "C:/Games/Being a DIK" "es" "game/tl/espanol/strings.rpy"')
        return
    
    game_path = sys.argv[1]
    lang_code = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else f"game/tl/{lang_code}/strings.rpy"
    
    # Mapeo de códigos a nombres completos
    lang_map = {
        'es': 'spanish',
        'en': 'english', 
        'fr': 'french',
        'de': 'german',
        'it': 'italian',
        'pt': 'portuguese',
        'ja': 'japanese',
        'ko': 'korean',
        'zh': 'chinese',
        'ru': 'russian'
    }
    
    lang_name = lang_map.get(lang_code, lang_code)
    
    # Asegurar que la ruta de salida sea absoluta si no lo es
    if not os.path.isabs(output_path):
        output_path = os.path.join(game_path, output_path)
    
    print("="*50)
    print("  Renpy UI & Screen Text Extractor")
    print("="*50)
    
    extractor = RenpyUIExtractor(game_path)
    extractor.extract()
    extractor.generate_translation_file(output_path, lang_name)
    
    print("\n✨ Listo! Los textos ahora pueden ser traducidos.")


if __name__ == "__main__":
    main()