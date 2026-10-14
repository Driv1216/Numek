"""Root-constrained handles and bounded immutable image bytes; no corpus copies."""
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import time

from datatrust.contracts import AnalysisError

FORMATS = {'JPEG', 'PNG', 'BMP', 'WEBP', 'TIFF'}
EXTENSIONS = {'.jpg', '.jpeg', '.jfif', '.avif', '.dng', '.cr2', '.nef', '.arw', '.png', '.bmp', '.webp', '.tif', '.tiff', '.gif', '.heic', '.raw', '.dcm', '.svg', '.pdf'}


def error(code, stage='image integrity'):
    raise AnalysisError('Image operation failed; review the declared source and coverage.', code=code, stage=stage)


def signature(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def authorized(path, roots):
    p = Path(os.path.abspath(os.fspath(path)))
    if '..' in Path(path).parts or '\x00' in str(path): error('unsafe_path')
    for r in roots:
        lexical = Path(os.path.abspath(os.fspath(r)))
        if p.is_relative_to(lexical):
            return lexical.resolve(), p.relative_to(lexical)
        canonical=lexical.resolve()
        if p.is_relative_to(canonical):
            return canonical, p.relative_to(canonical)
    error('out_of_root')


@contextmanager
def secure_open(path, roots):
    root, relative = authorized(path, roots)
    if not relative.parts: error('not_regular_file')
    if os.name == 'posix':
        parent = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = None
        try:
            for component in relative.parts[:-1]:
                next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                os.close(parent); parent = next_fd
            fd = os.open(relative.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            if not stat.S_ISREG(os.fstat(fd).st_mode): error('not_regular_file')
            with os.fdopen(fd, 'rb') as handle:
                fd = None
                yield handle, root / relative
        except OSError as exc:
            error('source_unavailable' if isinstance(exc, FileNotFoundError) else 'unsafe_or_unavailable_source')
        finally:
            if fd is not None: os.close(fd)
            os.close(parent)
    else:
        # Windows uses the opened handle's final path; reject every reparse component.
        current = root
        for part in relative.parts:
            current /= part
            s = current.lstat()
            if getattr(s, 'st_file_attributes', 0) & 0x400: error('reparse_source')
        with current.open('rb') as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode): error('not_regular_file')
            if os.name == 'nt':
                import ctypes, msvcrt
                from ctypes import wintypes
                api=ctypes.windll.kernel32.GetFinalPathNameByHandleW
                api.argtypes=[wintypes.HANDLE,wintypes.LPWSTR,wintypes.DWORD,wintypes.DWORD]; api.restype=wintypes.DWORD
                buffer = ctypes.create_unicode_buffer(32768)
                n = api(msvcrt.get_osfhandle(handle.fileno()), buffer, len(buffer), 0)
                if not n or n >= len(buffer): error('unverified_handle')
                final = Path(buffer.value.removeprefix('\\\\?\\'))
                if not final.is_relative_to(root): error('out_of_root')
            yield handle, current


def capture(path, roots, *, max_bytes=None, expected=None, check=None):
    started = time.monotonic(); digest = hashlib.sha256(); chunks = []
    with secure_open(path, roots) as (handle, actual):
        before = signature(os.fstat(handle.fileno()))
        retain = max_bytes is not None and before[2] <= max_bytes
        while True:
            block = handle.read(1024**2)
            if not block: break
            digest.update(block)
            if retain: chunks.append(block)
            if check: check()
        if before[:4] != signature(os.fstat(handle.fileno()))[:4]: error('source_changed')
    info = {'path': str(actual), 'signature': before, 'bytes': before[2], 'sha256': digest.hexdigest()}
    if expected and (info['sha256'] != expected['sha256'] or info['signature'][:4] != list(expected['signature'])[:4]): error('source_changed')
    return info, b''.join(chunks) if retain else None, time.monotonic() - started


def verify_files(files, roots, *, check=None):
    bytes_read = 0
    for info in files.values():
        current, _, _ = capture(info['path'], roots, expected=info, check=check)
        bytes_read += current['bytes']
    return bytes_read


def walk(directory, roots, *, check=None):
    root, relative = authorized(directory, roots)
    base = root / relative
    current = root
    for part in relative.parts:
        current /= part
        if current.is_symlink(): error('symlink_directory')
    pending = [base]
    while pending:
        parent = pending.pop()
        if parent.is_symlink() or not parent.is_dir(): error('directory_changed')
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    if entry.is_symlink(): error('symlink_inventory')
                    if entry.is_dir(follow_symlinks=False): pending.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        if check: check()
                        yield Path(entry.path)
                    else: error('special_inventory_entry')
        except OSError: error('incomplete_directory_inventory')


def membership(directory, roots, *, check=None):
    # Order-independent digest; the count and two independent modular sums bind membership.
    count = first = second = 0; modulus = 2**256
    for path in walk(directory, roots, check=check):
        relative = str(path.relative_to(Path(directory).resolve())).encode('utf8')
        first = (first + int.from_bytes(hashlib.sha256(relative).digest(), 'big')) % modulus
        second = (second + int.from_bytes(hashlib.sha256(b'2\0' + relative).digest(), 'big')) % modulus
        count += 1
    return {'entries': count, 'sha256_sum': f'{first:064x}', 'independent_sum': f'{second:064x}'}


def digest_raster(image, *, oriented=False, icc=b''):
    h = hashlib.sha256()
    header = {'method': 'oriented_rgba8_v1' if oriented else 'native_raster_v1', 'mode': image.mode, 'size': image.size}
    if not oriented:
        header['palette'] = image.getpalette() if image.mode == 'P' else None
        transparency = image.info.get('transparency')
        header['transparency'] = list(transparency) if isinstance(transparency, bytes) else transparency
    else: header['icc_sha256'] = hashlib.sha256(icc).hexdigest() if icc else None
    h.update(json.dumps(header, sort_keys=True).encode()); h.update(image.tobytes())
    return h.hexdigest()


def decode(raw, limits):
    import warnings
    import numpy as np
    from PIL import Image, ImageOps
    info = {'decode': 'unreadable', 'visual_eligible': False}
    if raw is None: return info | {'decode': 'capture_safety_excluded'}, None
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                w,h = image.size
                frames = getattr(image, 'n_frames', 1)
                orientation = image.getexif().get(274, 1)
                info.update(format=image.format, width=w, height=h, mode=image.mode, frames=frames, orientation=orientation,
                            icc_present=bool(image.info.get('icc_profile')), exif_present=bool(image.info.get('exif')))
                if image.format not in FORMATS: return info | {'decode': 'unsupported_format'}, None
                if frames != 1: return info | {'decode': 'unsupported_frames'}, None
                if w*h > limits.pixels_per_asset or w*h*16 > limits.decode_bytes: return info | {'decode': 'pixel_safety_excluded'}, None
                if orientation not in range(1,9): return info | {'decode': 'invalid_orientation'}, None
                image.load()
                info.update(decode='decoded', pixels=w*h, native_sha256=digest_raster(image))
                icc = image.info.get('icc_profile', b'')
                if len(icc) > 1024**2: return info | {'visual_exclusion': 'profile_metadata_limit'}, None
                if image.mode not in {'1','L','LA','RGB','RGBA','P'}: return info | {'visual_exclusion': 'unsupported_color_mode'}, None
                oriented = ImageOps.exif_transpose(image).convert('RGBA')
                info.update(oriented_width=oriented.width, oriented_height=oriented.height,
                            oriented_sha256=digest_raster(oriented, oriented=True, icc=icc))
                alpha = oriented.getchannel('A').getextrema()
                if icc or alpha != (255,255): return info | {'visual_exclusion': 'icc_profile' if icc else 'nontrivial_alpha'}, None
                preview = oriented.convert('RGB'); preview.thumbnail((512,512), Image.Resampling.LANCZOS)
                gray = np.asarray(preview.convert('L'), dtype=np.float64)/255
                lap = -4*gray[1:-1,1:-1] + gray[:-2,1:-1]+gray[2:,1:-1]+gray[1:-1,:-2]+gray[1:-1,2:]
                histogram = np.bincount(np.asarray(preview.convert('L')).ravel(), minlength=256).astype(float)
                probs = histogram[histogram>0]/histogram.sum()
                info.update(visual_eligible=True, contrast=float(gray.std()), mean_luminance=float(gray.mean()),
                            dark_fraction=float((gray<.05).mean()), bright_fraction=float((gray>.95).mean()),
                            entropy=float(-(probs*np.log2(probs)).sum()), sharpness=float(lap.var()) if lap.size else None,
                            preview_size=list(preview.size))
                info['phash'] = perceptual_hash(preview)
                return info, preview
        except (Image.DecompressionBombError, Image.DecompressionBombWarning): return info | {'decode':'pixel_safety_excluded'}, None
        except (OSError, ValueError, SyntaxError): return info | {'decode':'corrupt_or_truncated'}, None


def perceptual_hash(image):
    import numpy as np
    from PIL import Image
    pixels = np.asarray(image.convert('L').resize((32,32), Image.Resampling.LANCZOS), dtype=np.float64)
    n = np.arange(32); k = np.arange(8)[:,None]
    basis = np.cos(np.pi*(n+.5)*k/32)
    dct = basis @ pixels @ basis.T
    threshold = np.median(dct.ravel()[1:])
    result = 0
    for i, value in enumerate(dct.ravel()):
        if i and value > threshold: result |= 1 << i
    return result


def oriented_point(x,y,w,h,orientation):
    return {1:(x,y),2:(w-x,y),3:(w-x,h-y),4:(x,h-y),5:(y,x),6:(h-y,x),7:(h-y,w-x),8:(y,w-x)}[orientation]
