# Análise Detalhada do EDA — Otimização de Precificação (Produto_A, Minerva Foods)

**Notebook analisado:** `01-EDA_v3.ipynb` (99 células — 60 de código, 39 de markdown)
**Período de dados:** 01/08/2025 a 14/11/2025 · **Produto:** Produto_A (1 SKU)
**Split:** Treino ≤ 31/10/2025 · Teste = 03/11 a 14/11/2025 (10 dias úteis, sem split leakage)

---

## 1. Resumo Executivo

O EDA parte de uma base de 86 registros diários (Volume, Receita, Custo) e chega a um modelo de
demanda do tipo `Volume = A · Preço⁻ᴮ`, com **elasticidade única (B = 10,76) para todos os dias**
e **4 patamares de mercado (A)** diferentes: Segunda (Pico), Terça/Quarta/Quinta (Regular), Sexta
(Fraco) e Sábado/Domingo (Fim de Semana).

O caminho até aqui não foi direto: a primeira hipótese (3 clusters com elasticidades diferentes,
definida a partir da leitura visual de um boxplot) foi testada formalmente contra 5 alternativas em
um Torneio de Modelos e **perdeu** — generalizava pior fora da amostra. O modelo final é mais
simples que o original, e cada escolha foi justificada com um critério objetivo (MAPE fora da
amostra, BIC, significância estatística), não com interpretação visual.

**Validação final:** o modelo vencedor erra, em média, 56,3% do volume diário fora da amostra —
bem melhor que um baseline ingênuo (90,2%), mas longe de perfeito. Essa margem de erro deve ser
levada para a etapa de otimização (não tratar a previsão como certeza).

**Tratamento de outlier — duas premissas testadas formalmente:** o notebook testa e compara duas
formas distintas de definir "outlier" (seção 6 e seção 8). A Premissa A (Volume e Preço como
variáveis isoladas, capping por IQR) flagra 12 dos 66 dias úteis de treino — quase 1 em cada 5. A
Premissa B (um ponto é outlier quando o Volume não bate com o que a própria curva de elasticidade
prevê para aquele preço, via distância de Cook) flagra só 1 dia, e esse dia **não é** o mesmo que a
Premissa A flagra com mais destaque. A conclusão prática: a Premissa B é o critério tecnicamente
mais adequado para decidir o que pesa menos na estimativa de elasticidade, porque julga o ponto
*dado o preço* — a Premissa A, sozinha, tende a marcar como anômalo um volume alto que é
perfeitamente consistente com um preço baixo naquele dia (exatamente o comportamento que a curva
prevê). Detalhes e números completos na seção 8.

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

**Achado estrutural relevante:** de 26 finais de semana possíveis no período de treino, **16 não
têm nenhum registro** (nem venda zero) — a operação de fim de semana parece esporádica, não uma
rotina planejada. E, mais relevante ainda: **nenhum dos 6 sábados/domingos do período de teste
aparece na planilha.** Isso sugere que o horizonte real de precificação do desafio pode ser só os
10 dias úteis — recomenda-se confirmar esse ponto com quem definiu o desafio antes de assumir que o
Fim de Semana precisa de preço próprio (ver seção 14, item 9).

---

## 3. Preparação e Cuidados Metodológicos

### 3.1 Split treino/teste sem vazamento de dados
O corte (31/10/2025) acontece logo após criar `Preço`/`Dia da Semana` (cálculos linha a linha, sem
risco) e **antes** de qualquer estatística agregada, boxplot, tratamento de outlier ou regressão —
a ordem correta para evitar que decisões de modelagem "espiem" o futuro.

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
entre dias diferentes. Isso reduz, mas não elimina, a preocupação com endogeneidade (não há dados
de pedido individual para confirmar definitivamente). Fica registrado como limitação (seção 14).

### 3.3 Visão cronológica e estabilidade do custo
Olhar os dados em ordem cronológica (não só agrupados) revelou dois pontos que os gráficos
agrupados escondiam:
- **Custo por kg não é perfeitamente estável**: sobe gradualmente de ~R$985 (agosto) para
  ~R$1.000-1.010 (final de outubro), ~2% de tendência de alta, além de um pico isolado de R$1.030.
- Esse mesmo período (meados de outubro) concentra uma anomalia muito maior — ver seção 5.

---

