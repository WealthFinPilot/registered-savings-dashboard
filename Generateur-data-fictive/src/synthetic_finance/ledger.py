"""Moteur D — grand livre : ordres, parts, encaisse, frais de compte, rééquilibrages, valorisations.

Seule source de vérité des parts détenues. Chaque jour ouvrable, dans l'ordre :
1. rééquilibrages : nouvelle cible du J3 en vigueur ce jour, ou regard programmé sur la dérive ; la décision
   ne lit que la clôture de la veille (positions et VL), l'échange s'exécute à la VL de clôture du jour ;
2. mouvements externes du J3, exécutés à la VL de clôture du jour : un PAC suit la cible du compte, un
   ponctuel va d'abord aux fonds sous-pondérés à la veille, un retrait vend au prorata des valeurs de la veille ;
3. au dernier jour ouvrable du mois, frais de compte (FRAIS) prélevés par rachat de parts ;
4. valorisation des positions à la clôture.

Encaisse nulle en fin de journée : un apport est investi le jour même. Parts tenues en millièmes entiers,
montants en cents entiers. Le résidu d'arrondi d'un ordre, |parts × VL − montant|, reste dans la valeur ; il
est borné à 0,0005 × VL (parts arrondies) + 0,005 $ (vente de toutes les parts, montant arrondi au cent).
"""
import datetime as dt
import math
from collections.abc import Mapping
from dataclasses import dataclass

from .config import Config, ConfigError
from .market import jours_ouvrables
from .rng import flux, generateurs

SOUS_FLUX = ("controles", "fractions")
TYPES = {"PAC": 0, "PONCTUEL": 1, "RETRAIT": 2, "FRAIS": 3}
EVENEMENTS_CIBLE = {"revue_annuelle": "revue annuelle", "ajout_fonds": "ajout d'un fonds",
                    "prudence_marche": "prudence après une baisse", "retour_cible": "retour à la cible"}


class GrandLivreError(ValueError):
    """Opération impossible (retrait au-delà de la valeur du compte, fonds sans VL) : le moteur s'arrête."""


@dataclass
class GrandLivre:
    events: list[dict]
    external_movements: list[dict]
    internal_trades: list[dict]
    positions_daily: list[dict]
    account_values_daily: list[dict]

    def tables(self) -> dict[str, list[dict]]:
        return dict(self.__dict__)


def cents(x: float) -> int:
    return math.floor(x * 100 + 0.5)


def unites(montant: int, prix: float) -> int:
    """Millièmes de part pour « montant » cents à la VL « prix »."""
    return math.floor(montant / 100 / prix * 1000 + 0.5)


def valoriser(u: int, prix: float) -> int:
    """Valeur en cents de « u » millièmes de part."""
    return cents(u * prix / 1000)


def repartir(total: int, poids: Mapping[str, float]) -> dict[str, int]:
    """Répartit « total » cents au prorata des poids positifs, au plus fort reste ; la somme est exacte."""
    cles = sorted(k for k, w in poids.items() if w > 0)
    s = sum(poids[k] for k in cles)
    brut = {k: total * poids[k] / s for k in cles}
    part = {k: math.floor(v) for k, v in brut.items()}
    for k in sorted(cles, key=lambda k: (part[k] - brut[k], k))[:total - sum(part.values())]:
        part[k] += 1
    return part


def ecart(valeurs: dict[str, int], cible: dict[str, float]) -> float:
    """Dérive en points : ½ Σ |poids − cible| sur les fonds détenus ou visés, soit la part de la valeur à déplacer."""
    total = sum(valeurs.values())
    if total <= 0:
        return 0.0
    return 50 * sum(abs(valeurs.get(f, 0) / total - cible.get(f, 0) / 100) for f in set(valeurs) | set(cible))


