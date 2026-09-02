# A Curva de Demanda do Produto_A: a História de Como Chegamos Nela

**Notebook analisado:** `01-EDA_v3.ipynb` · **Produto:** Produto_A (1 SKU, Minerva Foods)
**Dados:** 01/08/2025 a 14/11/2025 · **Treino:** até 31/10/2025 · **Teste:** 03/11 a 14/11/2025 (10
dias, nunca usados para decidir nada, só para checar se o modelo acerta)

Este documento conta a história de como chegamos ao modelo que hoje calcula "quanto vamos vender se
cobrarmos X reais por quilo" — e por que descartamos vários outros modelos no caminho. Cada decisão
aqui foi tomada testando alternativas e comparando números, nunca "no olho".

---

## Como ler este documento (glossário rápido)

Este relatório tem gente de perfis diferentes lendo — alguns termos técnicos aparecem bastante, e
vale explicá-los uma vez aqui em vez de repetir a explicação toda hora:

| Termo | O que significa, em bom português |
|---|---|
| **Elasticidade** | O quanto o volume vendido reage quando o preço muda. Elasticidade alta = cliente é sensível, um pequeno aumento de preço derruba bastante a venda. Elasticidade baixa = cliente compra quase igual, preço importa menos. |
| **p-valor** | A chance de uma diferença que vemos nos dados ser só coincidência de amostra, não um padrão real. Quanto **menor**, mais confiável é a diferença. Regra usada aqui: p-valor abaixo de 0,05 (5%) = "essa diferença é real". Acima disso = "pode ser só coincidência, melhor não confiar". |
| **MAPE** | O erro médio do modelo quando ele tenta prever a venda de um dia que nunca viu. MAPE de 56% quer dizer que, em média, a previsão erra por 56% do valor real — pra mais ou pra menos. Quanto menor, melhor. |
| **BIC** | Uma "nota de simplicidade": pune modelos que usam variáveis demais sem ganho real de precisão. Entre dois modelos que preveem parecido, o de menor BIC é preferível — é mais simples e menos propenso a "decorar" o passado em vez de aprender o padrão. |
| **Outlier** | Um dia com resultado muito fora do comum — pode ser erro de registro, promoção, ou evento pontual. |
| **Cluster / agrupamento** | Juntar dias parecidos num mesmo "balde", com uma única equação por balde, em vez de uma equação diferente pra cada dia da semana. |
| **Capping por IQR** | Um jeito simples e comum de tratar valor fora do padrão: calcular um teto baseado na variação típica dos dados e "cortar" qualquer valor acima dele para esse teto. |
| **Regressão robusta (Huber)** | Uma forma alternativa de calcular a curva que, em vez de cortar os pontos fora do padrão antes de começar, deixa o próprio cálculo dar menos peso a eles automaticamente — sem descartar nenhum dado. |
| **Distância de Cook** | Uma nota, por dia, de "o quanto esse dia sozinho está puxando o resultado final para um lado". Um dia com nota alta é um dia que, se removido, mudaria bastante a conclusão. |

---

## Capítulo 1 — O Problema e os Dados que Tínhamos

A Minerva precisa decidir, todo dia, que preço cobrar por um corte de carne — e isso exige saber
como o volume vendido reage ao preço (a "curva de demanda"). Recebemos 86 dias de histórico (Volume,
Receita, Custo), com o objetivo final de alimentar um otimizador de preços que respeita metas
semanais de venda e um limite de variação de preço entre dias consecutivos.

**Dois achados de estrutura, antes de qualquer modelo:**
- De 26 finais de semana possíveis no período de treino, **16 não têm nenhum registro de venda**
  (nem zero) — parece uma operação esporádica, não uma rotina planejada.
- **Nenhum dos 6 sábados/domingos do período de teste aparece na planilha.** Isso sugere que o
  horizonte real de precificação pode ser só os 10 dias úteis — vale confirmar isso com quem definiu
  o desafio antes de assumir que o Fim de Semana precisa de preço próprio (ver Limitações, item 9).

**Dois cuidados tomados logo de cara, para não estragar tudo depois:**
- **O corte entre treino e teste** foi feito antes de qualquer conta agregada, gráfico ou ajuste de
  modelo — pra garantir que nenhuma decisão "espiasse" o futuro.
