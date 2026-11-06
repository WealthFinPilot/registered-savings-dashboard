"""Droits de cotisation du personnage fictif (mode conservative_synthetic) : CELI, CELIAPP, REER.

Les plafonds viennent d'une seule source, `sql/plafonds.sql` du projet (droit public, canada.ca cité en
commentaire de chaque bloc) : ce module les relit, il n'en écrit aucun. La situation personnelle (première
année d'admissibilité au CELI, revenu gagné, droits REER inutilisés au départ) est fictive et tirée.

Règles appliquées, mêmes conventions que `sql/vues.sql` :
- CELI : droits au début de l'année Y = Σ plafonds annuels de la première année d'admissibilité à Y
  − cotisations des années antérieures + retraits des années antérieures (un retrait ne rend des
  droits que le 1er janvier suivant). Aucun CELI antérieur à l'horizon.
- CELIAPP : rien avant l'année d'ouverture du premier CELIAPP ; cette année-là, le plafond annuel ;
  ensuite le plus petit de : plafond annuel + report des droits inutilisés (borné à report_max), et
  plafond à vie − tout ce qui a été versé avant.
- REER : maximum déductible de l'année de déduction D = droits inutilisés à la fin de D − 1 + le
  moindre de TAUX_REER × revenu gagné de D − 1 et du plafond en dollars de D ; une cotisation appartient
  à l'année de déduction dont la période (ref.periode_reer) se termine à sa date ou après.
Le scénario typical ne dépasse jamais les droits : la marge d'excédent REER n'est pas utilisée.
"""
import datetime as dt
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import ConfigError

# R11 (sql/plafonds.sql) : 18 % du revenu gagné de l'année précédente. Un taux, pas un montant : la table
# ref.plafond n'a pas de rubrique de taux, et son schéma est partagé avec les vues du rapport.
TAUX_REER = 0.18
REGIMES_DROITS = ("CELI", "CELIAPP", "REER")

_PLAFOND = re.compile(r"\(\s*'(CELI|CELIAPP|REER)'\s*,\s*'(\w+)'\s*,\s*(NULL|\d{4})\s*,\s*([\d.]+)\s*,\s*'([^']*)'\s*\)")
_PERIODE = re.compile(r"\(\s*(\d{4})\s*,\s*DATE\s*'(\d{4}-\d{2}-\d{2})'\s*,\s*'([^']*)'\s*\)")


@dataclass(frozen=True)
class Plafonds:
    lignes: tuple[dict, ...]                  # regime, rubrique, annee (None = sans millésime), montant, regle
    periodes_reer: dict[int, dt.date]         # année de déduction -> fin de sa période de cotisation
    sha256: str

    def montant(self, regime: str, rubrique: str, annee: int | None = None) -> float:
        for l in self.lignes:
            if (l["regime"], l["rubrique"], l["annee"]) == (regime, rubrique, annee):
                return l["montant"]
        raise ConfigError(f"sql/plafonds.sql : {regime} {rubrique} {annee if annee is not None else '(sans année)'} absent")

    def annee_reer(self, jour: dt.date) -> int:
        for annee in sorted(self.periodes_reer):
            if self.periodes_reer[annee] >= jour:
                return annee
        raise ConfigError(f"sql/plafonds.sql : aucune période REER ne couvre le {jour} (ref.periode_reer à compléter)")


def lire_plafonds(chemin: Path) -> Plafonds:
    if not chemin.is_file():
        raise ConfigError(f"plafonds fiscaux introuvables : {chemin.name}")
    octets = chemin.read_bytes()
    texte = octets.decode("utf-8")
    lignes = tuple(dict(regime=r, rubrique=k, annee=None if a == "NULL" else int(a), montant=float(m), regle=g)
                   for r, k, a, m, g in _PLAFOND.findall(texte))
    periodes = {int(a): dt.date.fromisoformat(d) for a, d, _ in _PERIODE.findall(texte)}
    if not lignes or not periodes:
        raise ConfigError(f"{chemin.name} : aucun plafond ou aucune période REER reconnus")
    return Plafonds(lignes, periodes, hashlib.sha256(octets).hexdigest())


def trouver_plafonds(depart: Path) -> Path:
    """sql/plafonds.sql du projet : premier dossier parent de « depart » qui le contient."""
    for dossier in depart.resolve().parents:
        candidat = dossier / "sql" / "plafonds.sql"
        if candidat.is_file():
            return candidat
    raise ConfigError(f"sql/plafonds.sql introuvable au-dessus de {depart.name}")


@dataclass
class Personnage:
    celi_first_year: int
    revenus: dict[int, float]                 # revenu gagné fictif par année civile
    reer_unused_start: float                  # droits REER inutilisés à la fin de l'année précédant l'horizon


