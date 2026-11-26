"""Derive and check the estimate palette.

Prints each level's hex with its perceived lightness (OKLab L, CIE L*, WCAG
luminance) and its OKLab L under simulated protanopia, deuteranopia and
tritanopia (Machado et al. 2009, severity 1.0). Exits 1 unless lightness
falls by at least MIN_GAP from simple to moderate to complex in every view.

Usage: python3 palette.py [L,H,C L,H,C L,H,C]
"""
import math, sys
def oklch_to_lin(L,C,H):
    a=C*math.cos(math.radians(H)); b=C*math.sin(math.radians(H))
    l=(L+0.3963377774*a+0.2158037573*b)**3
    m=(L-0.1055613458*a-0.0638541728*b)**3
    s=(L-0.0894841775*a-1.2914855480*b)**3
    return (4.0767416621*l-3.3077115913*m+0.2309699292*s,
            -1.2684380046*l+2.6097574011*m-0.3413193965*s,
            -0.0041960863*l-0.7034186147*m+1.7076147010*s)
def lin_to_oklabL(rgb):
    r,g,b=rgb
    l=0.4122214708*r+0.5363325363*g+0.0514459929*b
    m=0.2119034982*r+0.6806995451*g+0.1073969566*b
    s=0.0883024619*r+0.2817188376*g+0.6299787005*b
    l,m,s=[max(x,0)**(1/3) for x in (l,m,s)]
    return 0.2104542553*l+0.7936177850*m-0.0040720468*s
def enc(c): return 12.92*c if c<=0.0031308 else 1.055*c**(1/2.4)-0.055
def dec(c): return c/12.92 if c<=0.04045 else ((c+0.055)/1.055)**2.4
def hexof(rgb): return '#'+''.join('%02X'%round(max(0,min(1,enc(c)))*255) for c in rgb)
def hex_to_lin(h): return tuple(dec(int(h[i:i+2],16)/255) for i in (1,3,5))
def Y(rgb): return 0.2126*rgb[0]+0.7152*rgb[1]+0.0722*rgb[2]
def Lstar(rgb):
    y=Y(rgb); return 116*y**(1/3)-16 if y>0.008856 else 903.3*y
CVD={'protan':[[0.152286,1.052583,-0.204868],[0.114503,0.786281,0.099216],[-0.003882,-0.048116,1.051998]],
     'deutan':[[0.367322,0.860646,-0.227968],[0.280085,0.672501,0.047413],[-0.011820,0.042940,0.968881]],
     'tritan':[[1.255528,-0.076749,-0.178779],[-0.078411,0.930809,0.147602],[0.004733,0.691367,0.303900]]}
def sim(rgb,m): return tuple(max(0,min(1,sum(m[i][j]*rgb[j] for j in range(3)))) for i in range(3))
def maxC(L,H):
    lo,hi=0,0.4
    for _ in range(40):
        mid=(lo+hi)/2
        ok=all(-1e-6<=c<=1+1e-6 for c in oklch_to_lin(L,mid,H))
        lo,hi=(mid,hi) if ok else (lo,mid)
    return lo
def contrast(a,b):
    ya,yb=sorted((Y(a),Y(b)),reverse=True); return (ya+0.05)/(yb+0.05)
# The palette in skills/estimate/SKILL.md, as OKLCH lightness, hue, chroma.
spec=[('simple',0.90,150,0.15),('moderate',0.79,95,0.165),('complex',0.48,27,0.19)]
if len(sys.argv)>1:
    spec=[(n,float(a),float(b),float(c)) for n,(a,b,c) in zip(('simple','moderate','complex'),[x.split(',') for x in sys.argv[1:]])]
cols=[]
for n,L,H,Cw in spec:
    C=min(Cw,maxC(L,H)); h=hexof(oklch_to_lin(L,C,H)); cols.append((n,h,L,C,H))
print('level     hex      oklch(L C H)        OKLab-L  CIE-L*  WCAG-Y | L under protan deutan tritan | text  contrast')
for n,h,L,C,H in cols:
    rgb=hex_to_lin(h)
    ls=[lin_to_oklabL(sim(rgb,CVD[k])) for k in CVD]
    cb,cw=contrast(rgb,hex_to_lin('#111111')),contrast(rgb,(1,1,1))
    t=('#111111',cb) if cb>cw else ('#FFFFFF',cw)
    print(f'{n:9} {h}  {L:.2f} {C:.3f} {H:5.0f}     {lin_to_oklabL(rgb):.3f}   {Lstar(rgb):5.1f}   {Y(rgb):.3f} |        {ls[0]:.3f}  {ls[1]:.3f}  {ls[2]:.3f} | {t[0]} {t[1]:.1f}:1  simhex '+' '.join(hexof(sim(rgb,CVD[k])) for k in CVD))

MIN_GAP=0.09
views={'normal':lambda c:c, **{k:(lambda c,m=m:sim(c,m)) for k,m in CVD.items()}}
bad=[]
for name,f in views.items():
    ls=[lin_to_oklabL(f(hex_to_lin(h))) for _,h,*_ in cols]
    if not (ls[0]-ls[1]>=MIN_GAP and ls[1]-ls[2]>=MIN_GAP): bad.append((name,[round(x,3) for x in ls]))
print('OK: lightness falls simple > moderate > complex in every view' if not bad else f'FAIL: {bad}')
sys.exit(1 if bad else 0)
