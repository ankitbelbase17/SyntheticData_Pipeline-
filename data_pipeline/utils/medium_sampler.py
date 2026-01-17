import random
from medium_dict import MEDIUM_DICT

MIN_CATEGORIES = 2   # <-- change this single value to control the minimum
def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)

def sample_keywords(medium_dict):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.

    Returns:
        dict: {category_name: selected_item}
    """

    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in medium_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(
                data["items"]
            )[0]

    # --- Step 2: enforce minimum number of categories ---
    if len(selected) < MIN_CATEGORIES:
        remaining = list(set(medium_dict.keys()) - set(selected.keys()))
        remaining_weights = [medium_dict[c]["prob"] for c in remaining]

        while len(selected) < MIN_CATEGORIES:
            category = random.choices(
                remaining,
                weights=remaining_weights,
                k=1
            )[0]
            selected[category] = weighted_choice(
                medium_dict[category]["items"]
            )[0]

            idx = remaining.index(category)
            remaining.pop(idx)
            remaining_weights.pop(idx)

    return selected

# ---- Example usage ----
if __name__ == "__main__":
    for _ in range(1):
        print(sample_keywords(MEDIUM_DICT))