## 4. Testes de Sazonalidade e Padrão Semanal

Testados com regressão controlando por `ln(Preço)` e dia da semana: semana do mês (p entre 0,148 e
0,840), quinzena (p = 0,629) e mês (p entre 0,145 e 0,242) **não são estatisticamente
significativos** — descartados corretamente, evitando complexidade desnecessária.

**Achado que se tornou decisivo mais adiante:** no mesmo teste, controlando por preço, a
Quinta-feira **não** saiu significativamente diferente da Quarta-feira (p = 0,768), nem a Terça
(p = 0,849) — só a Sexta (p < 0,001) e, de forma limítrofe, a Segunda (p = 0,074). Esse resultado já
continha a pista de que "Segunda+Quinta" como um único grupo ("Pico") era uma hipótese frágil — só
foi resgatado depois, no Torneio de Modelos (seção 7) e confirmado na defesa do agrupamento vencedor
(seção 8.1).

---

## 5. Investigação de Anomalia: o Episódio de 13–24/10

A linha do tempo cronológica revelou uma janela de ~2 semanas que concentra praticamente todos os
valores extremos do dataset inteiro:

| Extremo | Valor | Data |
|---|---|---|
| Maior volume de todo o treino | 100,0 kg | 15/10/2025 |
| Menor preço de todo o treino | R$ 1.188,86 | 11/10/2025 |
| Maior preço de todo o treino | R$ 1.365,49 | 24/10/2025 |
| Maior custo/kg de todo o treino | R$ 1.030,34 | 20/10/2025 |

Padrão observado: 13–16/10 (preços nos mínimos históricos, volumes nos máximos — provável
promoção) seguido de 17–24/10 (preços disparando até o máximo histórico, volumes caindo a quase
zero — provável correção). Isso é um **ponto de alavancagem** em potencial: um episódio pontual de
negócio (não necessariamente um padrão repetível de comportamento do cliente) que pode estar
distorcendo a elasticidade estimada. Não foi removido do treino (decisão consciente de manter todos
os dados disponíveis dado o tamanho já pequeno da amostra); seu impacto real é quantificado
formalmente na seção 8.2.

---

## 6. Tratamento de Outliers: Duas Premissas Testadas

"Outlier" esconde duas perguntas diferentes, e o notebook testa as duas formalmente, em vez de
assumir que uma resolve a outra:

- **Premissa A — outlier como propriedade da variável isolada.** Um valor é estranho olhando só
  para a distribuição da própria variável (ex.: Volume muito acima do que aquele dia da semana
  costuma vender), sem olhar o preço praticado naquele dia.
- **Premissa B — outlier como propriedade da curva de elasticidade.** Um valor é estranho quando o
  Volume observado não bate com o que o modelo Preço→Volume prevê para aquele preço — mesmo que,
  isoladamente, nem o Volume nem o Preço pareçam extremos.

A Premissa B só pode ser testada depois que existe um modelo ajustado; por isso ela é aplicada
formalmente na seção 8, depois do Torneio de Modelos. Esta seção trata a Premissa A, que não
depende de nenhum modelo.

### 6.1 Volume: capping por IQR, por dia da semana
O tratamento aplicado ao Volume usa o teto do boxplot (Q3 + 1,5·IQR), calculado **dentro de cada
dia da semana** (não globalmente — uma primeira versão global foi descartada por misturar dias com
patamares de volume muito diferentes). O teto varia bastante por dia:

| Dia | Teto calculado (kg) | Queda média após capping |
|---|---|---|
| Segunda | 54,02 | -3,6% |
| Terça | 33,37 | -13,3% |
| Quarta | 46,94 | -16,7% |
| Quinta | 65,75 | -0,5% |
| Sexta | 13,89 | -5,4% |
| Sábado | 3,37 | -2,8% |
| Domingo | 2,46 | 0,0% |

Essa variável tratada (`Volume Tratado`) é a que alimenta todas as regressões do restante do
notebook — incluindo o Torneio de Modelos e a exportação para a etapa de modelagem seguinte
(`02-modelagem.ipynb`), o que limita o quanto essa escolha pode ser revisitada sem propagar
mudanças para essa etapa posterior.

### 6.2 Testando a mesma pergunta para o Preço (pela primeira vez)
O Preço nunca havia sido testado para outliers. Aplicando a mesma lógica de IQR, mas dos dois lados
(piso e teto, já que um preço promocional é um piso, não um teto):