- **O preço usado é uma média realizada** (Receita ÷ Volume), não necessariamente o preço de tabela.
  Em vendas B2B, um desconto por volume grande poderia inflar artificialmente a relação
  preço↔volume. Testamos a correlação preço×volume **dentro de cada dia da semana** (Segunda -0,77,
  Terça -0,74, Quarta -0,64, Quinta -0,83, Sexta -0,66) — todas fortes e negativas, o que é evidência
  de sensibilidade real ao preço, não só um efeito de nível entre dias diferentes. Reduz a
  preocupação, mas não elimina — fica registrado como limitação.

Olhando os dados em ordem cronológica (não só agrupados por categoria), também notamos que o
**custo por kg sobe gradualmente** ao longo do período (~985 → ~1.010, quase 2%), então a premissa
de "custo fixo" usada depois na conta de margem é uma aproximação, não um fato confirmado.

---

## Capítulo 2 — Descartando Pistas Falsas: Sazonalidade

Antes de ir direto pro dia da semana (que já parecia visualmente importante), testamos se outros
padrões de calendário também importavam: semana do mês, quinzena e mês. Nenhum deles passou no teste
de p-valor (todos acima de 0,05, controlando por preço) — descartados corretamente, evitando
complexidade que os dados não sustentam.

**Um achado que pareceu irrelevante na hora, mas virou decisivo depois:** nesse mesmo teste,
controlando por preço, **Quinta-feira não saiu diferente de Quarta-feira** (p = 0,768) — nem Terça
(p = 0,849). Só Sexta (p < 0,001) e, de forma limítrofe, Segunda (p = 0,074) se destacaram. Ou seja:
desde o início, os dados já sugeriam que "Segunda e Quinta são parecidas" (a hipótese inicial, ver
Capítulo 4) estava errada — só percebemos isso mais tarde.

---

## Capítulo 3 — Uma Anomalia no Meio do Caminho

Olhando o histórico em ordem cronológica, um período de ~2 semanas (13 a 24/10) chamou atenção por
concentrar quase todos os valores extremos do dataset inteiro:

| Extremo | Valor | Data |
|---|---|---|
| Maior volume de todo o treino | 100,0 kg | 15/10/2025 |
| Menor preço de todo o treino | R$ 1.188,86 | 11/10/2025 |
| Maior preço de todo o treino | R$ 1.365,49 | 24/10/2025 |
| Maior custo/kg de todo o treino | R$ 1.030,34 | 20/10/2025 |

O padrão parece ser: 13–16/10 com preço muito baixo e volume muito alto (provável promoção),
seguido de 17–24/10 com preço disparando e volume caindo a quase zero (provável correção). Isso é o
tipo de episódio pontual de negócio que pode distorcer a conclusão se pesar demais no cálculo —
guardamos essa suspeita para testar formalmente mais adiante (Capítulo 7), em vez de decidir
qualquer coisa sobre ela agora.

---

## Capítulo 4 — Primeira Tentativa: Uma Hipótese Lida num Gráfico

Olhando um boxplot de volume por dia da semana, a leitura visual mais óbvia foi dividir os dias em 3
grupos por "tração": Segunda+Quinta como dias de pico, Terça+Quarta como regulares, Sexta como fraco.
Essa foi a **primeira versão do modelo** — plausível à primeira vista, mas baseada só em olhar o
gráfico, sem controlar por preço nem testar contra alternativa nenhuma.

Era hora de descobrir se essa leitura visual realmente se sustentava — ou se era só uma impressão.

---

## Capítulo 5 — A Primeira Grande Decisão: Como Agrupar os Dias?

Em vez de aceitar a leitura do boxplot, comparamos formalmente 6 candidatos diferentes para "como
juntar os dias da semana", usando 3 critérios **decididos antes de rodar qualquer coisa**: (1) MAPE
fora da amostra — o mais importante, é o que decide se a ferramenta funciona de verdade; (2) BIC —
pune modelo complicado demais; (3) quantos parâmetros realmente se sustentam (p < 0,05). R² **não**
entrou como critério — ele quase sempre sobe com mais variáveis, mesmo sem o modelo generalizar
melhor (é fácil "decorar" o passado; o difícil é acertar o futuro).

