import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from export_rf_to_json import export_random_forest

MODEL_JSON_PATH = "../haferbot/analyse_und_gewicht_zeug/best_weight_model.json"


def safe_div(a, b):
    return a / b if b != 0 else 0.0


# ----------------------------
# 1. JSON-Datei einlesen
# ----------------------------
with open("../haferbot/analyse_und_gewicht_zeug/statistics.json", "r") as f:
    data = json.load(f)

# DataFrame erstellen
rows = []
for entry in data:
    infos = entry["infos"]
    if infos.get("best_weight", None) == None:
        continue
    rows.append(
        {
            "max_view": infos["max_view"],
            "views_less_30": infos["views_less_30"],
            # Ratios
            "max_view_norm": infos["max_view_norm"],
            "walls/blocked": infos["walls/blocked"],
            "min/blocked": infos["min/blocked"],
            "walls/width": infos["walls/width"],
            "max/width": infos["max/width"],
            "best_weight": infos["best_weight"],
        }
    )

df = pd.DataFrame(rows)
print("Erste 5 Zeilen der Daten:")
print(df.head())

# ----------------------------
# 2. Korrelationen prüfen
# ----------------------------
corr = df.corr()["best_weight"].sort_values(ascending=False)
print("\nKorrelation der Features mit best_weight:")
print(corr)

plt.figure(figsize=(8, 6))
sns.heatmap(df.corr(), annot=True, cmap="coolwarm")
plt.title("Korrelationsmatrix")
plt.show()

# ----------------------------
# 3. Random Forest Regression
# ----------------------------
X = df.drop("best_weight", axis=1)
y = df["best_weight"]

rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
rf_model.fit(X, y)

# Vorhersage
df["predicted_weight"] = rf_model.predict(X)

# ----------------------------
# 4. Modellbewertung
# ----------------------------
mse = mean_squared_error(y, df["predicted_weight"])
r2 = r2_score(y, df["predicted_weight"])
print(f"\nRandom Forest Regression - MSE: {mse:.4f}, R²: {r2:.4f}")

# Scatterplot: echte vs. vorhergesagte Werte
plt.figure(figsize=(6, 6))
plt.scatter(y, df["predicted_weight"])
plt.plot([y.min(), y.max()], [y.min(), y.max()], "r--")
plt.xlabel("Echte best_weight")
plt.ylabel("Vorhergesagte best_weight")
plt.title("Random Forest: Echte vs. Vorhergesagte Werte")
plt.show()

# ----------------------------
# 5. Feature Importance
# ----------------------------
importances = rf_model.feature_importances_
features = X.columns
plt.figure(figsize=(8, 6))
plt.barh(features, importances)
plt.xlabel("Feature Importance")
plt.title("Wichtigste Features für die Vorhersage von best_weight")
plt.show()
export_random_forest(rf_model, list(X.columns), MODEL_JSON_PATH)
