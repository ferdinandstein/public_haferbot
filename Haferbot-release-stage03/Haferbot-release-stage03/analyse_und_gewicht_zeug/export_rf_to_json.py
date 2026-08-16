import json


def export_random_forest(rf_model, feature_names, path):
    forest = {"features": feature_names, "trees": []}

    for estimator in rf_model.estimators_:
        tree = estimator.tree_
        forest["trees"].append(
            {
                "children_left": tree.children_left.tolist(),
                "children_right": tree.children_right.tolist(),
                "feature": tree.feature.tolist(),
                "threshold": tree.threshold.tolist(),
                "value": [v[0][0] for v in tree.value],
            }
        )

    with open(path, "w") as f:
        json.dump(forest, f)

    print(f"Modell als JSON gespeichert: {path}")
