"""Flux pseudoaléatoires indépendants, dérivés d'une seule graine.

L'ordre de FLUX est figé : ajouter un moteur se fait en fin de liste, sans décaler les flux existants
(un changement du moteur de comportement ne doit pas modifier l'univers ni les marchés).
"""
import numpy as np

FLUX = ("universe", "markets", "behaviour", "events", "ledger", "adapter")


def flux(seed: int) -> dict[str, np.random.SeedSequence]:
    return dict(zip(FLUX, np.random.SeedSequence(seed).spawn(len(FLUX))))


def generateurs(sequence: np.random.SeedSequence, noms: tuple[str, ...]) -> dict[str, np.random.Generator]:
    """Un Generator PCG64 par sous-flux nommé, dans l'ordre de noms."""
    return {n: np.random.default_rng(s) for n, s in zip(noms, sequence.spawn(len(noms)))}