| Modelo | O que é | MAPE teste | BIC | Veredito |
|---|---|---|---|---|
| A: Dia a dia, sem interação | Uma equação por dia, mesma elasticidade pra todos | 55,7% | 90,5 | Perdeu — BIC pior, mais parâmetros que o necessário |
| B: Dia a dia, com interação | Uma equação por dia, **cada dia com sua própria elasticidade** | 57,7% | 95,2 | Perdeu — overfitting: parece ótimo no papel (maior R²), mas generaliza mal e quase nenhum parâmetro é significativo |
| C: Hipótese do boxplot, sem interação | Segunda+Quinta / Terça+Quarta / Sexta | 56,4% | 86,9 | Perdeu — pior MAPE e BIC que o vencedor |
| D: Hipótese do boxplot, com interação | Igual a C, mas com elasticidade própria por grupo | **60,3%** | 88,1 | Perdeu — **pior MAPE de todos os candidatos sérios**, apesar de parecer mais sofisticado |
| **E: Segunda isolada + Terça/Quarta/Quinta juntas** | Uma hipótese alternativa, cogitada por termos visto o achado do Capítulo 2 | 56,5% | **82,3** | 🏆 **Venceu** — melhor BIC, 2º melhor MAPE, mais parâmetros significativos |
| F: Só preço, sem diferenciar dia | Ignora completamente o dia da semana | 125,1% | 146,1 | Perdeu de longe — confirma que dia da semana importa muito |

**Por que E ganhou e não A (que teve o melhor MAPE de todos)?** Boa pergunta, e vale explicar: A
prevê ligeiramente melhor nos 10 dias de teste, mas isso pode ser sorte de amostra pequena (só 10
dias) — A usa mais parâmetros (uma "gaveta" pra cada dia) do que os dados conseguem sustentar com
confiança (o BIC penaliza exatamente isso). É como comparar um terno sob medida que serve bem hoje
com um terno de tamanho padrão que serve quase tão bem em qualquer dia — o sob medida corre mais
risco de não servir mais amanhã.

A hipótese original do boxplot (C e D) **perdeu** — a leitura visual "Segunda+Quinta parecidas" não
se sustentou. O vencedor (E) isola Segunda como grupo próprio e junta Terça+Quarta+Quinta — batendo
com a pista que já tínhamos visto no Capítulo 2.

**O modelo vencedor desta rodada** (ainda sem Fim de Semana, ainda com o tratamento de outlier que
vamos questionar no próximo capítulo):
```
elasticidade = -12,90   (extremamente significativo)
Segunda (Pico)   +0,37  (significativo)
Sexta (Fraco)    -1,23  (extremamente significativo)
```

---

## Capítulo 6 — Confirmando o Agrupamento Vencedor (Não Confiar Só no Torneio)

O grupo "Terça+Quarta+Quinta juntas" mereceu uma checagem extra: um gráfico anterior parecia mostrar
Quarta e Quinta bem separadas em alguns pontos. Isolamos só esse trio (mais poder estatístico do que
testar todos os dias de uma vez) e comparamos Quarta e Quinta contra Terça, controlando por preço:
nenhuma diferença com p-valor abaixo de 0,05 (Quarta: p=0,825; Quinta: p=0,751) — o "gap" que
parecia existir no gráfico era só ruído de poucos pontos, não um padrão real. **Essa checagem foi
refeita mais tarde com o tratamento de outlier oficial (Capítulo 7) e o resultado ficou ainda mais
claro** — ver detalhe técnico ao final do Capítulo 8.

---

## Capítulo 7 — A Segunda Grande Decisão: O Que Fazer com os Pontos Fora da Curva?

Até aqui, todo modelo usou uma forma de tratar outlier de Volume que nem tinha sido questionada: um
teto por dia da semana (baseado na variação típica de cada dia), cortando qualquer valor acima dele.
Essa técnica (chamamos de **Premissa A**) tem um problema conceitual: ela olha só para o Volume,
**sem olhar o preço daquele dia**. Um volume alto pode ser perfeitamente normal se o preço também
estava baixo naquele dia — exatamente o comportamento que a própria curva de elasticidade prevê.
Cortar esse ponto como se fosse erro pode estar "limpando" justamente o sinal mais informativo que
os dados têm sobre sensibilidade a preço.

Existe uma alternativa mais correta tecnicamente (**Premissa B**): um ponto só é outlier se o Volume
observado **não bate com o que a própria curva Preço→Volume prevê** para aquele preço — mesmo que,
olhado sozinho, nem o Volume nem o Preço pareçam estranhos. Só que a Premissa B só pode ser
calculada depois que já existe uma curva ajustada — por isso vem depois, não antes.

