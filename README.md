# Perfect Props — NFL 2026 dashboard

A mobile-friendly, installable static dashboard built from your uploaded 2026 NFL weekly player-statistics CSV. Includes **4,624 qualifying thresholds** through **Week 7**, filtering, player search, favorites, weekly values, and CSV export.

## Publish on GitHub Pages

1. Download and unzip the supplied ZIP file.
2. Create a **public** GitHub repository, for example `nfl-perfect-props`.
3. Upload **all files and the `icons` folder** from the unzipped directory to the repository root. (Do not upload the ZIP itself.)
4. Open repository **Settings → Pages**.
5. Under **Build and deployment**, select **Deploy from a branch**, choose `main` and `/ (root)`, and save.
6. After GitHub publishes it, open `https://YOUR-USERNAME.github.io/nfl-perfect-props/` in Safari on your iPhone.
7. Tap **Share → Add to Home Screen → Add**. You'll have an app-like home-screen icon.

The site is a Progressive Web App (PWA), with an icon and offline cache after its first successful load. Favorites are saved in that browser/device, not synced between devices.

## Data and limitations

- Source: user-supplied `stats_player_week_2026.csv`, filtered to 2026 regular season Weeks 1–7.
- The dashboard displays **100% of recorded player-week rows**, not necessarily all official appearances. A player who appeared without a stats row could be mistakenly labeled perfect.
- The dataset is a frozen snapshot; it **does not update automatically**. To refresh, regenerate `data.json` from a newer dataset and update the title/cutoff.
- Passing yards in 25-yard steps, rushing/receiving/combined yards in 5-yard steps, and counting stats in 1-unit steps.
- No live odds or guaranteed winning picks. Historical 100% does not predict a future 100% probability.
- For private use, GitHub Pages generally requires a public repository on free plans, so do not publish private or proprietary data.
