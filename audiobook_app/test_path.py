from config import Config

target_language = 'ur'
font_name = 'Noto Nastaliq Urdu'
font_value = font_name
font_name = font_value.split(',')[0].strip().strip("'\"")

print('font_name:', font_name)

candidates = [font_name + '.ttf', font_name + '.ttc', font_name + '.otf']
print('Initial candidates:', candidates)

if target_language == 'ur':
    static_fonts_dir = Config.STATIC_FOLDER / 'fonts'
    print('static_fonts_dir:', static_fonts_dir)
    candidates.insert(0, str(static_fonts_dir / 'noto-nastaliq-urdu.otf'))
    candidates.insert(1, str(static_fonts_dir / (font_name + '.otf')))
    
print('Final candidates:', candidates)