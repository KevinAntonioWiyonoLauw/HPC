import colorsys
def hsl(h,s,l):
    r,g,b=colorsys.hls_to_rgb(h/360.0,l/100.0,s/100.0); return (round(r*255),round(g*255),round(b*255))
def lin(c):
    c/=255.0; return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
def L(rgb): r,g,b=rgb; return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
def ratio(a,b):
    la,lb=L(a),L(b); hi,lo=max(la,lb),min(la,lb); return (hi+0.05)/(lo+0.05)
def hx(rgb): return "#%02X%02X%02X"%rgb
WHITE=(255,255,255); NEARWHITE=hsl(210,40,98)

print("== SUCCESS candidates: white text on green, and green text on white ==")
for l in [28,30,32,34,36,40,45]:
    bg=hsl(142,72,l)
    print(f" success l={l} bg={hx(bg)} whiteOn={ratio(WHITE,bg):.2f} greenOnWhite={ratio(bg,WHITE):.2f}")

print("== PRIMARY candidates: white text on blue ==")
for l in [40,42,44,46,48,53]:
    bg=hsl(221.2,83.2,l)
    print(f" primary l={l} bg={hx(bg)} whiteOn={ratio(NEARWHITE,bg):.2f}")

print("== success-foreground dark on green(l=45) ==")
green=hsl(142,71,45)
for dl in [10,14,18]:
    dark=hsl(150,40,dl)
    print(f" dark l={dl} {hx(dark)} on green={ratio(dark,green):.2f}")
