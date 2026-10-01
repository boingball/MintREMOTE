"""Physical PC keys and display coordinates mapped to the Amiga protocol."""
from __future__ import annotations

RAW_KEYS = {
    "grave": 0x00,
    "1": 0x01, "2": 0x02, "3": 0x03, "4": 0x04, "5": 0x05,
    "6": 0x06, "7": 0x07, "8": 0x08, "9": 0x09, "0": 0x0A,
    "exclam": 0x01, "at": 0x02, "numbersign": 0x03, "dollar": 0x04,
    "percent": 0x05, "asciicircum": 0x06, "ampersand": 0x07,
    "asterisk": 0x08, "parenleft": 0x09, "parenright": 0x0A,
    "minus": 0x0B, "equal": 0x0C, "backslash": 0x0D,
    "underscore": 0x0B, "plus": 0x0C, "bar": 0x0D,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14,
    "y": 0x15, "u": 0x16, "i": 0x17, "o": 0x18, "p": 0x19,
    "bracketleft": 0x1A, "bracketright": 0x1B,
    "braceleft": 0x1A, "braceright": 0x1B,
    "a": 0x20, "s": 0x21, "d": 0x22, "f": 0x23, "g": 0x24,
    "h": 0x25, "j": 0x26, "k": 0x27, "l": 0x28,
    "semicolon": 0x29, "apostrophe": 0x2A,
    "colon": 0x29, "quotedbl": 0x2A,
    "z": 0x31, "x": 0x32, "c": 0x33, "v": 0x34,
    "b": 0x35, "n": 0x36, "m": 0x37, "comma": 0x38,
    "period": 0x39, "slash": 0x3A,
    "less": 0x38, "greater": 0x39, "question": 0x3A,
    "space": 0x40, "backspace": 0x41, "tab": 0x42,
    "return": 0x44, "escape": 0x45, "delete": 0x46,
    "up": 0x4C, "down": 0x4D, "right": 0x4E, "left": 0x4F,
    "f1": 0x50, "f2": 0x51, "f3": 0x52, "f4": 0x53, "f5": 0x54,
    "f6": 0x55, "f7": 0x56, "f8": 0x57, "f9": 0x58, "f10": 0x59,
    "help": 0x5F, "shift_l": 0x60, "shift_r": 0x61,
    "caps_lock": 0x62, "control_l": 0x63, "control_r": 0x63,
    "alt_l": 0x64, "alt_r": 0x65,
    "meta_l": 0x66, "super_l": 0x66, "win_l": 0x66,
    "meta_r": 0x67, "super_r": 0x67, "win_r": 0x67,
}

RAW_KEYS.update({
    "insert": 0x5F, "menu": 0x67, "kp_enter": 0x43,
    "kp_0": 0x0F, "kp_1": 0x1D, "kp_2": 0x1E, "kp_3": 0x1F,
    "kp_4": 0x2D, "kp_5": 0x2E, "kp_6": 0x2F,
    "kp_7": 0x3D, "kp_8": 0x3E, "kp_9": 0x3F,
    "kp_decimal": 0x3C, "kp_add": 0x5E, "kp_subtract": 0x4A,
    "kp_multiply": 0x5D, "kp_divide": 0x5C,
    "kp_insert": 0x0F, "kp_end": 0x1D, "kp_down": 0x1E,
    "kp_next": 0x1F, "kp_left": 0x2D, "kp_begin": 0x2E,
    "kp_right": 0x2F, "kp_home": 0x3D, "kp_up": 0x3E,
    "kp_prior": 0x3F, "kp_delete": 0x3C, "sterling": 0x03,
})

# Windows Tk keycodes are virtual-key codes, independent of Shift/Caps Lock.
# Prefer them for printable keys so releasing Shift before a letter still
# releases the same remote key. The Amiga's selected keymap controls symbols.
WINDOWS_KEYS = {ord(k.upper()): v for k, v in RAW_KEYS.items() if len(k) == 1 and k.isascii() and k.isalnum()}
WINDOWS_KEYS.update({
    0xBA: 0x29, 0xBB: 0x0C, 0xBC: 0x38, 0xBD: 0x0B,
    0xBE: 0x39, 0xBF: 0x3A, 0xC0: 0x00, 0xDB: 0x1A,
    0xDC: 0x0D, 0xDD: 0x1B, 0xDE: 0x2A, 0xE2: 0x30,
    0x60: 0x0F, 0x61: 0x1D, 0x62: 0x1E, 0x63: 0x1F,
    0x64: 0x2D, 0x65: 0x2E, 0x66: 0x2F, 0x67: 0x3D,
    0x68: 0x3E, 0x69: 0x3F, 0x6A: 0x5D, 0x6B: 0x5E,
    0x6D: 0x4A, 0x6E: 0x3C, 0x6F: 0x5C,
})


def raw_key(keysym: str, keycode: int = 0, windows: bool = False) -> int | None:
    if windows and keycode in WINDOWS_KEYS:
        return WINDOWS_KEYS[keycode]
    return RAW_KEYS.get(keysym.lower())


def display_geometry(width: int, height: int, area_width: int, area_height: int,
                     scale: str) -> tuple[int, int, int, int]:
    if scale == "Fit":
        factor = min(max(1, area_width) / width, max(1, area_height) / height)
        dw, dh = max(1, int(width * factor)), max(1, int(height * factor))
    else:
        factor = int(scale.rstrip("x"))
        dw, dh = width * factor, height * factor
    return max(0, (area_width - dw) // 2), max(0, (area_height - dh) // 2), dw, dh


def pointer_position(x: int, y: int, geometry: tuple[int, int, int, int],
                     width: int, height: int, clamp: bool = False) -> tuple[int, int] | None:
    left, top, dw, dh = geometry
    if not clamp and not (left <= x < left + dw and top <= y < top + dh):
        return None
    return (max(0, min(width - 1, (x - left) * width // dw)),
            max(0, min(height - 1, (y - top) * height // dh)))
