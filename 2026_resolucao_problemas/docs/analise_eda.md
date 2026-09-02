# Análise Detalhada do EDA — Otimização de Precificação (Produto_A, Minerva Foods)

**Notebook analisado:** `01-EDA_v3.ipynb` (88 células — 57 de código, 31 de markdown)
**Período de dados:** 01/08/2025 a 14/11/2025 · **Produto:** Produto_A (1 SKU)
**Split:** Treino ≤ 31/10/2025 · Teste = 03/11 a 14/11/2025 (10 dias úteis, sem split leakage)

---

## 1. Resumo Executivo

O EDA parte de uma base de 86 registros diários (Volume, Receita, Custo) e chega a um modelo de
demanda do tipo `Volume = A · Preço⁻ᴮ`, com **elasticidade única (B = 10,76) para todos os dias**
e **4 patamares de mercado (A)** diferentes: Segunda (Pico), Terça/Quarta/Quinta (Regular), Sexta
(Fraco) e Sábado/Domingo (Fim de Semana).

O caminho até aqui não foi direto: a primeira hipótese (3 clusters com elasticidades diferentes,
definida "no olho" a partir de um boxplot) foi testada formalmente contra 5 alternativas e **perdeu**
— generalizava pior fora da amostra. O modelo final é mais simples que o original, e cada escolha
foi justificada com um critério objetivo (MAPE fora da amostra, BIC, significância estatística),
não com interpretação visual.

**Validação final:** o modelo vencedor erra, em média, 56,3% do volume diário fora da amostra —
bem melhor que um baseline ingênuo (90,2%), mas longe de perfeito. Essa margem de erro deve ser
levada para a etapa de otimização (não tratar a previsão como certeza).

**Testes de robustez adicionais** (seção 9), feitos em resposta a questionamentos externos ao
notebook, confirmam duas coisas: (1) o agrupamento Terça+Quarta+Quinta se sustenta estatisticamente
mesmo isolando só o trio (p = 0,83 e p = 0,75) — o gap visto em curvas ajustadas dia a dia vem do
episódio de 13-24/10, não de uma diferença real entre os dias; (2) esse mesmo episódio infla a
elasticidade final em ~18%, uma influência real mas dentro da faixa de instabilidade já esperada.

---

## 2. Estrutura dos Dados

| Item | Detalhe |
|---|---|
| Granularidade | Diária, 1 produto (Produto_A) |
| Colunas originais | Produto, Data, Volume Realizado (kg), Receita Realizada (R$), Custo Realizado (R$) |
| Variáveis derivadas | Preço = Receita/Volume · Custo (R$/kg) = Custo/Volume · Dia da Semana |
| Treino | 76 registros (01/08 a 31/10/2025) |
| Teste | 10 registros, **todos dias úteis** (03/11 a 14/11/2025) |
| Metas (planilha à parte) | 165 kg/semana, tolerância ±30%, variação máx. de preço R$2/dia entre dias consecutivos |

**Achado estrutural importante:** de 26 finais de semana possíveis no período de treino, **16 não
têm nenhum registro** (nem venda zero) — a operação de fim de semana parece esporádica, não uma
rotina planejada. E, mais revelador ainda: **nenhum dos 6 sábados/domingos do período de teste
aparece na planilha.** Isso sugere fortemente que o horizonte real de precificação do desafio pode
ser só os 10 dias úteis — vale confirmar isso com quem definiu o desafio antes de assumir que o
Fim de Semana precisa mesmo de preço próprio.

---

## 3. Preparação e Cuidados Metodológicos

### 3.1 Split treino/teste sem vazamento de dados
O corte (31/10/2025) acontece logo após criar `Preço`/`Dia da Semana` (cálculos linha a linha, sem
risco) e **antes** de qualquer estatística agregada, boxplot, capping de outlier ou regressão —
exatamente a ordem certa para evitar que decisões de modelagem "espiem" o futuro.

