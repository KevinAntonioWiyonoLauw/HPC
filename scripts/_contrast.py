import colorsys

def hsl_to_rgb(h, s, l):
    r, g, b = colorsys.hls_to_rgb(h/360.0, l/100.0, s/100.0)
    return (round(r*255), round(g*255), round(b*255))

def lin(c):
    c = c/255.0
    return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4

def lum(rgb):
    r, g, b = rgb
    return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)

def ratio(a, b):
    la, lb = lum(a), lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi+0.05)/(lo+0.05)

def hexs(rgb):
    return "#%02X%02X%02X" % rgb

pairs = [
    # name, (fg h,s,l), (bg h,s,l)
    ("DARK muted-fg on background", (215,20.2,65.1),(222.2,47.4,7)),
    ("DARK muted-fg on muted(badge)", (215,20.2,65.1),(217.2,32.6,17.5)),
    ("DARK foreground on card", (210,40,96),(222.2,44,10)),
    ("DARK white on success(142,71,45)", None, (142,71,45)),
    ("DARK primary-fg on primary", (210,40,98),(217.2,91.2,59.8)),
    ("LIGHT muted-fg on white", (215.4,16.3,46.9),(0,0,100)),
    ("LIGHT white on primary", None, (221.2,83.2,53.3)),
    ("LIGHT white on success(142,71,45)", None, (142,71,45)),
    ("DARK success-text on success/15 over card", (142,71,45),(142,71,45)),
]

for name, fg, bg in pairs:
    bgr = hsl_to_rgb(*bg)
    if fg is None:
        fgr = (255,255,255)
    else:
        fgr = hsl_to_rgb(*fg)
    r = ratio(fgr, bgr)
    print(f"{name:48} fg={hexs(fgr)} bg={hexs(bgr)} ratio={r:.2f} normal={'PASS' if r>=4.5 else 'FAIL'} large={'PASS' if r>=3 else 'FAIL'}")
