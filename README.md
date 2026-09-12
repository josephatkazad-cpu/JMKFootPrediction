# JMK Prediction Foot

Projet Android complet + backend Flask + frontend + GitHub Actions.

## Serveur intégré dans l'application
L'application Android appelle directement :
`https://josephatkazad2013.pythonanywhere.com`

Il n'y a **aucun écran demandant à l'utilisateur de saisir une URL**.

## Structure
- `app/` : application Android native Java.
- `backend/` : API Flask compatible avec `/api/status`, `/api/fixtures` et `/api/analyze`.
- `frontend/` : interface web de référence.
- `.github/workflows/android.yml` : construction automatique de `JMK-Prediction-Foot.apk`.
- `gradle/` + `gradlew` + `gradlew.bat` : structure Gradle.

## GitHub
Après import du dossier dans un dépôt GitHub, le workflow se lance sur `main` ou manuellement. Le fichier APK est disponible dans l'onglet Actions > workflow > Artifacts.

## Backend PythonAnywhere
Le backend doit avoir une clé API Football dans une variable d'environnement `API_FOOTBALL_KEY`. Ne jamais mettre une clé secrète dans GitHub ou dans l'application Android.

## Important
Le wrapper JAR n'est pas inclus car cet environnement de préparation est hors ligne. Le workflow GitHub utilise directement Gradle 8.11.1 et produit l'APK sans ce JAR. Android Studio peut également régénérer le wrapper standard si nécessaire.