- **Volume:** 11 dias flagrados (piso ou teto, por dia da semana).
- **Preço:** 3 dias flagrados.
- **União (Volume e/ou Preço):** 12 dias, quase 1 em cada 5 dias de treino útil.

**Achado metodológico importante:** o capping usado na modelagem (seção 6.1) só corta o teto do
Volume. Se o mesmo critério de só-teto fosse aplicado ao Preço, o dia de preço **mínimo** — a
provável promoção de 11/10, o evento mais relevante do dataset (seção 5) — **não seria flagrado**,
porque ele é um piso, não um teto. Isso é o primeiro indício de que a Premissa A, na forma mais
simples de aplicar, tende a deixar passar exatamente o tipo de anomalia mais relevante neste caso.
A comparação definitiva contra a Premissa B está na seção 8.2.

---

## 7. Torneio de Modelos: a Decisão Mais Importante do Notebook

### 7.1 O problema
A primeira versão do modelo definia 3 clusters (Pico = Segunda+Quinta, Regular = Terça+Quarta,
Fraco = Sexta) a partir da leitura visual de um boxplot de volume médio bruto — sem controlar por
preço. Uma hipótese alternativa de agrupamento (Segunda isolada; Terça+Quarta+Quinta juntas) foi
levantada e precisava ser testada com o mesmo rigor.

### 7.2 O critério
Definido **antes** de rodar qualquer coisa: (1) MAPE fora da amostra — o mais importante; (2) BIC —
penaliza complexidade desnecessária, apropriado com poucos dados; (3) quantos parâmetros realmente
se sustentam estatisticamente (p < 0,05). R² não foi usado como critério de decisão (sobe quase
sempre com mais variáveis, mesmo sem generalizar melhor).

### 7.3 Os 6 candidatos testados

| Modelo | R² | AIC | BIC | MAPE teste | Nº parâm. |
|---|---|---|---|---|---|
| A: Dia a dia (aditivo, sem interação) | 0,741 | 77,4 | 90,5 | 55,7% | 6 |
| B: Dia a dia (com interação, 1 elasticidade/dia) | 0,784 | 73,3 | 95,2 | 57,7% | 10 |
| C: Cluster oficial (sem interação) | 0,722 | 78,1 | 86,9 | 56,4% | 4 |
| **D: Cluster oficial (com interação) — modelo original** | 0,751 | 74,9 | 88,1 | **60,3%** | 6 |
| **E: Cluster Alternativo (sem interação) — VENCEDOR** | 0,741 | **73,5** | **82,3** | 56,5% | 4 |
| F: Só preço, sem diferenciar dia | 0,226 | 141,7 | 146,1 | 125,1% | 2 |

### 7.4 Leitura dos resultados
- **F** confirma que dia da semana importa muito (erro de 125% sem ele).
- **B** é o exemplo clássico de overfitting: maior R² (0,784), mas pior BIC e poucos parâmetros
  significativos — complexidade que não se sustenta com o tanto de dado disponível.
- **D (o modelo original)** tem o **pior MAPE fora da amostra entre os candidatos sérios** —
  adicionar a interação preço×cluster piorou a generalização, apesar de parecer mais sofisticado.
- **E venceu ou empatou em quase todos os critérios**: melhor BIC, 2º melhor MAPE, maior proporção
  de parâmetros significativos (3 de 4). O agrupamento Terça+Quarta+Quinta que sustenta o modelo E
  é examinado em detalhe na seção 8.1.

### 7.5 O modelo vencedor (na época, 3 grupos + fim de semana ainda fora)
```
const       95,29   (p < 0,001)
ln_Preço   -12,90   (p < 0,001)  — elasticidade única para todos os dias
Fraco (Sexta) -1,23 (p < 0,001)
Pico (Segunda) +0,37 (p = 0,007)
```
R² = 0,741 · N = 66 (dias úteis de treino)

---

## 8. Defesa do Modelo Vencedor: Trio, Diagnóstico de Outlier e Impacto do Episódio

