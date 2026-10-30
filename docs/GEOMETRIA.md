# Geometria e decisão

Este documento explica **de onde vem cada número** que a integração usa, para que
o modelo possa ser conferido contra a realidade em vez de aceito por funcionar.

## 1. Cotas (croqui da cozinha)

Todas em cm, medidas a partir do piso.

| Cota | Valor | Para que serve |
|---|---:|---|
| Centro do rolo ao piso (100 %) | 255 | posição da borda aberta |
| Borda ao centro do rolo (100 %) | 9 | borda aberta = 255 − 9 = **246** |
| Borda ao piso (0 %) | 9 | borda fechada = **9** |
| Vão livre sob a viga | 230 | topo do vão por onde o sol entra |
| Distância cortina → porta (D) | 120 | queda do raio |
| Altura da porta | 220 | limita a altura iluminada reportada |

A borda inferior percorre 246 − 9 = **237 cm** entre 0 % e 100 %, então
`altura da borda = 9 + posição/100 · 237` (curso linear).

## 2. Hipóteses a confirmar

1. **O sol passa primeiro pela cortina e só depois chega à porta** (cortina sob a
   viga, na borda da varanda, a D da porta). Se a cortina estiver *depois* da
   porta, o modelo não se aplica.
2. A viga bloqueia tudo acima de 230 cm: abrir além disso não deixa entrar mais sol.
3. O curso da borda é linear na posição (a variação do diâmetro do rolo é desprezada).
4. A cortina é larga o bastante para que **não haja vazamento lateral**. Com sol
   oblíquo o raio se desloca `D · tan Δ` para o lado; a largura da cortina e da
   porta não entram no modelo.

## 3. Dedução

Seja `γ` o azimute para onde a fachada aponta e `Δ = azimute_sol − γ`
(normalizado para −180°…180°). O sol só incide se a elevação é positiva e
`|Δ| < limite` (padrão 85°).

Um raio de luz anda no sentido oposto ao do sol. Sua componente horizontal
perpendicular à fachada é `cos(elev) · cos(Δ)` e a vertical é `−sen(elev)`.
Para cruzar a distância `D` entre cortina e porta ele desce

```
s = D · tan(elev) / cos(Δ)          (queda do raio)
```

e o **ângulo de perfil** é `φ = atan(tan(elev) / cos Δ)`, de modo que `s = D · tan φ`.
Com o sol de frente (`Δ = 0`) isso se reduz a `D · tan(elev)`, a fórmula antiga.

Um raio que atravessa o plano da cortina na altura `z` chega à porta na altura
`z − s`. Os raios que passam pelo vão cobrem `z ∈ [0, e)`, onde `e` é a altura da
borda inferior (os de cima são bloqueados pela cortina e pela viga). Nenhum deles
atinge a porta se `z − s < 0` para todos, isto é:

```
e ≤ s − margem
posição = (e − 9) / 237 · 100        (limitada a 0…100)
```

Casos de borda:

- `s − margem < 9`: sol rasante demais, a cortina fica em 0 % e ainda sobra um vão
  de 9 cm no piso (limite físico, reportado em "Altura da porta iluminada").
- `s − margem ≥ 230`: acima da viga, 100 %.
- Altura iluminada da porta: `min(max(0, min(e, 230) − s), 220)`.

A **margem** é vertical (cm): positiva fecha mais. Na fórmula antiga a margem
*encurtava D*, o que reduz `s` e também fecha mais, mas de forma não linear e sem
significado físico direto.

## 4. Exemplo

30/10/2026 às 16:00 em São Paulo, fachada a 278°:

| Grandeza | Valor |
|---|---:|
| Azimute / elevação do sol | 267,2° / 30,5° |
| Δ | −10,8° |
| Queda do raio `s` | 120 · tan 30,5° / cos 10,8° = 71,96 cm |
| Borda com margem de 5 cm | 66,96 cm |
| Posição | (66,96 − 9) / 237 = **24,5 %** |

## 5. Como foi validado

`tests/core/test_geometry.py` faz um **traçado de raios independente**: constrói o
vetor do sol a partir do azimute/elevação, projeta na normal da fachada e deixa
raios atravessarem o vão, sem usar `Δ`, ângulo de perfil nem as fórmulas acima.
Para 15 azimutes × 8 elevações × 2 margens ele confirma que:

- na posição calculada **nenhum raio atinge a porta** (exceto o limite físico dos 9 cm);
- **abrir 1 % a mais já deixa sol entrar**, ou seja, a posição é a máxima segura;
- a altura iluminada da fórmula fechada coincide com a do traçado.

O cálculo solar interno (`core/sun.py`, algoritmo NOAA) é comparado ao `astral`
(o mesmo do `sun.sun`) em 4 locais e o ano todo, com diferença máxima de 0,25°.

## 6. Comparação com o template antigo

Com as cotas reais e margem zero, o template antigo (`1 − (2,2 − h)/2,5`) pede
uma cortina mais aberta do que a necessária para manter a porta na sombra:

| Elevação | Δ | Antigo | Novo | Porta iluminada no antigo |
|---:|---:|---:|---:|---:|
| 10° | 0° | 20,5 % | 5,1 % | 36 cm |
| 20° | 0° | 29,5 % | 14,6 % | 35 cm |
| 30,5° | −10,8° | 40,3 % | 26,6 % | 33 cm |
| 45° | 0° | 60,0 % | 46,8 % | 31 cm |

A diferença vem principalmente do `2,5` da fórmula: é a altura do centro do rolo e
não o curso da borda (237 cm entre 9 e 246 cm), o que deixava a borda cerca de 30 cm
acima do limite do raio. O `Δ` pesa pouco nas linhas acima (sol quase de frente),
mas cresce com o sol oblíquo, que a fórmula antiga ignorava. Se você compensava com a
"distância adicional de sombra", o efeito pode ter sido parcialmente mascarado.
