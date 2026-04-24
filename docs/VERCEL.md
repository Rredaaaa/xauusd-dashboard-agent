# Deploiement Vercel

Cette version ajoute une application web compatible Vercel:

- `public/index.html`: dashboard visible dans le navigateur.
- `api/xauusd.py`: endpoint serverless qui recupere le prix XAU/USD, les indicateurs et les analyses.
- `vercel.json`: configuration de cache et duree max de fonction.

## Fonctionnement

Quand la page Vercel est ouverte ou rafraichie, le navigateur appelle:

```text
/api/xauusd?mode=quick
```

Ce mode met a jour le prix, le contexte macro et la technique avec une requete plus legere.
La page lance aussi un chargement complet:

```text
/api/xauusd?mode=full
```

Ce mode ajoute les actualites, le geopolitique, le sentiment et les flux. Il peut etre plus lent car il depend de plusieurs sources externes.

Le dashboard relance automatiquement le mode rapide toutes les 60 secondes. Un refresh du navigateur force aussi une nouvelle requete API, donc les donnees sont actualisees si les sources repondent.

## Mise en ligne depuis GitHub

1. Aller sur <https://vercel.com/new>.
2. Importer le depot GitHub `Rredaaaa/xauusd-dashboard-agent`.
3. Garder le dossier racine du projet comme `Root Directory`.
4. Choisir `Other` si Vercel demande un framework.
5. Deployer.

## Variables d'environnement

Aucune variable n'est obligatoire pour la version Vercel actuelle.

L'analyse IA OpenAI reste optionnelle dans la version locale. Ne jamais publier le fichier `.env`.

## Limites importantes

- Les donnees viennent de sources publiques qui peuvent parfois bloquer ou ralentir une requete.
- Le mode complet peut prendre plus longtemps que le mode rapide.
- Vercel execute l'API a la demande: il n'y a pas de stockage permanent des rapports generes.
- Ce dashboard est une aide a la lecture du marche, pas un conseil financier personnalise.
