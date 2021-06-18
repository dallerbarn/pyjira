import colorsys


def hls_to_hex(hls):
    h, l, s = hls
    return rgb_to_hex(colorsys.hls_to_rgb(h, l, s))


def hex_to_hls(hex: str):
    return rgb_to_hls(hex_to_rgb(hex))


def rgb_to_hls(rgb):
    r, g, b = rgb
    return colorsys.rgb_to_hls(r, g, b)


def hex_to_rgb(value: str):
    value = value.lstrip('#')
    lv = len(value)
    return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))


def rgb_to_hex(rgb):
    r, g, b = rgb
    return '#{:02x}{:02x}{:02x}'.format(int(round(r, 0)), int(round(g, 0)), int(round(b, 0)))

