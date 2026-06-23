"""Importação do perfil Letterboxd: `ratings.csv` → [(tmdb_id, rating)].

O export oficial do Letterboxd (Settings → Import & Export) traz um `ratings.csv`
com as colunas: `Date, Name, Year, Letterboxd URI, Rating` (Name em inglês/original;
Rating 0.5–5.0 — mesma escala do nosso modelo, sem reescalar).

Resolução de `tmdb_id`:
  - `resolver="fuzzy"` (default, **funciona agora**): casa por **título + ano**
    diretamente no catálogo com rapidfuzz. ⚠️ Limitação conhecida: os títulos do
    catálogo estão em PT e o `Name` do Letterboxd em inglês/original, então muitos
    filmes não casam. É um fallback temporário.
  - `resolver="tmdb"` (**melhoria futura, atrás de flag**): resolver via TMDB
    `/search/movie` (nome+ano) → tmdb_id, bem mais preciso para títulos PT.
    Requer `TMDB_API_KEY` (ainda não configurada) — hoje só um stub.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Optional, Union

from core import catalog

# Limiar de similaridade de título para aceitar um casamento fuzzy.
DEFAULT_TITLE_CUTOFF = 82.0


@dataclass
class ImportResult:
    matched: list[tuple[int, float]] = field(default_factory=list)  # [(tmdb_id, rating)]
    unmatched: list[dict] = field(default_factory=list)             # linhas não resolvidas
    total_rows: int = 0

    @property
    def match_rate(self) -> float:
        return len(self.matched) / self.total_rows if self.total_rows else 0.0


def _read_csv(source: Union[str, io.IOBase]) -> list[dict]:
    """Lê o ratings.csv de um caminho ou file-like. Tolera colunas ausentes."""
    if hasattr(source, "read"):
        text = source.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
    else:
        f = open(source, "r", encoding="utf-8-sig", newline="")
        reader = csv.DictReader(f)
    rows = [dict(r) for r in reader]
    if hasattr(source, "read") is False:
        f.close()
    return rows


def _parse_rows(rows: list[dict]) -> list[dict]:
    """Normaliza para {name, year, rating} a partir das colunas do Letterboxd."""
    parsed = []
    for r in rows:
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        try:
            rating = float(r.get("Rating") or "")
        except ValueError:
            continue  # filmes sem nota não servem para o colaborativo
        year_raw = (r.get("Year") or "").strip()
        try:
            year = int(year_raw) if year_raw else None
        except ValueError:
            year = None
        parsed.append({"name": name, "year": year, "rating": rating})
    return parsed


class _FuzzyResolver:
    """Casa (título, ano) contra o catálogo com rapidfuzz."""

    def __init__(self, title_cutoff: float = DEFAULT_TITLE_CUTOFF):
        from rapidfuzz import fuzz, process

        self._fuzz = fuzz
        self._process = process
        self.title_cutoff = title_cutoff

        self._catalog = catalog.get_catalog()
        # Listas paralelas para o rapidfuzz; índice por ano para restringir o espaço.
        self._ids: list[int] = []
        self._titles: list[str] = []
        self._by_year: dict[int, list[int]] = {}  # year -> índices em self._ids
        for tid, mv in self._catalog.items():
            i = len(self._ids)
            self._ids.append(tid)
            self._titles.append(mv.get("title") or "")
            y = mv.get("release_year")
            if y is not None:
                self._by_year.setdefault(int(y), []).append(i)

    def _candidate_indices(self, year: Optional[int]) -> list[int]:
        if year is None:
            # Sem ano: o título sozinho é fraco; só busca em todo o catálogo.
            return list(range(len(self._ids)))
        # Ano exato ±1 (lançamentos divergem 1 ano entre bases). Se nada existe
        # nessa janela, o filme não está no catálogo -> sem match (evita falso
        # positivo de cair para todos os anos).
        idx: list[int] = []
        for y in (year, year - 1, year + 1):
            idx.extend(self._by_year.get(y, []))
        return idx

    def resolve(self, name: str, year: Optional[int]) -> Optional[tuple[int, float]]:
        cand_idx = self._candidate_indices(year)
        choices = {i: self._titles[i] for i in cand_idx}
        best = self._process.extractOne(
            name, choices, scorer=self._fuzz.WRatio, score_cutoff=self.title_cutoff
        )
        if best is None:
            return None
        _title, score, idx = best
        return self._ids[idx], score


def _resolve_via_tmdb(parsed: list[dict], api_key: Optional[str]) -> ImportResult:
    """STUB — melhoria futura. Requer TMDB_API_KEY (não configurada)."""
    raise NotImplementedError(
        "Resolução via TMDB ainda não implementada (TMDB_API_KEY não configurada). "
        "Use resolver='fuzzy'. Veja a Fase 3 do plano."
    )


def import_ratings(
    source: Union[str, io.IOBase],
    resolver: str = "fuzzy",
    title_cutoff: float = DEFAULT_TITLE_CUTOFF,
    tmdb_api_key: Optional[str] = None,
) -> ImportResult:
    """Lê o `ratings.csv` do Letterboxd e devolve [(tmdb_id, rating)] resolvidos.

    `resolver`: 'fuzzy' (título+ano, funciona agora) ou 'tmdb' (futuro, stub).
    """
    parsed = _parse_rows(_read_csv(source))
    result = ImportResult(total_rows=len(parsed))

    if resolver == "tmdb":
        return _resolve_via_tmdb(parsed, tmdb_api_key)
    if resolver != "fuzzy":
        raise ValueError(f"resolver desconhecido: {resolver!r}")

    fr = _FuzzyResolver(title_cutoff=title_cutoff)
    for row in parsed:
        hit = fr.resolve(row["name"], row["year"])
        if hit is None:
            result.unmatched.append(row)
        else:
            tmdb_id, _score = hit
            result.matched.append((tmdb_id, row["rating"]))
    return result