### 3.2 Cuidado com a variável `Preço` (endogeneidade)
`Preço = Receita/Volume` é o preço médio **realizado**, não necessariamente o preço de tabela
definido a priori. Em relações B2B, desconto por volume poderia inflar artificialmente a
correlação preço↔volume (causalidade reversa). **Teste feito:** correlação Preço×Volume calculada
**dentro** de cada dia da semana (não misturando dias diferentes):

| Dia | Correlação Preço × Volume |
|---|---|
| Segunda | -0,77 |
| Terça | -0,74 |
| Quarta | -0,64 |
| Quinta | -0,83 |
| Sexta | -0,66 |

Todas fortes e negativas — evidência de sensibilidade real ao preço, não apenas um efeito de nível
entre dias diferentes. **Isso reduz, mas não elimina**, a preocupação com endogeneidade (não há
dados de pedido individual para confirmar definitivamente). Fica registrado como limitação.

### 3.3 Visão cronológica e estabilidade do custo
Olhar os dados em ordem cronológica (não só agrupados) revelou dois pontos que os gráficos
agrupados escondiam:
- **Custo por kg não é perfeitamente estável**: sobe gradualmente de ~R$985 (agosto) para
  ~R$1.000-1.010 (final de outubro), ~2% de tendência de alta, além de um pico isolado de R$1.030.
- Esse mesmo período (meados de outubro) concentra uma anomalia muito maior — ver seção 5.

---

## 4. Testes de Sazonalidade e Padrão Semanal

Testados com regressão controlando por `ln(Preço)` e dia da semana: **semana do mês, quinzena e mês
não são estatisticamente significativos** (p > 0,05 em todos os testes) — descartados corretamente,
evitando complexidade desnecessária.

**Achado que passou despercebido na hora, mas foi decisivo depois:** no teste de dia-a-dia (dummies
individuais, controlando por preço), a Quinta-feira **não** saiu significativamente diferente da
Quarta-feira (p = 0,768), nem a Terça (p = 0,849) — só a Sexta (p < 0,001) e, de forma limítrofe, a
Segunda (p = 0,074). Esse resultado já continha a pista de que "Segunda+Quinta" como um único grupo
("Pico") era uma hipótese frágil — só foi resgatado depois, no Torneio de Modelos (seção 6).

---

## 5. Investigação de Anomalia: o Episódio de 13–24/10

A linha do tempo cronológica revelou uma janela de ~2 semanas que concentra **praticamente todos os
valores extremos do dataset inteiro**:

| Extremo | Valor | Data |
|---|---|---|
| Maior volume de todo o treino | 100,0 kg | 15/10/2025 |
| Menor preço de todo o treino | R$ 1.188,86 | 11/10/2025 |
| Maior preço de todo o treino | R$ 1.365,49 | 24/10/2025 |
| Maior custo/kg de todo o treino | R$ 1.030,34 | 20/10/2025 |

Padrão observado: 13–16/10 (preços nos mínimos históricos, volumes nos máximos — provável
promoção) seguido de 17–24/10 (preços disparando até o máximo histórico, volumes caindo a quase
zero — provável correção). Isso é um **ponto de alavancagem**: um episódio pontual de negócio
(não um padrão repetível de comportamento do cliente) que pode estar distorcendo a elasticidade
estimada. Documentado como limitação; **não foi removido do treino** (decisão consciente de manter
todos os dados disponíveis dado o tamanho já pequeno da amostra), mas deve ser considerado se a
elasticidade final parecer implausível. **Quantificado depois na seção 9.2**: removê-lo do treino
reduz a elasticidade em ~18%.

---

## 6. Torneio de Modelos: a Decisão Mais Importante do Notebook