@dataclass
class Droits:
    """Registre chronologique des cotisations et retraits ; droits disponibles à toute date."""
    plafonds: Plafonds
    perso: Personnage
    premiere_annee_reer: int                  # année de déduction du premier jour de l'horizon
    ouverture_celiapp: int | None = None      # année d'ouverture du premier CELIAPP
    cotisations: dict[tuple[str, int], float] = field(default_factory=dict)
    retraits: dict[tuple[str, int], float] = field(default_factory=dict)

    def annee(self, regime: str, jour: dt.date) -> int:
        return self.plafonds.annee_reer(jour) if regime == "REER" else jour.year

    def _c(self, regime: str, annee: int) -> float:
        return self.cotisations.get((regime, annee), 0.0)

    def nouveaux(self, regime: str, annee: int) -> float:
        """Droits acquis au titre de l'année (avant report et plafond à vie)."""
        if regime == "CELI":
            return self.plafonds.montant("CELI", "plafond_annuel", annee) if annee >= self.perso.celi_first_year else 0.0
        if regime == "CELIAPP":
            return self.plafonds.montant("CELIAPP", "plafond_annuel", annee)
        return min(TAUX_REER * self.perso.revenus[annee - 1], self.plafonds.montant("REER", "plafond_annuel", annee))

    def debut(self, regime: str, annee: int) -> float:
        """Droits au début de l'année (année de déduction pour le REER)."""
        if regime == "CELI":
            acquis = sum(self.nouveaux("CELI", y) for y in range(self.perso.celi_first_year, annee + 1))
            return acquis - sum(v for (r, y), v in self.cotisations.items() if r == "CELI" and y < annee) \
                + sum(v for (r, y), v in self.retraits.items() if r == "CELI" and y < annee)
        if regime == "CELIAPP":
            if self.ouverture_celiapp is None or annee < self.ouverture_celiapp:
                return 0.0
            vie = self.plafonds.montant("CELIAPP", "plafond_vie")
            if annee == self.ouverture_celiapp:
                return min(self.nouveaux("CELIAPP", annee), vie)
            report = min(self.plafonds.montant("CELIAPP", "report_max"),
                         max(self.debut("CELIAPP", annee - 1) - self._c("CELIAPP", annee - 1), 0.0))
            verse = sum(v for (r, y), v in self.cotisations.items() if r == "CELIAPP" and y < annee)
            return min(self.nouveaux("CELIAPP", annee) + report, vie - verse)
        inutilises = self.perso.reer_unused_start if annee == self.premiere_annee_reer else \
            self.debut("REER", annee - 1) - self._c("REER", annee - 1)
        return inutilises + self.nouveaux("REER", annee)

    def disponible(self, regime: str, jour: dt.date) -> float:
        if regime == "COMP":
            return float("inf")
        a = self.annee(regime, jour)
        return self.debut(regime, a) - self._c(regime, a)

    def cotiser(self, regime: str, jour: dt.date, montant: float, hors_droits: bool = False) -> None:
        """hors_droits : cotisation d'un cas d'usage scénarisé (behaviour.scripted_lumps), admise au-delà
        des droits ; les droits restants deviennent négatifs et le rapport calcule l'excédent."""
        if regime == "COMP":
            return
        if not hors_droits and montant > self.disponible(regime, jour) + 1e-9:
            raise ConfigError(f"{regime} {jour} : cotisation {montant:.2f} au-delà des droits")
        cle = (regime, self.annee(regime, jour))
        self.cotisations[cle] = self._c(*cle) + montant

    def retirer(self, regime: str, jour: dt.date, montant: float) -> None:
        if regime in ("REER", "CELIAPP"):
            raise ConfigError(f"{regime} {jour} : retrait interdit dans ce scénario")
        if regime == "CELI":
            cle = ("CELI", jour.year)
            self.retraits[cle] = self.retraits.get(cle, 0.0) + montant

    def tableau(self, annees: dict[str, range]) -> list[dict]:
        """contribution_room : une ligne par régime et par année (de déduction pour le REER)."""
        lignes = []
        for regime in REGIMES_DROITS:
            for a in annees.get(regime, ()):
                debut, c = self.debut(regime, a), self._c(regime, a)
                lignes.append(dict(regime=regime, year=a, new_room_cad=round(self.nouveaux(regime, a), 2),
                                   room_start_cad=round(debut, 2), contributions_cad=round(c, 2),
                                   withdrawals_cad=round(self.retraits.get((regime, a), 0.0), 2),
                                   room_end_cad=round(debut - c, 2)))
        return lignes
