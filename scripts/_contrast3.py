import colorsys
def hsl(h,s,l):
    r,g,b=colorsys.hls_to_rgb(h/360.0,l/100.0,s/100.0); return (round(r*255),round(g*255),round(b*255))
def lin(c):
    c/=255.0; return c/12.92 if c<=0.03928 else ((c+0.055)/1.055)**2.4
def L(rgb): r,g,b=rgb; return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)
def ratio(a,b):
    la,lb=L(a),L(b); hi,lo=max(la,lb),min(la,lb); return (hi+0.05)/(lo+0.05)
def hx(rgb): return "#%02X%02X%02X"%rgb
W=(255,255,255)

print("== destructive light (0 72% 51%) white text ==", round(ratio(W,hsl(0,72,51)),2))
print("== dark primary-foreground(222.2 47.4 11.2) on dark primary(217.2 91.2 59.8) ==",
      round(ratio(hsl(222.2,47.4,11.2),hsl(217.2,91.2,59.8)),2))
print("== dark success-foreground candidates (dark text on green 142 71 45) ==")
for l in [8,10,12]:
    print("  fg l=",l, hx(hsl(150,40,l)), "ratio=", round(ratio(hsl(150,40,l),hsl(142,71,45)),2))

print("== INPUT border non-text 3:1 checks ==")
# dark: input on card(222.2 44 10) and on background(222.2 47.4 7)
cardd=hsl(222.2,44,10); bgd=hsl(222.2,47.4,7)
for l in [30,34,38,42,46,50]:
    b=hsl(217.2,30,l)
    print(f"  dark border l={l} {hx(b)} on card={ratio(b,cardd):.2f} on bg={ratio(b,bgd):.2f}")
cardl=hsl(0,0,100); bgl=hsl(0,0,100)
for l in [60,64,68,72,75]:
    b=hsl(214,20,l)
    print(f"  light border l={l} {hx(b)} on white={ratio(b,cardl):.2f}")