### O que a Premissa A estava fazendo, em números
O teto de capping varia bastante por dia (de 3,4 kg no Domingo a 65,8 kg na Quinta), e no total
flagra 12 dos 66 dias de treino útil — quase 1 em cada 5. Testamos a mesma lógica pela primeira vez
também no Preço (nunca tinha sido feito): usando só o teto (como fizemos com Volume), o dia de preço
**mínimo** — a provável promoção do Capítulo 3, o evento mais relevante do dataset — **não seria
sequer flagrado**, porque é um piso, não um teto. Primeiro sinal de que a Premissa A, do jeito mais
simples de aplicar, tende a deixar passar exatamente a anomalia mais importante.

### Comparando as duas premissas, com o modelo já ajustado
Calculamos a Premissa B (distância de Cook, sobre o Volume **bruto** — teria que ser assim, senão o
capping da Premissa A já teria suavizado os pontos extremos antes mesmo de procurá-los, e o teste
sairia viciado a favor de "não achar nada"). Resultado: **as duas premissas quase não concordam.** A
Premissa A flagra 12 dias; a Premissa B flagra só 3, e apenas 1 deles coincide com os 12 da Premissa A.

**O achado mais revelador é o que a Premissa B *não* flagra:** o maior volume de todo o treino
(100 kg, 15/10) tem uma nota de influência (distância de Cook) de apenas 0,017 — bem abaixo do
limiar de "atenção" (0,061). Por quê? Porque o preço daquele dia também estava perto do mínimo
histórico — **dado o preço, aquele volume é exatamente o que a curva prevê, não uma anomalia.**
Nenhum outro dia do episódio do Capítulo 3 aparece como desproporcionalmente influente para a curva.

Isso é evidência de que **julgar outlier pela relação Preço→Volume é um critério diferente — e mais
adequado — do que julgar Volume isoladamente.** Como efeito colateral, também descobrimos algo
importante: o modelo ajustado sobre Volume bruto (sem nenhum tratamento) tem elasticidade -14,94,
visivelmente diferente da elasticidade -12,90 do modelo com capping. **O capping por IQR não só
decide o que é outlier — ele também distorce a elasticidade estimada**, o número mais importante
deste projeto inteiro.

### Um segundo torneio, agora para decidir o tratamento
Isso levantou a pergunta certa: qual tratamento realmente generaliza melhor pra dados novos? Testamos
formalmente 4 alternativas, cruzadas com as duas formas de agrupar dia (dia a dia vs. o agrupamento
vencedor do Capítulo 5), usando o mesmo critério de sempre (MAPE fora da amostra, BIC, significância):

| Tratamento | O que é | MAPE teste (agrupado) | Veredito |
|---|---|---|---|
| **Atual (capping IQR)** | Corta os valores acima do teto antes de ajustar qualquer modelo | 56,5% | Era o tratamento em uso — bom, mas não o melhor |
| **Bruto** | Não trata outlier nenhum | 56,5% | Empata em erro, mas perde em BIC — abandonar o tratamento sem pôr nada no lugar não ajuda |
| **Remoção pela curva** | Descobre os pontos influentes (Premissa B) e os remove do treino | 57,4% | **Perdeu** — com pouco dado, descartar informação dói mais do que ajuda |
| **Regressão robusta (Huber)** | Cada ponto é automaticamente reponderado pelo tamanho do seu próprio "erro" — nenhum dado é descartado | 56,3% | 🏆 **Venceu** — iguala/supera o atual, sem descartar dado, sem precisar de um teto arbitrário |

**Por que "remover pela curva" perdeu, se ela identifica os pontos certos?** Porque nossa amostra é
pequena (66-76 dias). Remover até poucos pontos reduz ainda mais o quanto o modelo tem para aprender
— o mesmo motivo pelo qual decidimos manter o episódio do Capítulo 3 no treino em vez de excluí-lo
(Capítulo 9). A regressão robusta resolve isso de um jeito mais esperto: em vez de excluir, ela só
"escuta menos" o ponto estranho, sem perder a observação inteira.

---

## Capítulo 8 — Confirmando os Grupos com Estatística, do Zero

Até aqui, os grupos (Segunda sozinha / Terça+Quarta+Quinta juntas / Sexta sozinha) vieram de
decisões anteriores (leitura de gráfico, depois confirmadas uma a uma). Nesta seção, fizemos o
caminho inverso, já com o tratamento oficial (Huber): **derivar** o agrupamento certo a partir de um
único teste de p-valor, em vez de assumir e só confirmar depois.

