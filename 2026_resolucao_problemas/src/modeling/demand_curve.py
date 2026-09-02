"""Curva de demanda (elasticidade Preço-Volume) do Produto_A.

Volume = A * Preço^-B, com uma elasticidade única (B) para todos os dias e um
nível (A) por grupo de dia da semana.

Decisão tomada em notebooks/01-EDA_v3.ipynb (seções "Torneio de Modelos" e
"Torneio 2: Tratamento de Outlier x Agrupamento"):
- Agrupamento: Pico (Segunda), TerQuaQui (Terça+Quarta+Quinta), Fraco (Sexta),
  FimDeSemana (Sábado+Domingo) — venceu o Torneio de Modelos original contra
  5 alternativas (MAPE fora da amostra, BIC, significância estatística).
- Tratamento de outlier: regressão robusta (M-estimador de Huber) sobre o
  Volume bruto, sem capping por IQR. O capping marginal (Premissa A) foi
  testado formalmente contra alternativas (bruto, remoção por distância de
  Cook, robusta de Huber) e perdeu: empata ou perde em MAPE fora da amostra,
  e atenua a elasticidade estimada em ~15-20% sem ganho de generalização.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.robust.robust_linear_model import RLMResultsWrapper

CLUSTER_BASE = "TerQuaQui"


def assign_cluster(dia_da_semana: str) -> str:
    """Mapeia um dia da semana para o grupo de demanda (nível A) usado na curva."""
    if dia_da_semana == "Segunda":
        return "Pico"
    if dia_da_semana in ("Terça", "Quarta", "Quinta"):
        return "TerQuaQui"
    if dia_da_semana == "Sexta":
        return "Fraco"
    return "FimDeSemana"


def _design_matrix(df: pd.DataFrame) -> pd.DataFrame:
    dummies = pd.get_dummies(df["Cluster"], dtype=int)
    dummies = dummies.drop(columns=[CLUSTER_BASE], errors="ignore")
    X = pd.concat([np.log(df["Preço"]).rename("ln_Preco"), dummies], axis=1)
    return sm.add_constant(X)


def fit_demand_curve(df: pd.DataFrame) -> RLMResultsWrapper:
    """Ajusta a curva de demanda oficial sobre os dados de treino.

    `df` precisa ter as colunas `Preço` e `Volume Realizado (kg)`, e ou uma
    coluna `Cluster` já pronta, ou `Dia da Semana` (o cluster é derivado via
    `assign_cluster`). Sem nenhum tratamento de outlier prévio: a robustez a
    pontos influentes vem da própria regressão (Huber/IRLS), não de um
    capping aplicado antes do ajuste.
    """
    df = df.copy()
    if "Cluster" not in df.columns:
        df["Cluster"] = df["Dia da Semana"].apply(assign_cluster)
    X = _design_matrix(df)
    y = np.log(df["Volume Realizado (kg)"])
    return sm.RLM(y, X, M=sm.robust.norms.HuberT()).fit()


def predict_volume(modelo: RLMResultsWrapper, preco: float, cluster: str) -> float:
    """Prevê o volume esperado (kg) para um preço e grupo de dia dados."""
    linha = {"const": 1.0, "ln_Preco": np.log(preco)}
    for col in modelo.params.index:
        if col not in ("const", "ln_Preco"):
            linha[col] = 1.0 if col == cluster else 0.0
    X = pd.DataFrame([linha])[modelo.params.index]
    return float(np.exp(modelo.predict(X).iloc[0]))
