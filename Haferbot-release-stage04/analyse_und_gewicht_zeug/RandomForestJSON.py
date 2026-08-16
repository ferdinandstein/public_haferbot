import json


class RandomForestJSON:
    def __init__(self, path):
        with open(path, "r") as f:
            data = json.load(f)

        self.features = data["features"]
        self.trees = data["trees"]

    def _predict_tree(self, tree, x):
        node = 0
        while True:
            feature = tree["feature"][node]
            if feature == -2:  # Leaf
                return tree["value"][node]

            threshold = tree["threshold"][node]
            if x[feature] <= threshold:
                node = tree["children_left"][node]
            else:
                node = tree["children_right"][node]

    def predict(self, feature_dict):
        # Feature-Vektor bauen (richtige Reihenfolge!)
        x = [feature_dict[name] for name in self.features]

        preds = []
        for tree in self.trees:
            preds.append(self._predict_tree(tree, x))

        return sum(preds) / len(preds)
