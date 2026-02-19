#!/usr/bin/env python3
"""Generate a high-quality prompt for the agent to write a 5-minute bilingual PT-BR story.

We generate the *prompt* deterministically so the creative work stays in the model.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--words-json", required=True, help="JSON array of target English words")
    ap.add_argument("--minutes", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    words = json.loads(args.words_json)
    if not isinstance(words, list) or not words:
        raise SystemExit("words-json must be a JSON array with at least 1 word")

    if args.seed:
        random.seed(args.seed)

    theme = random.choice(
        [
            "uma aventura no parque",
            "uma noite chuvosa e aconchegante",
            "um piquenique no quintal",
            "uma visita a uma biblioteca mágica",
            "uma missão de ajudar um amigo",
            "um dia de brinquedos e organização",
        ]
    )

    # Constraints tuned for toddlers.
    prompt = {
        "role": "system",
        "content": ""  # we output a user prompt only
    }

    user = f"""Escreva uma história infantil de ~{args.minutes} minutos para crianças de 3 e 2 anos.

Personagens fixos:
- Tico: urso robô curioso e gentil.
- Nino: urso pequenininho, brincalhão e carinhoso.

Objetivo didático (bilingue):
- A história deve ser majoritariamente em **português (pt-BR)**.
- Em vez de inserir as palavras em inglês isoladas, você vai ensinar por meio de **frases completas em inglês**, curtas e fáceis.
- Você DEVE usar exatamente estas palavras em inglês (lista abaixo) pelo menos 1x cada, mas sempre dentro de **frases completas** (não soltar a palavra sozinha):
  {', '.join(words)}
- Para cada palavra da lista, inclua **pelo menos 1 frase completa em inglês** que contenha essa palavra.
- Após cada frase em inglês, coloque **entre parênteses a pronúncia** como uma **aproximação em pt-BR**, pensando em um leitor brasileiro (falante de português) — simples de ler, sem símbolos fonéticos.
  Ex.: "Come with me." (kâm uíth mí)
- Não traduza imediatamente no meio do parágrafo (não faça “word = tradução” logo após usar). Guarde as traduções para o glossário no final.
- Prefira frases simples e repetição leve. Crianças pequenas aprendem por repetição.

Estratégias didáticas obrigatórias:
1) Criar 2–3 **frases-modelo em inglês** (curtas) e repetir essas mesmas frases ao longo da história.
   - Sempre com pronúncia entre parênteses logo após a frase.
2) Usar perguntas simples em português para engajar (ex.: “Onde está o ___?”, “Você viu o ___?”).
3) Incluir ações/gestos (ex.: “vamos bater palmas”, “vamos apontar”, “vamos respirar fundo”).
4) Encerrar com um mini “momento de prática” (30–60s) com 5 prompts rápidos e divertidos.
   - Pelo menos 2 prompts devem pedir para a criança repetir **uma frase inteira em inglês**.

Restrições de estilo:
- Tom caloroso, engraçadinho, seguro.
- Sem temas assustadores, sem violência.
- Uma trama simples com começo-meio-fim.
- Tema sugerido de hoje: {theme}.

Formato de saída (Markdown):
- Título
- História
- Seção final: “Prática rápida” (com 5 prompts curtos)
- Seção final: “Glossário”
  - Para cada palavra do dia: inclua **1 frase em inglês** (a melhor/mais didática que você usou), a **pronúncia** (entre parênteses) como aproximação **para um leitor brasileiro**, e a **tradução/ideia em pt-BR**.
  - Formato sugerido (1 item por palavra):
    - **word** — "English sentence." (pronúncia) — tradução/ideia
- Seção final: “Palavras de hoje” (lista das palavras em inglês usadas)
"""

    print(user)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
