import random
from hard_dict import HARD_DICT
from medium_dict import MEDIUM_DICT

MIN_CATEGORIES_FROM_HARD = 3  # <-- minimum number of categories from HARD_DICT
MIN_CATEGORIES_FROM_MEDIUM = 3  # <-- minimum number of categories from MEDIUM_DICT


def weighted_choice(items: dict, k=1):
    """
    Selects k keys from a dict {item: weight}
    """
    keys = list(items.keys())
    weights = list(items.values())
    return random.choices(keys, weights=weights, k=k)


def sample_keywords(source_dict, min_categories):
    """
    Samples categories independently using their category probabilities.
    From each selected category, samples exactly one sub-item.

    Args:
        source_dict: Dictionary with category probabilities and items
        min_categories: Minimum number of categories to sample

    Returns:
        dict: {category_name: selected_item}
    """

    selected = {}

    # --- Step 1: sample categories independently ---
    for category, data in source_dict.items():
        if random.random() < data["prob"]:
            selected[category] = weighted_choice(
                data["items"]
            )[0]

    # --- Step 2: enforce minimum number of categories ---
    if len(selected) < min_categories:
        remaining = list(set(source_dict.keys()) - set(selected.keys()))
        remaining_weights = [source_dict[c]["prob"] for c in remaining]

        while len(selected) < min_categories:
            category = random.choices(
                remaining,
                weights=remaining_weights,
                k=1
            )[0]
            selected[category] = weighted_choice(
                source_dict[category]["items"]
            )[0]

            idx = remaining.index(category)
            remaining.pop(idx)
            remaining_weights.pop(idx)

    return selected


# ---- Example usage ----
if __name__ == "__main__":
    for i in range(1):
        # Sample from both dictionaries
        medium_keywords = sample_keywords(MEDIUM_DICT, MIN_CATEGORIES_FROM_MEDIUM)
        hard_keywords = sample_keywords(HARD_DICT, MIN_CATEGORIES_FROM_HARD)
        
        # Merge: start with medium, then override with hard (hard takes precedence)
        combined = {**medium_keywords, **hard_keywords}
        
        print(combined)
        print()
