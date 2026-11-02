# Solar Cover

Controle solar de cortinas de rolo para o Home Assistant. **Uma cortina = um
dispositivo**, com sensores que explicam *por que* a cortina está onde está.

A cortina é posicionada pela geometria real do sol (azimute, elevação, orientação
da fachada, distância até a porta e altura da borda), para manter a porta na
sombra com a cortina o mais aberta possível e o mínimo de movimentos do motor.
A dedução está em [docs/GEOMETRIA.md](docs/GEOMETRIA.md).

## Instalação

**HACS:** Integrações → menu → *Repositórios personalizados* → adicione este
repositório como *Integração* → instale **Solar Cover** → reinicie o Home Assistant.

**Manual:** copie `custom_components/solar_cover` para a pasta `custom_components`
do seu Home Assistant e reinicie.

Requer Home Assistant 2026.2 ou mais novo (versão em que os testes rodam).

## Configuração

*Configurações → Dispositivos e serviços → Adicionar integração → Solar Cover.*

1. **Cortina:** escolha uma entidade `cover` com suporte a posição. As demais
   cortinas (`blind`, `curtain`, `shade`, `shutter`, `awning`) aparecem sozinhas em
   *Descobertos* depois que a primeira estiver configurada.
2. **Geometria:** azimute da fachada (bússola; 270° = oeste) e as cotas em cm.
   Os valores iniciais são os do croqui da cozinha.
3. **Sensores e horizonte (opcionais):** temperatura, luminosidade, alarme e o
   perfil do prédio vizinho. Sensor não informado deixa de ser exigido.

A posição do sol vem da latitude/longitude do Home Assistant (*Configurações →
Sistema → Geral*), calculada na própria integração a cada 30 s.

Tudo (geometria, sensores, horizonte) pode ser alterado depois em *Configurar*.

### Perfil do horizonte (prédio vizinho)

Pontos `azimute:elevação` do topo do prédio, separados por `;`. Entre os pontos a
elevação é interpolada; fora deles não há obstrução. O sol só conta como visível
0,5° acima do topo. Exemplos:

```
262:15; 291:15                 # topo plano a 15° entre 262° e 291° (a regra antiga)
250:0; 250:18; 280:18; 280:0   # prédio com quinas verticais
```

### Prédio como parede (a sombra sobe pela cortina)

O perfil de horizonte é um interruptor: abaixo do topo, o sol está bloqueado e a cortina
abre. Na prática a sombra de um prédio sobe pela cortina aos poucos, e o sol ainda entra
pela parte de cima do vão. Para seguir essa sombra, configure o prédio como uma parede de
topo plano, paralela à fachada, nos *números* de configuração da cortina:

| Número | O que é |
|---|---|
| Distância do prédio | m entre a cortina e a parede, na perpendicular à fachada |
| Altura do prédio | m do topo acima do piso de referência da cortina |
| Azimute do prédio (início / fim) | faixa de azimutes em que o prédio é visto da cortina (a ordem não importa; vale o arco menor) |

Com os quatro preenchidos, a borda da cortina sobe até a altura da sombra
(`altura − distância · tan φ`) menos a margem, e o motivo passa a ser `building_edge`.
Quando a sombra cobre todo o vão, o motivo é `building_shadow` e a cortina abre.
O sensor **Altura da sombra do prédio** mostra o valor calculado, para você comparar com
o que enxerga. **Deixe o perfil de horizonte vazio para o mesmo prédio**, senão ele abre
a cortina antes da hora. Veja `docs/GEOMETRIA.md`, seção 7.

## Entidades de cada cortina

| Entidade | O que é |
|---|---|
| `sensor` **Posição desejada** | resultado final; atributos trazem todos os critérios (`checks`), ângulos e alturas |
| `sensor` **Motivo** | por que a posição tem esse valor (ver ordem abaixo) |
| `sensor` **Estado do controle** | na posição, movendo, aguardando, pausado, desligado, parado, indisponível |
| `sensor` diagnósticos | ângulo do sol na fachada, ângulo de perfil, queda do raio, **altura da porta iluminada**, horizonte do prédio; azimute/elevação do sol (desabilitados por padrão) |
| `binary_sensor` | sol na fachada · luminosidade alta · sombra do prédio · pausa por ajuste manual |
| `switch` **Controle automático** | liga/desliga a integração (a cortina fica onde está) |
| `button` **Retomar controle** | encerra a pausa por ajuste manual |
| `number` (configuração) | temperatura mínima · lux para ligar/desligar · atraso do lux · margem de sombra · tolerância · intervalo mínimo · pausa após ajuste manual |

O dispositivo da cortina aparece como "conectado via" o dispositivo físico da
entidade `cover`, quando ela tem um.