### 6.1 O problema
A primeira versão do modelo definia 3 clusters (Pico = Segunda+Quinta, Regular = Terça+Quarta,
Fraco = Sexta) a partir da leitura visual de um boxplot de volume médio bruto — **sem controlar por
preço**. Uma revisão posterior (conversa com colega) levantou a hipótese alternativa de que
Quinta se pareceria mais com Terça/Quarta do que com Segunda.

### 6.2 O critério
Definido **antes** de rodar qualquer coisa: (1) MAPE fora da amostra — o mais importante; (2) BIC —
penaliza complexidade desnecessária, apropriado com poucos dados; (3) quantos parâmetros realmente
se sustentam estatisticamente (p < 0,05). R² não foi usado como critério de decisão (sobe quase
sempre com mais variáveis, mesmo sem generalizar melhor).

### 6.3 Os 6 candidatos testados

| Modelo | R² | AIC | BIC | MAPE teste | Nº parâm. |
|---|---|---|---|---|---|
| A: Dia a dia (aditivo, sem interação) | 0,741 | 77,4 | 90,5 | 55,7% | 6 |
| B: Dia a dia (com interação, 1 elasticidade/dia) | 0,784 | 73,3 | 95,2 | 57,7% | 10 |
| C: Cluster oficial (sem interação) | 0,722 | 78,1 | 86,9 | 56,4% | 4 |
| **D: Cluster oficial (com interação) — modelo original** | 0,751 | 74,9 | 88,1 | **60,3%** | 6 |
| **E: Cluster do Marcelo (sem interação) — VENCEDOR** | 0,741 | **73,5** | **82,3** | 56,5% | 4 |
| F: Só preço, sem diferenciar dia | 0,226 | 141,7 | 146,1 | 125,1% | 2 |

### 6.4 Leitura dos resultados
- **F** confirma que dia da semana importa muito (erro de 125% sem ele).
- **B** é o exemplo clássico de overfitting: maior R² (0,784), mas pior BIC e poucos parâmetros
  significativos — complexidade que não se sustenta com o tanto de dado disponível.
- **D (o modelo original)** tem o **pior MAPE fora da amostra entre os candidatos sérios** —
  adicionar a interação preço×cluster piorou a generalização, apesar de parecer mais sofisticado.
- **E venceu ou empatou em quase todos os critérios**: melhor BIC, 2º melhor MAPE, maior proporção
  de parâmetros significativos (3 de 4). O agrupamento Terça+Quarta+Quinta que sustenta o modelo E
  foi questionado depois e reconfirmado com um teste focado só no trio — ver seção 9.1.

### 6.5 O modelo vencedor (na época, 3 grupos + fim de semana ainda fora)
```
const       95,29   (p < 0,001)
ln_Preço   -12,90   (p < 0,001)  — elasticidade única para todos os dias
Fraco (Sexta) -1,23 (p < 0,001)
Pico (Segunda) +0,37 (p = 0,007)
```
R² = 0,741 · N = 66 (dias úteis de treino)

---

## 7. Prova Estatística de que Há Poucos Dados

Três testes independentes, feitos especificamente para não deixar essa afirmação como opinião:

### 7.1 Curva de aprendizado
Reajustando a mesma regressão com quantidades crescentes de dias de treino:

| Nº de dias | Elasticidade | IC 95% |
|---|---|---|
| 20 | **+7,29** (sinal errado!) | [-19,77, 34,36] |
| 30 | -4,97 | [-13,69, 3,76] |
| 40 | -7,14 | [-13,49, -0,80] |
| 50 | -10,74 | [-15,91, -5,56] |
| 60 | -13,64 | [-17,68, -9,60] |
| 66 (tudo) | -12,89 | [-16,30, -9,48] |

A estimativa ainda estava mudando visivelmente entre 60 e 66 dias — sinal de que mais histórico
mudaria a conclusão de novo.

### 7.2 Bootstrap (2.000 reamostragens)
Simulando "e se tivéssemos coletado uma amostra ligeiramente diferente de dias":