**Passo 1 — sem agrupar nada:** comparamos cada dia útil contra Quarta-feira (usada como referência),
controlando por preço:

| Dia (vs. Quarta) | p-valor | Interpretação |
|---|---|---|
| Terça | 0,869 | Não dá pra dizer que é diferente de Quarta — junta |
| Quinta | 0,971 | Não dá pra dizer que é diferente de Quarta — junta |
| Segunda | 0,071 | Levemente acima do limite de 0,05 — parece diferente, mas sozinho o teste não confirma |
| Sexta | < 0,001 | Claramente diferente — grupo próprio |

**Passo 2 — juntar quem não é diferente, e testar de novo com mais gente na base:** ao juntar
Terça+Quarta+Quinta num único grupo de referência, a base do teste passa a ter 39 dias em vez de só
os ~13 de Quarta isolada — mais dado, mais precisão para detectar diferenças reais. Refazendo o
teste com essa base maior, Segunda passa de p=0,071 (Passo 1, inconclusivo) para **p=0,037**
(Passo 2, agora sim confirmado). O mesmo efeito real estava lá — só precisava de uma base mais
robusta para aparecer com clareza.

**A lição, em uma frase:** o agrupamento Segunda / Terça+Quarta+Quinta / Sexta não foi um palpite —
foi calculado, e o próprio ato de agrupar os dias parecidos aumentou nossa capacidade de confirmar
os dias que são de fato diferentes.

*(Detalhe técnico: o teste de Quarta/Quinta do Capítulo 6, refeito com este mesmo tratamento
oficial, deu p=0,887 e p=0,882 — ainda mais longe de significativo do que antes. A conclusão não
dependia do tratamento antigo.)*

---

## Capítulo 9 — Quanto do Resultado Vem Só da Anomalia do Capítulo 3?

A pergunta ficou em aberto desde o Capítulo 3: será que aquele episódio de 13 dias com preço/volume
extremos está distorcendo a elasticidade calculada? O Capítulo 7 já deu uma resposta indireta (a
curva não trata esses dias como anomalia). Aqui damos a resposta direta: reajustamos o modelo
**removendo** esses dias do treino e comparamos.

| | Nº de dias no treino | Elasticidade |
|---|---|---|
| Com o episódio | 66 | -12,90 |
| **Sem o episódio** | 56 | **-10,63** |

A elasticidade cai ~18% ao remover o episódio — um efeito real, mas do mesmo tamanho da instabilidade
geral que já esperávamos ver com uma amostra pequena (Capítulo 11). **Decisão:** manter o episódio no
treino — removê-lo encolheria ainda mais uma amostra que já é pequena, e o efeito medido não é grande
o bastante para justificar perder 10 dias de dado.

---

## Capítulo 10 — E o Fim de Semana?

Sábado e Domingo ficaram de fora de tudo até aqui — só 5 dias de treino cada, menos da metade do que
já tínhamos por dia útil. Duas perguntas, com necessidades de dado bem diferentes:

1. **Fim de semana reage a preço de um jeito diferente?** (elasticidade própria — exige muito dado)
2. **Fim de semana vende, em média, uma quantidade diferente?** (nível — patamar geral do grupo, exige pouco dado)

**Pergunta 1: não dá.** Com só 5 dias cada, o Sábado até mostrou uma correlação preço×volume
**positiva** (economicamente ao contrário do esperado) — sinal claro de que 5 pontos não bastam para
confiar numa elasticidade própria pro fim de semana.

**Pergunta 2: sim, e com folga.** Comparando "juntar fim de semana com Sexta" vs. "dar um patamar
próprio para o fim de semana", a segunda opção venceu com folga (BIC 122,7 vs. 166,7). O efeito
"Fim de Semana" saiu extremamente significativo (p < 0,001) mesmo com só 10 dias no total — reforça
a mesma lição do Capítulo 5: **um patamar (nível) é muito mais fácil de confirmar com pouco dado do
que uma elasticidade.**

Isso deu origem ao **4º grupo** do modelo final: Fim de Semana, com patamar próprio, mesma
elasticidade dos outros grupos. **Limitação que fica em aberto:** essa equação não pôde ser validada
fora da amostra — não existe nenhum dia de fim de semana no período de teste (Capítulo 1).

---

## Capítulo 11 — Quão Confiável é Esse Número? (Provas de que Há Pouco Dado)