## Como a posição é decidida

O **primeiro critério que falha** define o motivo e a posição padrão (100 %,
aberta). Todos aparecem em `checks`.

| # | Critério | Motivo se falhar |
|--:|---|---|
| 1 | sol acima do horizonte | `sun_below_horizon` |
| 2 | sol de frente para a fachada (`\|Δ\| <` limite) | `sun_not_on_facade` |
| 3 | alarme desarmado (se configurado) | `alarm` / `alarm_unavailable` |
| 4 | temperatura **acima** do mínimo (se configurada) | `temperature_low` / `temperature_unavailable` |
| 5 | luminosidade alta, com histerese e atraso (se configurada) | `low_light` |
| 6 | sol acima do topo do prédio (perfil de horizonte) e sombra do prédio não cobre todo o vão | `building_shadow` |
| — | tudo ok → posição geométrica | `geometric` |
| — | tudo ok e a sombra do prédio na cortina é mais alta que a queda do raio → borda na sombra | `building_edge` |

Se o motivo for **alarme ou temperatura indisponíveis**, a cortina **não se move**
(estado `hold`) em vez de abrir às cegas.

### Luminosidade

Gatilho com dois limiares e atraso: liga com `lux ≥ lux_on` por N minutos e desliga
com `lux < lux_off` por N minutos; entre os dois mantém o estado. Se o sensor fica
*atrás* da cortina, a leitura cai quando ela fecha, então use `lux_off` bem abaixo
de `lux_on`. Substitui o `input_boolean` e a automação com `toggle`. O estado
sobrevive a reinícios.

### Movimento

- **Aberta demais** (mais de 1 ponto acima do desejado): fecha logo e passa
  `tolerância − 2` pontos do alvo, para o próximo ajuste demorar.
- **Fechada demais**: só abre quando a diferença chega à `tolerância` (mínimo 2) e
  depois do `intervalo mínimo`.
- Cortina em movimento ou comando idêntico recém-enviado: nada é reenviado.
- **Ajuste manual:** se a cortina se mexe sem comando da integração (fora dos 3 min
  seguintes a um comando), o controle pausa por `pausa após ajuste manual` minutos
  (0 desativa). *Retomar controle* encerra a pausa.

Simulando 30/10 em São Paulo (fachada a 278°): 25 movimentos por tarde, sem sol na
porta causado pela política de movimento.

## Migrando do template e das automações antigas

| Antes | Agora |
|---|---|
| `cortinasettemp` | número *Temperatura mínima* |
| `cortinasetlux` / `cortinasetluzinf` | números *Lux para ligar* / *Lux para desligar* |
| `cortinasetazimuteoff/on` | **somem**: vêm do azimute da fachada e do ângulo máximo de incidência |
| `cortinasetazimuteprediooff/on` + regra 15°/20°/40 % | perfil do horizonte, ex. `off:15; on:15` (a faixa de 40 % some: acima do topo vale o cálculo) |
| `cortina_distancia_adicional_sombra` | número *Margem de sombra* (cm, **vertical**; positivo fecha mais) |
| `cozinhacortinacontroleautomatico` | switch *Controle automático* |
| `cortina_controle_luminosidade` + automação de lux | binary_sensor *Luminosidade alta* |
| `sensor.cortina_posicao_desejada` + automação de posição | sensor *Posição desejada* (o comando ao motor é feito pela integração) |

Desative as automações antigas ao ligar a integração para não haver dois
controladores comandando o mesmo motor.

## Limitações conhecidas

- Assume que o sol passa pela cortina antes de chegar à porta (ver hipóteses em
  `docs/GEOMETRIA.md`) e que não há vazamento lateral.
- Curso da borda linear na posição.
- A entidade `cover` precisa reportar `current_position`.
- O `entity_id` da cortina é guardado na configuração: renomeá-lo exige reconfigurar.
- O número *Temperatura mínima* é em °C; sensores em °F não são convertidos.

## Desenvolvimento

```bash
pip install -r requirements_test.txt
pytest          # núcleo + Home Assistant de verdade (pytest-homeassistant-custom-component)
ruff check . && ruff format --check .
```

O núcleo (`custom_components/solar_cover/core/`) é Python puro, sem Home Assistant:
geometria, horizonte, posição do sol, decisão, filtro de lux e política de movimento.

### Release

A versão vem de `custom_components/solar_cover/manifest.json` (`version`). Ao dar
push em `main`, o workflow **Auto tag** espera o workflow **Tests** passar e cria a
tag `v<versão>` com um release (notas geradas automaticamente), se essa tag ainda
não existir. Para lançar uma nova versão, aumente `version` no manifest e faça push.