| Coeficiente | Coef. de variação |
|---|---|
| Elasticidade (modelo vencedor, sem interação) | 13,7% |
| Efeito Pico (Segunda) | 24,0% |
| Efeito Fraco (Sexta) | 11,4% |
| Nível "Pico" no modelo **com** interação (D, o original) | **41%** — IC 90% de [27,6, 123,6] para um valor nominal de 73,2 |

O modelo com interação (o original) é visivelmente mais instável que o modelo vencedor — reforça,
com número, por que ele generaliza pior.

### 7.3 Largura do intervalo de confiança
IC de 95% da elasticidade final: [-16,30, -9,48] — mais de 1,7x de diferença entre a ponta de baixo
e a de cima.

**Conclusão:** as três evidências contam a mesma história de ângulos diferentes. Isso não invalida
o modelo, mas define quanto de confiança depositar nele daqui pra frente (não tratar como número
definitivo).

---

## 8. Fim de Semana: Nível Próprio, Elasticidade Impossível de Estimar

### 8.1 A pergunta certa dividida em duas
1. Fim de semana reage a preço diferente? (elasticidade própria — exige muito dado)
2. Fim de semana vende, em média, quantidade diferente? (nível próprio — exige pouco dado)

### 8.2 Pergunta 1: não dá
Correlação Preço×Volume dentro do próprio dia (N=5 cada):

| Dia | N | Correlação |
|---|---|---|
| Sábado | 5 | **+0,86** (sinal economicamente invertido) |
| Domingo | 5 | -0,45 (fraca, não confiável com N=5) |

### 8.3 Pergunta 2: sim, e com folga
Comparando "juntar com Sexta" vs "nível próprio" (76 dias de treino, incluindo fim de semana):

| Abordagem | R² | AIC | BIC |
|---|---|---|---|
| Fim de semana junto com Sexta | 0,691 | 157,4 | 166,7 |
| **Fim de semana com nível próprio** | **0,836** | **111,0** | **122,7** |

O coeficiente `FimDeSemana` sai com **p < 0,001** (t = -16,4) — extremamente significativo, mesmo
com só 10 observações no total. Reforça o mesmo princípio do Torneio: **níveis são muito mais
fáceis de estimar com pouco dado do que elasticidades.**

### 8.4 Modelo final com 4 grupos (76 dias de treino)
```
const         79,97   (p < 0,001)
ln_Preço     -10,76   (p < 0,001)  — elasticidade única, atualizada
Fraco (Sexta) -1,23   (p < 0,001)  — praticamente igual ao modelo de 3 grupos
Pico (Segunda) +0,36  (p = 0,022)  — praticamente igual ao modelo de 3 grupos
FimDeSemana   -2,83   (p < 0,001)  — novo
```
R² = 0,836 · N = 76 (todos os dias de treino)

A elasticidade mudou de -12,90 para -10,76 ao incluir o fim de semana no ajuste — variação dentro
da faixa de instabilidade já demonstrada na seção 7, não motivo de alarme.

**Checagem de segurança:** validado que incluir o fim de semana no ajuste **não piora** a
performance nos dias úteis (MAPE = 56,3%, praticamente igual ao 56,5% anterior).

**Limitação que fica em aberto:** a equação do Fim de Semana **não pôde ser validada fora da
amostra** — não existe nenhum dia de fim de semana no período de teste (ver seção 2).

---

## 9. Testes de Robustez Adicionais

Duas perguntas de acompanhamento levantadas numa revisão externa do modelo vencedor (conversa com
colega), testadas formalmente e incorporadas ao notebook.

### 9.1 O trio Terça/Quarta/Quinta é mesmo parecido?

As curvas ajustadas **dia a dia** (uma regressão isolada por dia, só 13 pontos cada) mostravam
Quarta e Quinta bem separadas logo no início da faixa de preço (ex.: em R$1.220, uma leitura das
curvas dava ~35 kg para Quarta e ~55 kg para Quinta). Antes de aceitar isso como um padrão real,
foi feito um teste formal controlando por preço, usando **só o trio** (mais poder estatístico do
que testar todos os dias de uma vez):

