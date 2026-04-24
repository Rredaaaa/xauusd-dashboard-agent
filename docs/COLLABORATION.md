# Collaboration Git

Ce projet est partage entre plusieurs personnes. L'objectif est de garder le repo propre et facile a reprendre.

## Regle Importante

Ne jamais publier:

- `.env`
- cles API
- caches Python
- fichiers generes dans `reports/`

Les fichiers `reports/xauusd_dashboard.html`, `reports/xauusd_data.json` et `reports/xauusd_report.md` sont recrees automatiquement au lancement.

## Workflow Simple

Avant de travailler:

```powershell
git pull
```

Voir les changements:

```powershell
git status
```

Sauvegarder une modification:

```powershell
git add .
git commit -m "Message clair"
git push
```

Recuperer le travail de l'autre:

```powershell
git pull
```

## Conseils Pour Travailler a Deux

- Eviter de modifier le meme bloc de `xauusd_agent.py` au meme moment.
- Se prevenir avant les grosses modifications de dashboard ou de scoring.
- Faire des commits petits et nommes clairement.
- Tester avant de pousser avec `python -B -m unittest discover -s tests -v`.

## Fuseaux Horaires

Le projet est local: chacun voit les heures selon son ordinateur. Maroc et France peuvent donc avoir un decalage selon la saison. Pour comparer une analyse, utilisez aussi l'heure UTC presente dans les rapports.
