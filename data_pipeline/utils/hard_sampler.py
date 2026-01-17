import random
from hard_dict import HARD_DICT

MIN_CATEGORIES = 1 # <-- minimum number of categories (change only this)


def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)


def sample_keywords(hard_dict):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.

    Returns:
        dict: {category_name: selected_item}
    """

    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in hard_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(
                data["items"]
            )[0]

    # --- Step 2: enforce minimum number of categories ---
    if len(selected) < MIN_CATEGORIES:
        remaining = list(set(hard_dict.keys()) - set(selected.keys()))
        remaining_weights = [hard_dict[c]["prob"] for c in remaining]

        while len(selected) < MIN_CATEGORIES:
            category = random.choices(
                remaining,
                weights=remaining_weights,
                k=1
            )[0]
            selected[category] = weighted_choice(
                hard_dict[category]["items"]
            )[0]

            idx = remaining.index(category)
            remaining.pop(idx)
            remaining_weights.pop(idx)

    return selected


# ---- Example usage ----
if __name__ == "__main__":
    for _ in range(1):
        print(sample_keywords(HARD_DICT))