```
is_Quarta (vs. Terça, controlando por preço): p = 0,825
is_Quinta (vs. Terça, controlando por preço): p = 0,751
```

Nenhuma diferença estatisticamente sustentável. Uma segunda checagem — os resíduos do modelo final
já treinado, separados por dia — reforça a mesma conclusão:

| Dia | Erro médio | Desvio-padrão |
|---|---|---|
| Terça | -0,035 | 0,329 |
| Quarta | +0,009 | 0,435 |
| Quinta | +0,026 | 0,562 |

As diferenças médias entre os dias (0,01 a 0,03) são pequenas frente ao desvio-padrão de cada um
(0,33 a 0,56) — a variação **dentro** de cada dia é bem maior que a diferença **entre** eles.
Conferindo os dados brutos, os pontos mais próximos da faixa de preço onde o gap aparecia nas
curvas individuais são justamente **15/10 (Quarta) e 16/10 (Quinta)** — dois dias consecutivos do
episódio de 13–24/10 (seção 5), não uma diferença estrutural entre os dias da semana. O gap visto
nas curvas individuais reflete a instabilidade de ajustar 13 pontos sozinhos (o mesmo problema do
Modelo B no Torneio, seção 6), não um padrão real.

### 9.2 Quanto da elasticidade vem do episódio de 13–24/10?

Reajustando o modelo (3 grupos, dias úteis) **removendo** os 12 dias do episódio do treino:

| | N (treino) | Elasticidade | Pico | Fraco | R² |
|---|---|---|---|---|---|
| Com o episódio | 66 | -12,90 | 0,37 | -1,23 | 0,741 |
| **Sem o episódio** | 56 | **-10,62** | 0,37 | -1,20 | 0,699 |

Removendo o episódio, a elasticidade cai ~18% em magnitude (-12,90 → -10,62) — confirma que ele
realmente infla um pouco a estimativa. Mas os efeitos de Pico e Fraco praticamente não mudam, e a
variação observada está **dentro da mesma faixa de instabilidade** já demonstrada na seção 7 (o
bootstrap já mostrava coeficiente de variação de ~14%). Ou seja: o episódio contribui para a
incerteza geral, mas não é a única fonte dela — o problema de fundo continua sendo o tamanho da
amostra.

**Decisão tomada:** manter o episódio no treino (removê-lo reduziria ainda mais uma amostra já
pequena, de 66 para 56 observações), registrando este teste como evidência documentada de quanto
essa escolha específica pesa no resultado final.

---

## 10. Modelo Final: as 4 Equações de Demanda

$$Volume = A \cdot \text{Preço}^{-10{,}76}$$

| Grupo | Dias | A (nível) | Equação |
|---|---|---|---|
| Regular | Terça, Quarta, Quinta | e^79,97 | Volume = e^79,97 · Preço⁻¹⁰·⁷⁶ |
| Pico | Segunda | e^80,34 | Volume = e^80,34 · Preço⁻¹⁰·⁷⁶ |
| Fraco | Sexta | e^78,74 | Volume = e^78,74 · Preço⁻¹⁰·⁷⁶ |
| Fim de Semana | Sábado, Domingo | e^77,14 | Volume = e^77,14 · Preço⁻¹⁰·⁷⁶ ⚠️ não validado |

**Faixa de preço observada por grupo (fora dela = extrapolação):**

| Grupo | Mín. | Máx. | N (treino) |
|---|---|---|---|
| Fim de Semana | R$ 1.188,86 | R$ 1.354,19 | 10 |
| Fraco | R$ 1.208,37 | R$ 1.365,49 | 14 |
| Pico | R$ 1.220,47 | R$ 1.352,42 | 13 |
| Regular | R$ 1.201,63 | R$ 1.344,63 | 39 |