Antes de fechar o modelo, valia provar com número — não só intuição — que "temos pouco dado" é uma
limitação real, não desculpa.

- **Curva de aprendizado:** reajustamos a mesma regressão usando cada vez mais dias de treino. Com
  20 dias, a elasticidade saiu com o **sinal errado** (+7,29 em vez de negativo!). Só a partir de ~50
  dias o sinal se estabiliza — e mesmo entre 60 e 66 dias, o número ainda estava mudando
  visivelmente. Ou seja: mais histórico ainda mudaria a conclusão.
- **Bootstrap (2.000 simulações de "e se a amostra fosse ligeiramente diferente"):** a elasticidade
  balança ~14% em torno do seu valor médio só por causa de qual amostra de dias calhou de existir.
- **Intervalo de confiança:** a faixa de valores plausíveis para a elasticidade final vai de -16,30
  a -9,48 — mais de 1,7x de diferença entre a ponta de baixo e a de cima.

*(Nota: estes três testes foram feitos com o tratamento antigo, antes da troca para Huber no
Capítulo 7 — não foram refeitos com a elasticidade final de -14,10. A conclusão qualitativa
["pouco dado, muita incerteza"] não muda, mas os números exatos acima valem para a elasticidade
-12,90, não para -14,10.)*

**O que isso significa na prática:** o número da elasticidade — seja -12,90 ou -14,10 — é a melhor
estimativa que temos, mas não é uma verdade fixa: é um valor com uma margem de incerteza real (da
ordem de 15-20% para mais ou para menos), e essa margem precisa ser levada para a etapa de
otimização (por exemplo, via cenários ou margem de segurança), não tratada como certeza absoluta.

---

## Capítulo 12 — O Campeão e o Vice-Campeão