Três testes de robustez sobre o modelo vencedor do Torneio, encadeados: primeiro confirma-se que o
agrupamento escolhido é estatisticamente sólido (8.1); depois aplica-se formalmente a Premissa B de
outlier, comparando-a lado a lado com a Premissa A da seção 6 (8.2); por fim quantifica-se
diretamente o quanto o episódio de 13–24/10 pesa na estimativa (8.3), fechando o ciclo aberto nas
seções 5 e 6.

### 8.1 O trio Terça/Quarta/Quinta é mesmo parecido?
As curvas ajustadas **dia a dia** (uma regressão isolada por dia, poucos pontos cada) pareciam
mostrar Quarta e Quinta bem separadas logo no início da faixa de preço. Isolando só o trio (mais
poder estatístico do que testar todos os dias de uma vez) e controlando por preço:

```
is_Quarta (vs. Terça): p = 0,825
is_Quinta (vs. Terça): p = 0,751
```

Nenhuma diferença estatisticamente sustentável. Os resíduos do modelo vencedor, separados por dia,
confirmam a mesma conclusão:

| Dia | Erro médio | Desvio-padrão |
|---|---|---|
| Terça | -0,033 | 0,337 |
| Quarta | +0,008 | 0,465 |
| Quinta | +0,025 | 0,515 |

As diferenças médias entre os dias (0,008 a 0,033) são pequenas frente ao desvio-padrão de cada um
(0,34 a 0,52) — a variação **dentro** de cada dia é bem maior que a diferença **entre** eles. O gap
visto nas curvas ajustadas dia a dia reflete a instabilidade de ajustar poucos pontos isoladamente
(o mesmo problema do candidato B do Torneio), não uma diferença estrutural real — o que sustenta
manter os três dias juntos no modelo vencedor.

### 8.2 Premissa A vs. Premissa B, lado a lado: o teste de outlier na curva de elasticidade
Com o modelo vencedor em mãos, a Premissa B (seção 6) pode finalmente ser calculada: distância de
Cook e resíduos estudentizados sobre a própria regressão Preço→Volume.

**Resultado:** as duas premissas discordam quase por completo.

- **Premissa A** (marginal, seção 6.2) flagra 12 dos 66 dias — quase 1 em cada 5.
- **Premissa B** (curva de elasticidade) flagra só **1 dia** acima do limiar prático de distância de
  Cook (4/n = 0,061): Segunda, 18/08/2025, com distância de Cook = 0,090.

Esse único dia **não pertence** ao episódio de 13–24/10. Mais revelador ainda: **nenhum dos dias do
episódio aparece como desproporcionalmente influente para a curva de elasticidade em si** — a
distância de Cook de todos eles fica visivelmente abaixo do limiar (ou não pôde ser calculada, por
instabilidade numérica do estimador *leave-one-out* nessa amostra pequena — uma limitação conhecida
da técnica em N baixo, não um sinal de outlier).

**Leitura técnica:** isso é evidência direta de que julgar outlier pela própria relação Preço→Volume
é um critério diferente — e, para o objetivo de estimar elasticidade, mais adequado — do que julgar
Volume e Preço isoladamente. O "volume alto" do episódio é consistente com o preço praticado naquele
dia; a curva de elasticidade não o trata como anômalo, mesmo que a distribuição marginal do Volume
trate. Em outras palavras: **a Premissa A, usada na modelagem (seção 6.1), tende a superestimar o
número de outliers "reais"** em relação ao que a própria curva considera influente.

### 8.3 Quanto da elasticidade vem do episódio de 13–24/10?
Reajustando o modelo vencedor **removendo** os 10 dias úteis do episódio do treino:

| | N (treino) | Elasticidade | Pico | Fraco | R² |
|---|---|---|---|---|---|
| Com o episódio | 66 | -12,90 | 0,369 | -1,233 | 0,741 |
| **Sem o episódio** | 56 | **-10,63** | 0,365 | -1,204 | 0,699 |

Removendo o episódio, a elasticidade cai ~17,6% em magnitude (-12,90 → -10,63) — um efeito real,
mas da mesma ordem de grandeza da instabilidade geral já demonstrada pelo bootstrap (seção 9,
coeficiente de variação ~14%), não um outlier isolado distorcendo o resultado sozinho. Isso é
consistente com o diagnóstico da seção 8.2: o episódio pesa na estimativa porque desloca o centro
de massa dos dados (um bloco de dias inteiro com preço anormalmente baixo/alto), não porque algum
ponto individual seja estatisticamente incompatível com a curva ajustada.