---

## 11. Validação Final Fora da Amostra

| Modelo | MAPE (10 dias de teste) |
|---|---|
| Baseline ingênuo (média histórica por dia, sem olhar preço) | 90,2% |
| **Modelo vencedor (4 grupos, elasticidade única)** | **56,3%** |

O modelo bate o baseline com folga (quase 34 pontos percentuais de melhora), confirmando que o
preço carrega informação real sobre a demanda. Ainda assim, 56,3% de erro médio é um número alto
em termos absolutos — a etapa de otimização não deve tratar a previsão de volume como um valor
certo, e sim considerar essa margem de erro na decisão (ex: margem de segurança, cenários, ou
otimização robusta em vez de point forecast).

---

## 12. Síntese das Limitações (para constar no relatório final)

1. **Endogeneidade do Preço** não descartada — é média realizada, pode conter causalidade reversa
   (desconto por volume em pedidos grandes). Testado indiretamente (correlação dentro do dia), mas
   sem confirmação definitiva por falta de dados de pedido individual.
2. **Amostra pequena em geral** — 66 a 76 observações de treino, dependendo do corte. Elasticidade
   ainda não convergiu (curva de aprendizado) e tem coeficiente de variação de ~14% no bootstrap.
3. **Cluster "Fraco" (Sexta) e "Fim de Semana"** são os grupos com menos dado (14 e 10 observações).
4. **Episódio de 13-24/10** concentra quase todos os extremos do dataset. Testado formalmente
   (seção 9.2): removê-lo do treino reduz a elasticidade em ~18% (-12,90 → -10,62), confirmando que
   ele infla a estimativa, mas dentro da mesma faixa de instabilidade já esperada — decisão consciente
   de mantê-lo, dado o tamanho já pequeno da amostra.
5. **Fim de semana**: nível bem estimado (p<0,001), mas elasticidade impossível de estimar (N=5) e
   sem qualquer validação fora da amostra (teste não tem nenhum dia de fim de semana).
6. **Custo** tem tendência de alta de ~2% ao longo do período e um pico atípico — a premissa de
   "custo fixo" usada na conta de margem é uma aproximação, não um fato confirmado.
7. **Faixa de preço observada é estreita** (~14% de amplitude no treino) — qualquer preço simulado
   fora dela na etapa de otimização é extrapolação sem garantia estatística.
8. **Erro de previsão ainda alto** (56,3% MAPE) mesmo no modelo vencedor — deve ser incorporado
   como incerteza na etapa de otimização, não ignorado.
9. **Confirmar com quem definiu o desafio** se o horizonte de precificação realmente inclui os
   fins de semana — a estrutura do período de teste sugere que talvez não.

---

## 13. Recomendações para a Próxima Etapa (Modelagem/Otimização)

- Usar o modelo de 4 grupos com elasticidade única (seção 10) como ponto de partida.
- Antes de otimizar, testar a sensibilidade do resultado removendo o período de 13-24/10 do
  treino, para checar se a elasticidade e as decisões de preço mudam materialmente.
- Incorporar a incerteza da elasticidade (IC largo, bootstrap) na formulação da otimização — por
  exemplo, via cenários, otimização robusta, ou uma margem de segurança sobre o volume previsto,
  em vez de tratar a previsão como determinística.
- Formular a otimização como: maximizar `Σ (Preço_d − Custo_d) · Volume_previsto(Preço_d, grupo_d)`
  sujeito a meta semanal (165kg ±30%) e variação máxima de preço (R$2/dia consecutivo). Dado o
  tamanho pequeno do problema (1 produto, 14 dias), tanto busca em grade quanto otimização não
  linear (`scipy.optimize`) são viáveis.
- Confirmar o escopo do fim de semana antes de decidir se a 4ª equação entra na otimização.
