"""Query-SLM opcional: traduz a consulta PTâ†’EN com uma SLM instruct local.

As keywords da TMDB sÃ£o em inglÃªs; traduzir a consulta e usar a versÃ£o EN no
**sinal de keyword** aproxima a consulta desse espaÃ§o. Medido no harness de 52
casos (empilhado com o re-ranker): MRR 0.577 â†’ 0.589, hits@10 43 â†’ 44.

**Off por padrÃ£o** (`RECOMENDAI_QUERY_SLM=1` liga) â€” custa um modelo de ~3 GB e
~0.6 s/consulta, para um ganho modesto. SÃ³ **traduzimos**: enriquecer com "tropes"
de gÃªnero foi testado e PIORA (a SLM alucina termos e injeta ruÃ­do).

Auto-seleciona device CUDA â†’ MPS â†’ CPU. Degrada em silÃªncio se o modelo faltar.
"""

from __future__ import annotations

import os
from typing import Optional

from core.device import get_device

DEFAULT_QUERY_SLM = os.environ.get("RECOMENDAI_QUERY_SLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
QUERY_SLM_ENABLED = os.environ.get("RECOMENDAI_QUERY_SLM", "0").lower() in ("1", "true", "yes")

_SYSTEM = ("Translate the movie plot description to concise English. "
           "Output only the translation, one line.")


class QueryExpander:
    """Traduz a consulta PTâ†’EN com uma SLM instruct (carregada sob demanda)."""

    def __init__(self, model_name: str = DEFAULT_QUERY_SLM, device: Optional[str] = None,
                 max_new_tokens: int = 80):
        self.model_name = model_name
        self.device = device or get_device()
        self.max_new_tokens = max_new_tokens
        self._tok = None
        self._model = None
        self._cache: dict[str, str] = {}

    def _load(self):
        if self._model is None:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_name, dtype=torch.float16).to(self.device)
        return self._model

    def translate(self, query: str) -> str:
        """TraduÃ§Ã£o EN concisa da consulta (cacheada por consulta)."""
        if query in self._cache:
            return self._cache[query]
        model = self._load()
        text = self._tok.apply_chat_template(
            [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": query}],
            tokenize=False, add_generation_prompt=True)
        inputs = self._tok([text], return_tensors="pt").to(self.device)
        out = model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        res = self._tok.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        self._cache[query] = res
        return res
