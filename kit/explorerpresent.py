"""Presentation only: original paths and format identifiers remain unchanged in the API."""
from pathlib import PurePosixPath
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def extension(row):
    path = PurePosixPath(row['member'] or row['path'])
    return (path.stem[-7:] if path.stem.casefold().endswith('.assets') and row['kind'] == 'sound' else '') + path.suffix


def name(row):
    path = PurePosixPath(row['member'] or row['path'])
    stem, suffix = path.stem, path.suffix
    if row['kind'] == 'sound':
        if stem.casefold().endswith('.assets'):
            stem, suffix = stem[:-7], extension(row)
        # FMOD's generated names often repeat the complete bank name twice.
        words = stem.split('_')
        for length in range(len(words)//2, 0, -1):
            if words[:length] == words[length:2*length]:
                stem = '_'.join(words[length:]); break
    readable = re.sub(r'[_\s]+', ' ', stem).strip()
    return readable + suffix if readable else path.name


def group(row, lang):
    parts = PurePosixPath(row['path']).parts
    if row['kind'] == 'sound':
        match = re.search(r'DIALOG([^/]+)', row['path'], re.I)
        if match:
            locale = match.group(1)
            languages = {
                'es-es': ('Español', 'Spanish'), 'en-us': ('Inglés', 'English'),
                'en-gb': ('Inglés', 'English'), 'fr-fr': ('Francés', 'French'),
                'de-de': ('Alemán', 'German'), 'it-it': ('Italiano', 'Italian'),
                'pt-br': ('Portugués (Brasil)', 'Portuguese (Brazil)'),
                'nl-nl': ('Neerlandés', 'Dutch'), 'da-dk': ('Danés', 'Danish'),
                'sv-se': ('Sueco', 'Swedish'), 'nb-no': ('Noruego', 'Norwegian'),
                'fi-fi': ('Finés', 'Finnish'), 'pl-pl': ('Polaco', 'Polish'),
                'ru-ru': ('Ruso', 'Russian'), 'ja-jp': ('Japonés', 'Japanese'),
                'cs-cz': ('Checo', 'Czech'), 'es-mx': ('Español (México)', 'Spanish (Mexico)'),
            }
            label = languages.get(locale.casefold(), (locale, locale))[lang != 'es']
            return ('Diálogos — ' if lang == 'es' else 'Dialogue — ') + label
        return 'Música y efectos' if lang == 'es' else 'Music and effects'
    folder = parts[1] if len(parts) > 2 else parts[0]
    known = {'characters': ('Personajes', 'Characters'), 'levels': ('Niveles', 'Levels'),
             'worlds': ('Mundos', 'Worlds'), 'objects': ('Objetos', 'Objects'),
             'props': ('Objetos', 'Objects'), 'assets': ('Otros archivos', 'Other files'),
             'data_dx': ('Datos del juego', 'Game data')}
    return known.get(folder.casefold(), (folder.replace('_', ' '),)*2)[lang != 'es']


def matches(row, query, lang):
    words = normalized(query).split()
    haystack = normalized(' '.join((row['path'], row['member'] or '', name(row), group(row, lang))))
    return all(word in haystack for word in words)


def size(value, lang):
    units = ('B', 'KB', 'MB', 'GB')
    unit = 0
    while value >= 1000 and unit < 3:
        value /= 1000; unit += 1
    number = str(int(value)) if unit == 0 else '%.1f' % value
    return (number.replace('.', ',') if lang == 'es' else number) + ' ' + units[unit]


def count(value, lang):
    return str(value) + (' resultado' if lang == 'es' else ' result') + ('' if value == 1 else 's')


def preview_kind(row, entries=None):
    """Availability hint, refined after opening. Extension alone cannot prove OCT content."""
    if 'preview_hint' in row: return row['preview_hint']
    kind = row['kind']
    if kind == 'texture': return 'image'
    if kind == 'text': return 'text'
    if kind == 'oct': return 'check'
    if kind == 'sound':
        count = row.get('audio_samples')
        return 'check_audio' if count is None else 'audio' if count > 0 else 'none'
    if kind == 'archive' and row['member'] is None:
        if entries is None: return 'check'
        main = PurePosixPath(row['path']).stem.casefold() + '.oct'
        return 'check' if any(e['member'].casefold() == main for e in entries) else 'none'
    return 'none'


def preview_text(row, lang, detail=False):
    kind = preview_kind(row)
    labels = {
        'image': ('Imagen', 'Image'), 'images': ('Imágenes', 'Images'),
        'model': ('Modelo 3D', '3D model'), 'audio': ('Audio', 'Audio'), 'text': ('Texto', 'Text'),
        'check': ('Por comprobar', 'Check preview'), 'check_audio': ('Comprobar audio', 'Check audio'),
        'none': ('No disponible', 'Unavailable'), 'error': ('Error al abrir', 'Could not open'),
    }
    if not detail: return labels[kind][lang != 'es']
    notes = {
        'image': ('Imagen. Pulsa Ver imagen.', 'Image. Choose View image.'),
        'images': ('Imágenes disponibles. Pulsa Ver imágenes.', 'Images available. Choose View images.'),
        'model': ('Modelo 3D disponible. Pulsa Ver modelo.', '3D model available. Choose View model.'),
        'audio': ('Audio. Pulsa Ver sonidos para elegir una muestra.', 'Audio. Choose View sounds to select a sample.'),
        'text': ('Texto. Pulsa Ver información para leerlo.', 'Text. Choose View information to read it.'),
        'check': ('Por comprobar. Pulsa Comprobar vista para buscar modelos o imágenes.',
                  'Not checked yet. Choose Check preview to look for models or images.'),
        'check_audio': ('Audio por comprobar. Pulsa Ver sonidos para buscar muestras.',
                        'Audio not checked yet. Choose View sounds to look for samples.'),
        'none': ('No disponible. Puedes ver la información o guardar una copia.',
                 'Unavailable. You can view information or save a copy.'),
        'error': ('No se pudo abrir. Puedes reintentar o consultar Más → Detalles técnicos.',
                  'Could not open. Retry or use More → Technical details.'),
    }
    return ('Vista previa: ' if lang == 'es' else 'Preview: ') + notes[kind][lang != 'es']


def actions(row):
    if not row: return ()
    kind, member = row['kind'], row['member']
    hint = preview_kind(row)
    primary = ('audio' if kind == 'sound' and hint != 'none' else
               'preview' if kind in ('archive', 'oct', 'texture') and hint != 'none' else 'inspect')
    result = [primary, 'extract', 'technical']
    if primary == 'preview': result.append('export')
    if (kind == 'archive' and member is None) or (kind == 'oct' and member is not None):
        result.extend(('tex_dump', 'glb'))
    if kind == 'oct' and member is not None: result.append('mesh_dump')
    return tuple(result)


def summary(row, lang, info=None):
    """Human summary. Only the explicit technical view displays raw JSON/hex."""
    es = lang == 'es'
    kinds = dict(zip(('archive', 'oct', 'texture', 'sound', 'mesh', 'text', 'other'),
                     ('Archivo con contenido del juego', 'Contenido del juego (OCT)', 'Imagen', 'Banco de sonidos',
                      'Parte de un modelo', 'Documento de texto', 'Archivo del juego') if es else
                     ('Game content archive', 'Game content (OCT)', 'Image', 'Sound bank',
                      'Model component', 'Text document', 'Game file')))
    lines = [name(row), kinds[row['kind']] + ' · ' + size(row['size'], lang)]
    hints = {
        'archive': ('Abre la flecha de la lista para elegir un modelo o imagen. Puedes ver su contenido o preparar texturas para editar.',
                    'Expand this archive in the list to choose a model or image. You can preview its content or prepare textures to edit.'),
        'oct': ('Este formato puede contener modelos o imágenes. En Editar puedes preparar texturas o un objeto rígido para trabajar fuera de la herramienta.',
                'This format can contain models or images. Use Edit to prepare textures or a rigid object for editing in another app.'),
        'texture': ('Mira la imagen o guarda una copia. Para crear un mod de texturas, elige el archivo que la contiene.',
                    'View the image or save a copy. To create a texture mod, select the archive containing it.'),
        'sound': ('Pulsa Ver sonidos para elegir una muestra. Solo sonará cuando pulses Reproducir.',
                  'Choose View sounds to select a sample. It plays only when you press Play.'),
    }
    lines.extend(('', hints.get(row['kind'], ('Puedes consultar la información o guardar una copia del archivo.',
                                             'You can view information or save a copy of this file.'))[not es]))
    samples = len(info['sounds']) if info and 'sounds' in info else row.get('audio_samples')
    if samples is not None:
        lines.extend(('', (('%d sonido' if es else '%d sound') % samples) + ('' if samples == 1 else 's')))
        if samples == 0: lines.append('Contiene eventos o metadatos; no hay audio para escuchar.' if es else 'Contains events or metadata; there is no audio to play.')
    if info:
        if 'entries' in info: lines.extend(('', ('%d archivos dentro' if es else '%d files inside') % len(info['entries'])))
        if 'width' in info: lines.extend(('', '%d × %d px' % (info['width'], info['height'])))
        if 'textures' in info: lines.extend(('', ('%d imágenes' if es else '%d images') % len(info['textures'])))
        if info.get('model'):
            m = info['model']
            lines.append(('%d piezas · %d triángulos · %d huesos' if es else '%d pieces · %d triangles · %d bones') %
                         (m['pieces'], m['triangles'], m['bones']))
        if row['kind'] == 'text': lines.extend(('', info.get('text', '')))
    return '\n'.join(lines)


def error(message, lang):
    es = lang == 'es'
    if 'outside' in message or 'Export outside' in message:
        return 'Elige una carpeta de destino fuera del juego.' if es else 'Choose an output folder outside the game.'
    if 'new output' in message or 'exists' in message:
        return 'La carpeta de destino ya existe. Elige otra carpeta.' if es else 'The output folder already exists. Choose another folder.'
    if 'changed' in message:
        return 'El archivo cambió. Actualiza la lista y vuelve a intentarlo.' if es else 'The file changed. Refresh the list and try again.'
    if 'large' in message or 'limit' in message:
        return 'Este archivo supera el tamaño que se puede procesar. Elige un archivo más pequeño.' if es else 'This file exceeds the supported size. Choose a smaller file.'
    return ('No se pudo completar la operación. Comprueba el archivo y la carpeta de destino. En «Más → Detalles técnicos» puedes consultar el motivo.' if es else
            'The operation could not be completed. Check the file and output folder. Use More → Technical details to see the reason.')