def regards(cfg: Config, comptes: dict[str, dict], seed: int | None = None) -> tuple[dict[str, float],
                                                                                 dict[dt.date, set[str]]]:
    """Regards sur la dérive, tirés d'avance (ils ne dépendent pas du marché) : un seuil par compte, en points,
    puis des mois espacés d'une loi géométrique et un jour ouvrable tiré dans chacun."""
    if cfg.ledger is None:
        raise ConfigError("ledger : section absente de la configuration")
    g = generateurs(flux(cfg.seed if seed is None else seed)["ledger"], SOUS_FLUX)["controles"]
    par_mois: dict[tuple[int, int], list[dt.date]] = {}
    for j in jours_ouvrables(cfg.start_date, cfg.end_date):
        par_mois.setdefault((j.year, j.month), []).append(j)
    seuil: dict[str, float] = {}
    controles: dict[dt.date, set[str]] = {}
    for a in sorted(comptes):
        seuil[a] = round(float(g.uniform(*cfg.ledger["drift_threshold_pts"])), 1)
        n = comptes[a]["opened_at"].year * 12 + comptes[a]["opened_at"].month - 1
        while True:
            n += int(g.geometric(1 / cfg.ledger["drift_check_months"]))
            mois = par_mois.get((n // 12, n % 12 + 1))
            if mois is None:
                break
            controles.setdefault(mois[int(g.integers(len(mois)))], set()).add(a)
    return seuil, controles


def tenir_grand_livre(cfg: Config, tables: dict[str, list[dict]], seed: int | None = None) -> GrandLivre:
    if cfg.ledger is None:
        raise ConfigError("ledger : section absente de la configuration")
    p = cfg.ledger
    r = generateurs(flux(cfg.seed if seed is None else seed)["ledger"], SOUS_FLUX)
    comptes = {c["account_id"]: c for c in tables["accounts"]}
    fonds = {f["fund_id"]: f for f in tables["funds"]}
    vl = {(l["fund_id"], l["date"]): round(l["nav_total_return"], 6) for l in tables["fund_prices_daily"]}
    jours = jours_ouvrables(cfg.start_date, cfg.end_date)
    fins_mois = {j for j, k in zip(jours, jours[1:] + [None]) if k is None or k.month != j.month}

    # Cibles des comptes, par date d'effet ; une cible postérieure à l'ouverture est un changement (J3)
    groupes: dict[tuple[str, dt.date], dict[str, float]] = {}
    for l in tables["allocation_targets_history"]:
        if l["level"] == "account":
            groupes.setdefault((l["account_id"], l["effective_date"]), {})[l["fund_id"]] = l["target_weight"]
    cibles: dict[str, list[tuple[dt.date, dict[str, float]]]] = {}
    for (a, d), c in sorted(groupes.items()):
        cibles.setdefault(a, []).append((d, c))
    changements = {(a, d) for a, l in cibles.items() for d, _ in l if d > comptes[a]["opened_at"]}
    causes = {(e["account_id"], e["date"]): e["event_type"] for e in tables["events"] if e["event_type"] in EVENEMENTS_CIBLE}

    def cible(a: str, jour: dt.date) -> dict[str, float]:
        return [c for d, c in cibles[a] if d <= jour][-1]

    def prix(f: str, jour: dt.date) -> float:
        x = vl.get((f, jour))
        if x is None:
            raise GrandLivreError(f"{f} : aucune VL le {jour}")
        return x

    seuil, controles = regards(cfg, comptes, seed)

    parts: dict[str, dict[str, int]] = {a: {} for a in comptes}
    ordres: list[dict] = []
    evenements: list[dict] = []          # rééquilibrages ; « jeton » relie les ordres à l'événement
    frais: list[dict] = []
    positions: list[dict] = []
    valeurs_comptes: list[dict] = []

    def executer(jour: dt.date, a: str, sens: str, montants: dict[str, int], lien: tuple[str, object]) -> int:
        """Ordres en montants (cents) à la VL du jour. Un montant trop petit pour un millième de part rejoint le
        plus gros ordre qui en achète au moins un (à défaut, le fonds de plus petite VL) ; une vente ne dépasse
        jamais les parts détenues (au-delà, elle les vend toutes). Rend le total exécuté, en cents."""
        montants = {f: m for f, m in montants.items() if m > 0}
        if not montants:
            return 0
        nuls = [f for f in montants if unites(montants[f], prix(f, jour)) == 0]
        if nuls:
            pleins = [f for f in montants if f not in nuls]
            vers = (max(pleins, key=lambda f: (montants[f], f)) if pleins
                    else min(montants, key=lambda f: (prix(f, jour), f)))
            for f in nuls:
                if f != vers:
                    montants[vers] += montants.pop(f)
        total = 0
        for f in sorted(montants):
            x, m = prix(f, jour), montants[f]
            u = unites(m, x)
            if sens == "SELL":
                detenu = parts[a].get(f, 0)
                if detenu == 0:
                    continue
                if u >= detenu:
                    u, m = detenu, valoriser(detenu, x)
                parts[a][f] = detenu - u
                if parts[a][f] == 0:
                    del parts[a][f]
            else:
                parts[a][f] = parts[a].get(f, 0) + u
            if u == 0 and sens == "SELL":
                continue                                 # vente de moins d'un millième de part : rien à vendre
            if u == 0:
                raise GrandLivreError(f"{comptes[a]['account_alias']}, {jour} : ordre de {m / 100:.2f} $ inférieur à "
                                      f"un millième de part de {f}")
            ordres.append(dict(date=jour, account_id=a, fund_id=f, side=sens, units=u / 1000, unit_price=x,
                               gross_amount_cad=m / 100, fee_cad=0.0, lien=lien))
            total += m
        return total

    def vendre(jour: dt.date, a: str, montant: int, poids: Mapping[str, float], lien: tuple[str, object]) -> None:
        """Vend « montant » cents au prorata de « poids » ; un fonds vendu en entier laisse un reste, vendu au
        prorata des valeurs du jour des fonds encore détenus ; un reste trop petit pour être réparti se vend sur le
        fonds de plus petite VL."""
        reste = montant - executer(jour, a, "SELL", repartir(montant, poids), lien)
        for _ in range(len(fonds)):
            if reste <= 0 or not parts[a]:
                break
            vendu = executer(jour, a, "SELL", repartir(reste, {f: valoriser(u, prix(f, jour))
                                                               for f, u in parts[a].items()}), lien)
            if vendu == 0:
                vendu = executer(jour, a, "SELL", {min(parts[a], key=lambda f: (prix(f, jour), f)): reste}, lien)
                if vendu == 0:
                    break
            reste -= vendu
        if reste != 0:
            raise GrandLivreError(f"{comptes[a]['account_alias']}, {jour} : vente de {montant / 100:.2f} $ "
                                  f"impossible, il manque {reste / 100:.2f} $")

    def reequilibrer(jour: dt.date, a: str, valeurs: dict[str, int], vise: dict[str, float], cause: str) -> None:
        avant = ecart(valeurs, vise)
        if cause == "derive" and avant < seuil[a]:
            return                                       # dérive sous le seuil : rien à faire
        total = sum(valeurs.values())
        if total <= 0:
            return
        gf = r["fractions"]
        complet, fraction = gf.random() < p["full_rebalance_probability"], float(gf.uniform(*p["rebalance_fraction"]))
        phi = 1.0 if complet else fraction
        delta = {f: phi * (vise.get(f, 0) / 100 * total - valeurs.get(f, 0)) for f in sorted(set(valeurs) | set(vise))}
        ventes = {f: cents(-d / 100) for f, d in delta.items() if d < 0}
        achats = {f: d for f, d in delta.items() if d > 0}
        echange = sum(ventes.values())
        if echange < p["rebalance_min_cad"] * 100 or not achats:
            return                                       # échange trop petit pour qu'on s'en donne la peine
        prevu = repartir(echange, achats)
        apres = ecart({f: valeurs.get(f, 0) - ventes.get(f, 0) + prevu.get(f, 0) for f in delta}, vise)
        alias = comptes[a]["account_alias"]
        if cause == "derive":
            description = f"rééquilibrage du {alias} : dérive de {avant:.1f} points, au-delà du seuil de {seuil[a]:.1f} points"
        else:
            description = f"rééquilibrage du {alias} vers sa nouvelle cible ({EVENEMENTS_CIBLE[causes[(a, jour)]]})"
        jeton = len(evenements)
        evenements.append(dict(date=jour, event_type="reequilibrage", institution_id=comptes[a]["institution_id"],
                               account_id=a, description=description,
                               scenario_impact=f"échange de {echange / 100:.2f} $ ({phi:.0%} de l'écart) ; dérive "
                                               f"{avant:.1f} → {apres:.1f} points, à la clôture de la veille"))
        # Un fonds qui sort de la cible lors d'un rééquilibrage complet part en entier (montant au-delà de sa valeur) ;
        # les autres ventes partent ensemble, en montants
        entiers = {f for f in ventes if vise.get(f, 0) == 0 and phi == 1.0}
        vendu = executer(jour, a, "SELL", {f: m for f, m in ventes.items() if f not in entiers}, ("E", jeton))
        for f in sorted(entiers):
            vendu += executer(jour, a, "SELL", {f: valoriser(parts[a][f], prix(f, jour)) + 1}, ("E", jeton))
        executer(jour, a, "BUY", repartir(vendu, achats), ("E", jeton))

    def orienter(vise: dict[str, float], valeurs: dict[str, int], montant: int) -> Mapping[str, float]:
        """Ponctuel : comble d'abord les fonds sous-pondérés à la veille (Σ des manques ≥ montant)."""
        total = sum(valeurs.values()) + montant
        manques = {f: max(0.0, w / 100 * total - valeurs.get(f, 0)) for f, w in vise.items()}
        return manques if sum(manques.values()) > 0 else vise

    def prelever(jour: dt.date) -> None:
        """Frais de compte du mois : Σ valeurs des fonds × taux annuel du fonds ÷ 12, arrondi au cent. Taux sous le
        palier (account_fee_low_pct) ou au-delà (account_fee_high_pct) selon l'actif du ménage chez la société."""
        valeurs = {a: {f: valoriser(u, prix(f, jour)) for f, u in parts[a].items()} for a in sorted(comptes)}
        actif: dict[str, int] = {}
        for a, v in valeurs.items():
            actif[comptes[a]["institution_id"]] = actif.get(comptes[a]["institution_id"], 0) + sum(v.values())
        for a, v in valeurs.items():
            if not v:
                continue
            colonne = ("account_fee_high_pct" if actif[comptes[a]["institution_id"]] >= cfg.fee_tier_threshold_cad * 100
                       else "account_fee_low_pct")
            montant = cents(sum(x / 100 * fonds[f][colonne] / 100 / 12 for f, x in v.items()))
            if unites(montant, min(prix(f, jour) for f in v)) == 0:
                continue                                 # moins d'un millième de la part la moins chère : non prélevé
            jeton = len(frais)
            frais.append(dict(date=jour, account_id=a, movement_type="FRAIS", amount_cad=-montant / 100, event_id=None,
                              jeton=("F", jeton)))
            vendre(jour, a, montant, v, ("F", jeton))

    mouvements_jour: dict[dt.date, list[dict]] = {}
    for m in tables["external_movements"]:
        mouvements_jour.setdefault(m["date"], []).append(m)
    veille: dt.date | None = None
    for jour in jours:
        def valeurs_veille(a: str) -> dict[str, int]:
            return {f: valoriser(u, prix(f, veille)) for f, u in debut[a].items()} if veille else {}

        debut = {a: dict(parts[a]) for a in comptes}     # positions à la clôture de la veille
        for a in sorted(comptes):
            if (a, jour) in changements:
                reequilibrer(jour, a, valeurs_veille(a), cible(a, jour), "cible")
            elif a in controles.get(jour, ()):
                reequilibrer(jour, a, valeurs_veille(a), cible(a, jour), "derive")

        for m in mouvements_jour.get(jour, ()):
            a, montant = m["account_id"], cents(abs(m["amount_cad"]))
            lien = ("M", m["movement_id"])
            if m["movement_type"] == "PAC":
                executer(jour, a, "BUY", repartir(montant, cible(a, jour)), lien)
            elif m["movement_type"] == "PONCTUEL":
                executer(jour, a, "BUY", repartir(montant, orienter(cible(a, jour), valeurs_veille(a), montant)), lien)
            elif m["movement_type"] == "RETRAIT":
                valeur = sum(valoriser(u, prix(f, jour)) for f, u in parts[a].items())
                if valeur < montant:
                    raise GrandLivreError(f"retrait {m['movement_id']} du {jour} : {montant / 100:.2f} $ demandés, le "
                                          f"{comptes[a]['account_alias']} vaut {valeur / 100:.2f} $")
                vendre(jour, a, montant, valeurs_veille(a) or {f: valoriser(u, prix(f, jour)) for f, u in parts[a].items()},
                       lien)
            else:
                raise GrandLivreError(f"{m['movement_id']} : type {m['movement_type']} inattendu en entrée du grand livre")

        if jour in fins_mois:
            prelever(jour)

        for a, c in sorted(comptes.items()):
            if c["opened_at"] > jour or (c["closed_at"] is not None and c["closed_at"] <= jour):
                continue
            investi = 0
            for f, u in sorted(parts[a].items()):
                x = valoriser(u, prix(f, jour))
                positions.append(dict(date=jour, account_id=a, fund_id=f, units=u / 1000, market_value_cad=x / 100))
                investi += x
            valeurs_comptes.append(dict(date=jour, account_id=a, cash_cad=0.0, invested_value_cad=investi / 100,
                                        total_value_cad=investi / 100))
        veille = jour

    # --------------------------------------------------------------------------------------------
    # Identifiants : événements et mouvements du J3 complétés, puis renumérotés dans l'ordre chronologique
    # --------------------------------------------------------------------------------------------
    tous_ev = [(e["date"], 0, k, e) for k, e in enumerate(tables["events"])]
    tous_ev += [(e["date"], 1, k, e) for k, e in enumerate(evenements)]
    tous_ev.sort(key=lambda x: x[:3])
    id_ev, events = {}, []
    for n, (_, source, k, e) in enumerate(tous_ev, 1):
        id_ev[("E", k) if source else e["event_id"]] = f"E{n:04d}"
        events.append(dict(event_id=f"E{n:04d}", **{c: v for c, v in e.items() if c != "event_id"}))
    tous_m = [(m["date"], m["account_id"], TYPES[m["movement_type"]], k, m) for k, m in enumerate(tables["external_movements"])]
    tous_m += [(m["date"], m["account_id"], TYPES["FRAIS"], k, m) for k, m in enumerate(frais)]
    tous_m.sort(key=lambda x: x[:4])
    id_m, mouvements = {}, []
    for n, (*_, m) in enumerate(tous_m, 1):
        id_m[m["jeton"] if "jeton" in m else ("M", m["movement_id"])] = f"M{n:05d}"
        mouvements.append(dict(movement_id=f"M{n:05d}", date=m["date"], account_id=m["account_id"],
                               movement_type=m["movement_type"], amount_cad=m["amount_cad"],
                               event_id=id_ev[m["event_id"]] if m["event_id"] else None))
    ordres.sort(key=lambda o: (o["date"], o["account_id"]))           # tri stable : ordre d'exécution du jour
    trades = []
    for n, o in enumerate(ordres, 1):
        lien = o.pop("lien")
        trades.append(dict(trade_id=f"T{n:06d}", **o, movement_id=id_m.get(lien) if lien[0] != "E" else None,
                           event_id=id_ev[lien] if lien[0] == "E" else None))
    return GrandLivre(events, mouvements, trades, positions, valeurs_comptes)