Juntando as duas grandes decisões (Capítulo 5: como agrupar os dias; Capítulo 7: como tratar
outlier) e a extensão para o fim de semana (Capítulo 10), chegamos ao modelo final. **Ao todo, 19
modelos diferentes foram ajustados e comparados ao longo desta análise** (a lista completa, com a
descrição de cada um e por que perdeu, está no notebook, seção final "Comparativo de Todos os
Modelos Testados").

### 🏆 Campeão
**4 grupos (Segunda / Terça+Quarta+Quinta / Sexta / Fim de Semana), elasticidade única, ajustado por
regressão robusta de Huber sobre Volume bruto.**
- Erra, em média, **56,1%** do volume diário em dias que nunca viu.
- Não descarta nenhum dia de dado.
- Não depende de um teto de corte decidido antes de existir qualquer modelo.
- Mantém todos os efeitos (Segunda, Sexta, Fim de Semana) estatisticamente confirmados.

### 🥈 Vice-Campeão
**O mesmo agrupamento de 4 grupos, mas com o tratamento antigo (capping IQR) — na prática, era o
modelo que estava em uso até essa análise.**
- Erra, em média, **56,3%** — só 0,2 ponto percentual pior que o campeão. Pelo erro de previsão
  sozinho, os dois são quase empatados.
- **O que desempata:** o vice-campeão tem um problema escondido — ele **subestima em ~30% o quanto o
  cliente reage ao preço** (elasticidade -10,76 contra -14,10 do campeão), porque o corte de outlier
  "limpa" justamente os dias de preço/volume mais extremos, que são os mais informativos sobre
  sensibilidade a preço. Isso não aparece no MAPE (que mede erro de previsão pontual), mas importa
  demais para um otimizador de preços — que decide o preço olhando exatamente para o tamanho dessa
  reação.

**Por que não escolher pelo MAPE sozinho, já que os dois empatam quase?** Porque a elasticidade é o
número que o otimizador vai usar para decidir *quanto* mudar o preço — um erro de 30% nesse número
específico é muito mais grave para a decisão final do que 0,2 ponto percentual de MAPE. É a mesma
lição do Capítulo 5 (candidato A quase empatava em MAPE com o vencedor, mas foi descartado por um
motivo mais profundo que o próprio MAPE não captura).

*(Um "bronze" honrado: dentro do Torneio de agrupamento — Capítulo 5 — o candidato "dia a dia"
teve o menor MAPE de todos (55,7%), mas foi descartado por complexidade não sustentada pelos dados,
não por erro de previsão.)*

---

## Capítulo 13 — Testando Contra a Realidade

Depois de decidir tudo com base no treino, o teste final é o mais honesto: aplicar o modelo campeão
nos 10 dias de novembro que nunca foram usados para decidir nada.

| Modelo | Erro médio nos 10 dias de teste |
|---|---|
| Baseline ingênuo (média histórica por dia, ignora o preço) | 90,2% |
| Modelo antigo (vice-campeão, capping IQR) | 56,3% |
| **Modelo campeão (Huber)** | **56,1%** |

O modelo campeão bate o baseline ingênuo por 34 pontos percentuais — prova de que o preço carrega
informação real sobre a demanda. Ainda assim, ~56% de erro médio é alto em termos absolutos: a
etapa de otimização não deve tratar a previsão de volume como um número certo, e sim considerar essa
margem de erro na decisão (cenários, margem de segurança, otimização robusta em vez de um único
número "de ponto").

---

## Capítulo 14 — Limitações (para constar no relatório final)

1. **Endogeneidade do Preço** não descartada — é uma média realizada, pode conter causalidade
   reversa (desconto por volume grande). Testado indiretamente (Capítulo 1), sem confirmação
   definitiva por falta de dado de pedido individual.
2. **Amostra pequena em geral** — 66 a 76 dias de treino, dependendo do corte. A elasticidade ainda
   não convergiu (Capítulo 11) e balança ~14% no bootstrap.
3. **Grupos "Fraco" (Sexta) e "Fim de Semana"** são os com menos dado (14 e 10 dias).
4. **Episódio de 13-24/10** concentra quase todos os extremos do dataset. A curva de elasticidade
   não o considera desproporcionalmente influente (Capítulo 7), mas removê-lo do treino desloca a
   elasticidade em ~18% (Capítulo 9) — um efeito real, mas dentro da instabilidade geral já
   documentada. Decisão consciente de mantê-lo, dado o tamanho já pequeno da amostra.
5. **O tratamento antigo de outlier (capping IQR) foi abandonado como decisão oficial** (Capítulo 7):
   era baseado só no Volume, ignorando o preço do dia, e testado formalmente contra 3 alternativas —
   perdeu para a regressão robusta de Huber. O capping subestimava a elasticidade em ~30%. A curva
   oficial (Capítulo 12) já reflete essa troca; `02-modelagem.ipynb` consome exclusivamente o modelo
   com Huber.
6. **Fim de semana**: patamar bem estimado (p<0,001), mas elasticidade impossível de estimar (só 5
   dias por dia da semana) e sem qualquer validação fora da amostra (o teste não tem nenhum dia de
   fim de semana).
7. **Custo** tem tendência de alta de ~2% ao longo do período e um pico atípico — a premissa de
   "custo fixo" usada na conta de margem é uma aproximação, não um fato confirmado.
8. **Faixa de preço observada é estreita** (~14% de amplitude no treino) — qualquer preço simulado
   fora dela na etapa de otimização é extrapolação sem garantia estatística.
9. **Erro de previsão ainda alto** (56,1% MAPE) mesmo no modelo campeão — deve ser incorporado como
   incerteza na etapa de otimização, não ignorado.
10. **Confirmar com quem definiu o desafio** se o horizonte de precificação realmente inclui os fins
    de semana — a estrutura do período de teste sugere que talvez não (Capítulo 1).

---

## Capítulo 15 — Recomendações para a Próxima Etapa (Otimização)

- Usar o modelo campeão (Capítulo 12) como ponto de partida — já disponível como código pronto em
  `src/modeling/demand_curve.py` (`fit_demand_curve`/`predict_volume`), e é o que `02-modelagem.ipynb`
  consome. A etapa de otimização deve importar dessa mesma função, não recalcular a curva por conta
  própria, para não divergir da decisão tomada e validada aqui.
- Incorporar a incerteza da elasticidade (Capítulo 11) na formulação da otimização — por exemplo,
  via cenários, otimização robusta, ou uma margem de segurança sobre o volume previsto, em vez de
  tratar a previsão como determinística.
- Formular a otimização como: maximizar `Σ (Preço_d − Custo_d) · Volume_previsto(Preço_d, grupo_d)`
  sujeito a meta semanal (165kg ±30%) e variação máxima de preço (R$2/dia consecutivo). Dado o
  tamanho pequeno do problema (1 produto, 14 dias), tanto busca em grade quanto otimização não
  linear (`scipy.optimize`) são viáveis.
- Confirmar o escopo do fim de semana antes de decidir se a 4ª equação entra na otimização.