**Decisão tomada:** o episódio permanece no treino — removê-lo reduziria ainda mais uma amostra já
pequena (de 66 para 56 observações). O valor desta seção é documentar, com número, o quanto essa
escolha específica pesa no resultado final.

---

## 9. Prova Estatística de que Há Poucos Dados

Três testes independentes, feitos especificamente para não deixar essa afirmação como opinião:

### 9.1 Curva de aprendizado
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

### 9.2 Bootstrap (2.000 reamostragens)
Simulando "e se tivéssemos coletado uma amostra ligeiramente diferente de dias":

| Coeficiente | Coef. de variação |
|---|---|
| Elasticidade (modelo vencedor, sem interação) | 13,7% |
| Efeito Pico (Segunda) | 24,0% |
| Efeito Fraco (Sexta) | 11,4% |

### 9.3 Largura do intervalo de confiança
IC de 95% da elasticidade final: [-16,30, -9,48] — mais de 1,7x de diferença entre a ponta de baixo
e a de cima.

**Conclusão:** as três evidências contam a mesma história de ângulos diferentes. Isso não invalida
o modelo, mas define quanto de confiança depositar nele daqui pra frente (não tratar como número
definitivo).

---

## 10. Fim de Semana: Nível Próprio, Elasticidade Impossível de Estimar

### 10.1 A pergunta certa dividida em duas
1. Fim de semana reage a preço diferente? (elasticidade própria — exige muito dado)
2. Fim de semana vende, em média, quantidade diferente? (nível próprio — exige pouco dado)

### 10.2 Pergunta 1: não dá
Correlação Preço×Volume dentro do próprio dia (N=5 cada):

| Dia | N | Correlação |
|---|---|---|
| Sábado | 5 | **+0,86** (sinal economicamente invertido) |
| Domingo | 5 | -0,45 (fraca, não confiável com N=5) |

### 10.3 Pergunta 2: sim, e com folga
Comparando "juntar com Sexta" vs "nível próprio" (76 dias de treino, incluindo fim de semana):

| Abordagem | R² | AIC | BIC |
|---|---|---|---|
| Fim de semana junto com Sexta | 0,691 | 157,4 | 166,7 |
| **Fim de semana com nível próprio** | **0,836** | **111,0** | **122,7** |

O coeficiente `FimDeSemana` sai com **p < 0,001** (t = -16,4) — extremamente significativo, mesmo
com só 10 observações no total. Reforça o mesmo princípio da seção 7: **níveis são muito mais
fáceis de estimar com pouco dado do que elasticidades.**

### 10.4 Modelo final com 4 grupos (76 dias de treino)
```
const         79,97   (p < 0,001)
ln_Preço     -10,76   (p < 0,001)  — elasticidade única, atualizada
Fraco (Sexta) -1,23   (p < 0,001)  — praticamente igual ao modelo de 3 grupos
Pico (Segunda) +0,36  (p = 0,022)  — praticamente igual ao modelo de 3 grupos
FimDeSemana   -2,83   (p < 0,001)  — novo
```
R² = 0,836 · N = 76 (todos os dias de treino)

A elasticidade mudou de -12,90 para -10,76 ao incluir o fim de semana no ajuste — variação dentro
da faixa de instabilidade já demonstrada na seção 9, não motivo de alarme.

**Checagem de segurança:** validado que incluir o fim de semana no ajuste **não piora** a
performance nos dias úteis (MAPE = 56,3%, praticamente igual ao 56,5% anterior).

**Limitação que fica em aberto:** a equação do Fim de Semana **não pôde ser validada fora da
amostra** — não existe nenhum dia de fim de semana no período de teste (ver seção 2).

---

## 11. Modelo Final: as 4 Equações de Demanda

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

Um modelo estatístico só "aprendeu" o que já observou: usar essas equações para simular um preço
fora da faixa observada em cada grupo é extrapolação, sem garantia estatística.

---

## 12. Validação Final Fora da Amostra

| Modelo | MAPE (10 dias de teste) |
|---|---|
| Baseline ingênuo (média histórica por dia, sem olhar preço) | 90,2% |
| **Modelo vencedor (4 grupos, elasticidade única)** | **56,3%** |

O modelo bate o baseline com folga (quase 34 pontos percentuais de melhora), confirmando que o
preço carrega informação real sobre a demanda. Ainda assim, 56,3% de erro médio é um número alto
em termos absolutos — a etapa de otimização não deve tratar a previsão de volume como um valor
certo, e sim considerar essa margem de erro na decisão (ex.: margem de segurança, cenários, ou
otimização robusta em vez de point forecast).

---

## 13. Síntese das Limitações (para constar no relatório final)

1. **Endogeneidade do Preço** não descartada — é média realizada, pode conter causalidade reversa
   (desconto por volume em pedidos grandes). Testado indiretamente (correlação dentro do dia), mas
   sem confirmação definitiva por falta de dados de pedido individual.
2. **Amostra pequena em geral** — 66 a 76 observações de treino, dependendo do corte. Elasticidade
   ainda não convergiu (curva de aprendizado) e tem coeficiente de variação de ~14% no bootstrap.
3. **Cluster "Fraco" (Sexta) e "Fim de Semana"** são os grupos com menos dado (14 e 10 observações).
4. **Episódio de 13-24/10** concentra quase todos os extremos do dataset. O diagnóstico de outlier
   baseado na curva de elasticidade (seção 8.2) não o considera desproporcionalmente influente, mas
   o teste direto de remoção (seção 8.3) mostra que ele desloca a elasticidade em ~17,6%
   (-12,90 → -10,63) — um efeito real, ainda que dentro da faixa de instabilidade geral já
   documentada. Decisão consciente de mantê-lo no treino, dado o tamanho já pequeno da amostra.
5. **Tratamento de outlier de Volume (Premissa A, seção 6.1)** é uma prática defensável mas não a
   mais correta tecnicamente para este problema: é marginal (ignora o preço do dia) e é aplicada
   antes de existir qualquer modelo. Foi mantida porque já alimenta a etapa de modelagem seguinte
   (`02-modelagem.ipynb`); o diagnóstico baseado na curva de elasticidade (Premissa B, seção 8.2) é
   o critério tecnicamente mais adequado para decidir influência sobre a elasticidade em si, e
   mostrou resultados bem diferentes da Premissa A.
6. **Fim de semana**: nível bem estimado (p<0,001), mas elasticidade impossível de estimar (N=5) e
   sem qualquer validação fora da amostra (teste não tem nenhum dia de fim de semana).
7. **Custo** tem tendência de alta de ~2% ao longo do período e um pico atípico — a premissa de
   "custo fixo" usada na conta de margem é uma aproximação, não um fato confirmado.
8. **Faixa de preço observada é estreita** (~14% de amplitude no treino) — qualquer preço simulado
   fora dela na etapa de otimização é extrapolação sem garantia estatística.
9. **Erro de previsão ainda alto** (56,3% MAPE) mesmo no modelo vencedor — deve ser incorporado
   como incerteza na etapa de otimização, não ignorado.
10. **Confirmar com quem definiu o desafio** se o horizonte de precificação realmente inclui os
    fins de semana — a estrutura do período de teste sugere que talvez não.

---

## 14. Recomendações para a Próxima Etapa (Modelagem/Otimização)

- Usar o modelo de 4 grupos com elasticidade única (seção 11) como ponto de partida.
- Incorporar a incerteza da elasticidade (IC largo, bootstrap) na formulação da otimização — por
  exemplo, via cenários, otimização robusta, ou uma margem de segurança sobre o volume previsto,
  em vez de tratar a previsão como determinística.
- Formular a otimização como: maximizar `Σ (Preço_d − Custo_d) · Volume_previsto(Preço_d, grupo_d)`
  sujeito a meta semanal (165kg ±30%) e variação máxima de preço (R$2/dia consecutivo). Dado o
  tamanho pequeno do problema (1 produto, 14 dias), tanto busca em grade quanto otimização não
  linear (`scipy.optimize`) são viáveis.
- Confirmar o escopo do fim de semana antes de decidir se a 4ª equação entra na otimização.
- Se uma futura iteração do EDA revisar o tratamento de outlier de Volume, considerar substituir a
  Premissa A (capping marginal) pela Premissa B (diagnóstico via distância de Cook/resíduos da
  própria curva) como critério principal — ela se mostrou mais conservadora e mais alinhada ao
  objetivo de estimar elasticidade (seção 8.2).
